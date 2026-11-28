"""0041: siete auditorías/8 informes, TOCTOU y rechazo de falsos permisos."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from worker.retirement_unified_gate_0041 import (
    SOURCES,
    InterlockNoConfiable,
    evaluar_interlock_0041,
    parsear_fuente_0041,
)

P18 = """PREFLIGHT_0018=REALIZADO_SOLO_LECTURA
PELICULAS_ANALIZADAS=4
DIARIOS_NTFS_VERIFICADOS=2
DIARIOS_VERIFICADOS_EN_SNAPSHOT=2
PELICULAS_BLOQUEADAS=4
PERMISO_DE_BORRADO_OTORGADO=NO
ARCHIVOS_ELIMINADOS=0
TORRENTS_MODIFICADOS=0
MOTIVO_FALTA_AUTORIZACION_ADMINISTRADOR=4
MOTIVO_HAY_PERFILES_SIN_MARCAR_VISTA=4
MEDIO_2=BLOQUEADA
MEDIO_3=BLOQUEADA
MEDIO_4=BLOQUEADA
MEDIO_5=BLOQUEADA"""
P19 = """ADMIN_PREFLIGHT_0019=SOLO_LECTURA
PELICULAS_ANALIZADAS=4
CANDIDATAS_SIN_OTROS_BLOQUEOS=0
HAY_CLAVE_ADMINISTRATIVA_EN_API=NO
APROBACIONES_EMITIDAS=0
PERMISO_BORRADO_FISICO=NO
OPERACIONES_BORRADO_Y_QBIT=0
BLOQUEO_FALTA_AUTORIZACION_ADMINISTRADOR=4"""
P26 = """CUSTODIA_QBIT_0026=SOLO_GET
DOBLE_SNAPSHOT_SQL_JELLYFIN_QBIT=COINCIDENTE
DOBLE_EVIDENCIA_DIARIOS_Y_NTFS=COINCIDENTE
DESCARGAS=2
TORRENT_COMPLETO_Y_EN_REPOSO_REPORTADO=0
TORRENT_NO_EN_REPOSO_O_INCOMPLETO=2
TORRENT_PROPIEDAD_O_RUTA_INCONSISTENTE=0
TORRENTS_CON_ARCHIVOS_EXTRA=2
ARCHIVOS_QBIT=6
ARCHIVOS_PUBLICADOS_CORRELACIONADOS=2
ARCHIVOS_EXTRA_PROTEGIDOS=4
EXTRAS_CON_NOMBRE_NO_NORMALIZABLE=2
EXTRAS_TIPO_VIDEO=0
EXTRAS_TIPO_SUBTITULO=0
EXTRAS_TIPO_METADATO=4
EXTRAS_TIPO_OTRO=0
BYTES_LOGICOS_EXTRAS_PROTEGIDOS=488
ARCHIVOS_CON_TAMANO_INCOMPATIBLE=0
ARCHIVOS_CON_PROGRESO_INCOMPLETO=0
ARCHIVOS_CON_PRIORIDAD_EXCLUIDA=0
BYTES_LOGICOS_EXTRAS_NO_SON_ESPACIO_RECUPERABLE=SI
EXTRAS_CONSERVADOS=SI
QUIETUD_TRANSACCIONAL_QBIT_JELLYFIN=NO
PERMISO_BORRADO_FISICO=NO
ARCHIVOS_ELIMINADOS=0
TORRENTS_MODIFICADOS=0"""
P27 = """SUPERFICIE_PLAYBACK_0027=SOLO_LECTURA
RUTAS_AUTENTICADAS_CONTADAS=3
TTL_HLS_SEGUNDOS=14400
PUERTO_JELLYFIN_PUBLICADO_SOLO_LOOPBACK=SI
OTROS_ACCESOS_JELLYFIN_DESCARTADOS=NO
PROTOCOLO_ADMISION_0027_INSTALADO=NO
BLOQUEO_REAL_DE_NUEVOS_STREAMS=NO
PERMISO_BORRADO_FISICO=NO
SERVICIOS_MODIFICADOS=0
REPRODUCCIONES_MODIFICADAS=0"""
P33 = """RETIRADA_ACCESOS_0033=AUDITORIA_REAL_SOLO_LECTURA
ESTADO_RETIRADA_0033=BLOQUEADA
PERMISO_DE_BORRADO_OTORGADO=NO
ARCHIVOS_ELIMINADOS=0
TORRENTS_MODIFICADOS=0
BARRERA_QBITTORRENT_EXPUESTO=PENDIENTE"""
P37 = """RETIRADA_SIDS_0037=AUDITORIA_REAL_SOLO_LECTURA
ESTADO_RETIRADA_0037=BLOQUEADA
BARRERA_QBITTORRENT_SIN_SEGREGAR=PENDIENTE
PERMISO_DE_BORRADO_OTORGADO=NO
ARCHIVOS_REALES_ELIMINADOS=0
TORRENTS_REALES_MODIFICADOS=0"""
P40 = """RETIRADA_WEBUI_QBIT_0040=AUDITORIA_REAL_SOLO_LECTURA
ESTADO_RETIRADA_0040=BLOQUEADA
BARRERA_GUI_QBIT_EN_SID_OPERADOR=PENDIENTE
PERMISO_DE_BORRADO_OTORGADO=NO
ARCHIVOS_ELIMINADOS=0
TORRENTS_MODIFICADOS=0"""
RAW = {
    "0018_inicial": P18, "0018_final": P18, "0019": P19,
    "0026": P26, "0027": P27, "0033": P33, "0037": P37,
    "0040": P40,
}


def test_todos_los_informes_completos_tampoco_autorizan():
    assert set(RAW) == set(SOURCES)
    decision = evaluar_interlock_0041(RAW)
    assert decision["estado"] == "bloqueada"
    assert decision["fuentes_verificadas"] == 8
    assert decision["fuentes_exigidas"] == 8
    assert decision["puede_retirar_archivos"] is False
    assert decision["permiso_de_borrado_otorgado"] is False
    assert "aislamiento_kernel_ntfs_no_instalado" in decision["motivos"]


@pytest.mark.parametrize("missing", SOURCES)
def test_falta_fuente_nunca_permite_borrar(missing):
    partial = {k: v for k, v in RAW.items() if k != missing}
    result = evaluar_interlock_0041(partial)
    assert "inventario_de_fuentes_incompleto" in result["motivos"]
    assert not result["permiso_de_borrado_otorgado"]


@pytest.mark.parametrize("name, marker", (
    ("0018_inicial", "DIARIOS_NTFS_VERIFICADOS=2"),
    ("0019", "CANDIDATAS_SIN_OTROS_BLOQUEOS=0"),
    ("0026", "ARCHIVOS_EXTRA_PROTEGIDOS=4"),
    ("0027", "PROTOCOLO_ADMISION_0027_INSTALADO=NO"),
    ("0033", "ESTADO_RETIRADA_0033=BLOQUEADA"),
    ("0037", "ESTADO_RETIRADA_0037=BLOQUEADA"),
    ("0040", "ESTADO_RETIRADA_0040=BLOQUEADA"),
    ("0018_final", "PERMISO_DE_BORRADO_OTORGADO=NO"),
))
def test_toda_fuente_truncada_falla_cerrada(name, marker):
    report = dict(RAW)
    report[name] = report[name].replace(marker + "\n", "")
    if report[name] == RAW[name]:
        report[name] = report[name].replace(marker, "")
    result = evaluar_interlock_0041(report)
    assert "fuente_" + name.split("_")[0] + "_no_verificable" in result["motivos"]
    assert not result["permiso_de_borrado_otorgado"]


@pytest.mark.parametrize("key,needle,replacement", (
    ("0018_final", "PELICULAS_BLOQUEADAS=4", "PELICULAS_BLOQUEADAS=3"),
    ("0018_final", "MEDIO_2=BLOQUEADA", "MEDIO_2=AUTORIZADA"),
    ("0018_final", "TORRENTS_MODIFICADOS=0", "TORRENTS_MODIFICADOS=1"),
    ("0019", "APROBACIONES_EMITIDAS=0", "APROBACIONES_EMITIDAS=1"),
    ("0019", "HAY_CLAVE_ADMINISTRATIVA_EN_API=NO",
     "HAY_CLAVE_ADMINISTRATIVA_EN_API=SI"),
    ("0026", "QUIETUD_TRANSACCIONAL_QBIT_JELLYFIN=NO",
     "QUIETUD_TRANSACCIONAL_QBIT_JELLYFIN=SI"),
    ("0026", "ARCHIVOS_EXTRA_PROTEGIDOS=4", "ARCHIVOS_EXTRA_PROTEGIDOS=0"),
    ("0027", "PROTOCOLO_ADMISION_0027_INSTALADO=NO",
     "PROTOCOLO_ADMISION_0027_INSTALADO=SI"),
    ("0033", "ESTADO_RETIRADA_0033=BLOQUEADA",
     "ESTADO_RETIRADA_0033=AUTORIZADA"),
    ("0037", "ESTADO_RETIRADA_0037=BLOQUEADA",
     "ESTADO_RETIRADA_0037=AUTORIZADA"),
    ("0040", "ESTADO_RETIRADA_0040=BLOQUEADA",
     "ESTADO_RETIRADA_0040=AUTORIZADA"),
))
def test_falsos_permisos_o_datos_contradictorios_rechazados(
    key, needle, replacement,
):
    altered = dict(RAW)
    altered[key] = altered[key].replace(needle, replacement)
    verdict = evaluar_interlock_0041(altered)
    assert not verdict["permiso_de_borrado_otorgado"]
    assert "fuente_" + key.split("_")[0] + "_no_verificable" in verdict["motivos"]


def test_drift_en_preflight_valido_detectado():
    reports = dict(RAW)
    reports["0018_final"] += "\nMOTIVO_TORRENT_ACTIVO_O_INCOMPLETO=2"
    decision = evaluar_interlock_0041(reports)
    assert decision["fuentes_verificadas"] == 8
    assert "preflight_0018_cambio_durante_auditoria" in decision["motivos"]


def test_cambio_contador_de_peliculas_causal_evidencia_incoherente():
    report = dict(RAW)
    report["0019"] = P19.replace(
        "PELICULAS_ANALIZADAS=4", "PELICULAS_ANALIZADAS=5"
    )
    decision = evaluar_interlock_0041(report)
    assert "recuento_de_peliculas_incoherente" in decision["motivos"]


def test_diarios_superan_publicaciones_qbit_no_se_aceptan():
    report = dict(RAW)
    report["0018_inicial"] = P18.replace(
        "DIARIOS_VERIFICADOS_EN_SNAPSHOT=2",
        "DIARIOS_VERIFICADOS_EN_SNAPSHOT=3",
    )
    report["0018_final"] = report["0018_inicial"]
    result = evaluar_interlock_0041(report)
    assert "diarios_ntfs_no_cubiertos_por_qbit" in result["motivos"]


@pytest.mark.parametrize("source", (
    "0018", "0019", "0026", "0027", "0033", "0037", "0040",
))
def test_numeros_extras_o_datos_privados_rechazados(source):
    original = RAW["0018_final" if source == "0018" else source]
    for tail in (
        "\nRUTA=C:\\VIEWTV\\peliculas",
        "\nSID=S-1-5-21-111",
        "\nAPIKEY=secreto",
        "\nHASH_1=abcd",
        "\nARCHIVOS_ELIMINADOS=1",
        "\nINVALID=0",
        "\nPROTOCOLO=AUTORIZADO",
    ):
        with pytest.raises(InterlockNoConfiable):
            parsear_fuente_0041(source, original + tail)


@pytest.mark.parametrize("source", ("0018", "0019", "0026", "0027", "0033", "0037", "0040"))
def test_informe_incompleto_o_no_textual_rechazado(source):
    for evidence in (None, 12, b"datos", {}, "", "x" * 16385):
        with pytest.raises(InterlockNoConfiable):
            parsear_fuente_0041(source, evidence)


def _runner():
    location = (
        Path(__file__).resolve().parents[2]
        / "scripts" / "viewtv_retirada_interlock_0041.py"
    )
    spec = importlib.util.spec_from_file_location("viewtv_interlock_0041", location)
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


def test_runner_sintetico_no_emite_ficheros_ni_peliculas(monkeypatch, capsys):
    runner = _runner()
    monkeypatch.setattr(
        runner, "_read_only",
        lambda source: RAW[source if source != "0018" else "0018_final"],
    )
    # Auditoría completa NO equivale a autorización: salida no-cero.
    assert runner.main() == 3
    output = capsys.readouterr().out
    assert "ESTADO_RETIRADA_0041=BLOQUEADA" in output
    assert "FUENTES_VERIFICADAS=8" in output
    assert "PERMISO_DE_BORRADO_OTORGADO=NO" in output
    assert "ARCHIVOS_ELIMINADOS=0" in output
    assert "TORRENTS_MODIFICADOS=0" in output
    assert "MEDIO_2" not in output
    assert "secreto" not in output


def test_runner_fallo_parcial_termina_codigo_2_sin_exponer_error(monkeypatch, capsys):
    runner = _runner()
    def read(source):
        if source == "0037":
            return None
        return RAW[source if source != "0018" else "0018_final"]

    monkeypatch.setattr(runner, "_read_only", read)
    assert runner.main() == 2
    output = capsys.readouterr().out
    assert "FUENTE_0037=NO_VERIFICABLE" in output
    assert "PERMISO_DE_BORRADO_OTORGADO=NO" in output


def test_runner_no_admite_scripts_fuera_de_lista():
    runner = _runner()
    assert runner._read_only("../../../windows/kill-process.ps1") is None


def test_fuentes_sin_hacer_unlink_nunca_permiten_commit():
    result = evaluar_interlock_0041(RAW)
    assert not result["puede_retirar_archivos"]
    assert not result["permiso_de_borrado_otorgado"]
