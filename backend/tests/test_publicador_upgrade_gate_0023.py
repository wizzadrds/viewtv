"""0023: estados de mantenimiento y rechazo de fuentes no confiables.

Los resultados Windows son sintéticos; ningún test lee tareas, vídeos,
credenciales, Windows ni qBittorrent reales.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from worker.publication_upgrade_gate_0023 import (
    InformeNoConfiable,
    evaluar_informe,
)

CURRENT: dict[str, str] = {
    "UPGRADE_0023": "SOLO_LECTURA",
    "PUBLICADOR_INSTALADO_COINCIDE_CON_FUENTE_0022": "NO",
    "HELPER_MUTEX_0022_INSTALADO": "NO",
    "HELPER_INSTALADO_COINCIDE_CON_FUENTE_0022": "NO",
    "TAREA_PROGRAMADA_CON_USUARIO_LIMITADO": "SI",
    "ACCION_TAREA_ES_ESPERADA": "SI",
    "WRAPPER_TAREA_COINCIDE_CON_FUENTE": "SI",
    "ESTADO_TAREA": "READY",
    "TAREA_EN_EJECUCION": "NO",
    "SERVICIO_SCM_EXISTE": "NO",
    "SERVICIO_SCM_ACTIVO": "NO",
    "PROCESOS_PUBLICADOR_OBSERVADOS": "0",
    "PROCESOS_POWERSHELL_SIN_LINEA_VISIBLE": "0",
    "VERSION_LISTA_PARA_REVISION_DE_MUTEX": "NO",
    "PUEDE_AFIRMARSE_EXCLUSION_PRODUCTIVA": "NO",
    "REEMPLAZO_AUTOMATICO_DESDE_AUDITORIA": "NO",
    "PROCESOS_DETENIDOS": "0",
    "TAREAS_MODIFICADAS": "0",
    "ARCHIVOS_MEDIA_MODIFICADOS": "0",
    "TORRENTS_MODIFICADOS": "0",
}


def report(overrides: dict[str, str] | None = None) -> str:
    items = deepcopy(CURRENT)
    items.update(overrides or {})
    return "\n".join(f"{key}={value}" for key, value in items.items()) + "\n"


def test_estado_real_simulado_identifica_cuatro_bloqueos():
    result = evaluar_informe(report())
    assert result["bloqueos"] == [
        "biblioteca_mutex_no_instalada",
        "instalacion_no_validada",
        "publicador_instalado_desactualizado",
        "tarea_no_deshabilitada",
    ]
    assert result["permite_actualizar_automaticamente"] is False
    assert result["permite_eliminar_peliculas"] is False
    assert result["comprobacion_solo_lectura"] is True


def test_tarea_deshabilitada_por_si_sola_no_autoriza_actualizar():
    result = evaluar_informe(report({"ESTADO_TAREA": "DISABLED"}))
    assert "tarea_no_deshabilitada" not in result["bloqueos"]
    assert "publicador_instalado_desactualizado" in result["bloqueos"]
    assert not result["permite_actualizar_automaticamente"]


def test_versiones_iguales_y_sin_procesos_tampoco_es_permiso():
    result = evaluar_informe(report({
        "ESTADO_TAREA": "DISABLED",
        "PUBLICADOR_INSTALADO_COINCIDE_CON_FUENTE_0022": "SI",
        "HELPER_MUTEX_0022_INSTALADO": "SI",
        "HELPER_INSTALADO_COINCIDE_CON_FUENTE_0022": "SI",
        "VERSION_LISTA_PARA_REVISION_DE_MUTEX": "SI",
    }))
    assert result["bloqueos"] == []
    assert result["estado"] == "requiere_intervencion_supervisada"
    assert not result["permite_actualizar_automaticamente"]
    assert not result["permite_eliminar_peliculas"]


@pytest.mark.parametrize(("key", "value", "reason"), [
    ("TAREA_PROGRAMADA_CON_USUARIO_LIMITADO", "NO", "privilegios_tarea_no_confiables"),
    ("ACCION_TAREA_ES_ESPERADA", "NO", "accion_tarea_diferente"),
    ("WRAPPER_TAREA_COINCIDE_CON_FUENTE", "NO", "wrapper_tarea_diferente"),
    ("PUBLICADOR_INSTALADO_COINCIDE_CON_FUENTE_0022", "NO", "publicador_instalado_desactualizado"),
    ("HELPER_MUTEX_0022_INSTALADO", "NO", "biblioteca_mutex_no_instalada"),
    ("SERVICIO_SCM_EXISTE", "SI", "servicio_publicador_detectado"),
    ("SERVICIO_SCM_ACTIVO", "SI", "servicio_publicador_activo"),
    ("PROCESOS_PUBLICADOR_OBSERVADOS", "1", "procesos_publicador_observados"),
    ("PROCESOS_POWERSHELL_SIN_LINEA_VISIBLE", "2", "procesos_no_inspeccionables"),
])
def test_origen_sospechoso_bloquea(key, value, reason):
    results = evaluar_informe(report({key: value}))
    assert reason in results["bloqueos"]
    assert results["permite_actualizar_automaticamente"] is False


def test_service_and_helper_versions_different():
    results = evaluar_informe(report({
        "HELPER_MUTEX_0022_INSTALADO": "SI",
        "HELPER_INSTALADO_COINCIDE_CON_FUENTE_0022": "NO",
    }))
    assert "biblioteca_mutex_version_diferente" in results["bloqueos"]


@pytest.mark.parametrize(("key", "value"), [
    ("UPGRADE_0023", "EJECUTAR"),
    ("PUEDE_AFIRMARSE_EXCLUSION_PRODUCTIVA", "SI"),
    ("REEMPLAZO_AUTOMATICO_DESDE_AUDITORIA", "SI"),
    ("TAREAS_MODIFICADAS", "1"),
    ("PROCESOS_DETENIDOS", "1"),
    ("ARCHIVOS_MEDIA_MODIFICADOS", "1"),
    ("TORRENTS_MODIFICADOS", "1"),
    ("ESTADO_TAREA", "UNKNOWN"),
    ("TAREA_EN_EJECUCION", "X"),
    ("PROCESOS_PUBLICADOR_OBSERVADOS", "-1"),
    ("PROCESOS_PUBLICADOR_OBSERVADOS", "000"),
    ("PROCESOS_PUBLICADOR_OBSERVADOS", "10000000"),
])
def test_informe_que_afirma_operaciones_o_permisos_es_rechazado(key, value):
    with pytest.raises(InformeNoConfiable):
        evaluar_informe(report({key: value}))


def test_informe_imposible_mutex_ausente_y_checksum_positivo_bloquea():
    with pytest.raises(InformeNoConfiable):
        evaluar_informe(report({
            "HELPER_MUTEX_0022_INSTALADO": "NO",
            "HELPER_INSTALADO_COINCIDE_CON_FUENTE_0022": "SI",
        }))


@pytest.mark.parametrize(("task", "active"), [
    ("RUNNING", "NO"),
    ("QUEUED", "NO"),
    ("READY", "SI"),
    ("DISABLED", "SI"),
])
def test_estado_de_tarea_inconsistente_es_denegado(task, active):
    with pytest.raises(InformeNoConfiable):
        evaluar_informe(report({
            "ESTADO_TAREA": task, "TAREA_EN_EJECUCION": active,
        }))


@pytest.mark.parametrize("invalid", [
    "", "privado", "TOKEN=privado", "PRIVATE=/mnt/secret",
    "ESTADO_TAREA=READY\n", "PUEDE_AFIRMARSE_EXCLUSION_PRODUCTIVA=SI\n",
    "A" * 4001,
])
def test_no_acepta_datos_no_acotados_o_filtrables(invalid):
    with pytest.raises(InformeNoConfiable):
        evaluar_informe(invalid)


def test_no_acepta_campos_desconocidos_duplicados_ni_faltantes():
    text = report()
    with pytest.raises(InformeNoConfiable):
        evaluar_informe(text + "USER_NAME=PRIVADO\n")
    with pytest.raises(InformeNoConfiable):
        evaluar_informe(text + "UPGRADE_0023=SOLO_LECTURA\n")
    with pytest.raises(InformeNoConfiable):
        evaluar_informe(text.replace("TORRENTS_MODIFICADOS=0\n", ""))


def test_se_pueden_reordenar_las_claves_sin_cambiar_decision():
    source = report()
    assert evaluar_informe("".join(reversed(source.splitlines(keepends=True)))) == (
        evaluar_informe(source)
    )
