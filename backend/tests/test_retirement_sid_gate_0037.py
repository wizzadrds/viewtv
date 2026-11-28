"""0037: parser cerrado y evaluación de identidades que nunca autoriza."""
from __future__ import annotations

import pytest
from worker.retirement_sid_gate_0037 import (
    SidsNoVerificables,
    evaluar_aislamiento_sids_0037,
    parsear_auditoria_sids_0037,
)

OK = "\n".join((
    "SIDS_WINDOWS_0037=OBSERVADOS_SOLO_LECTURA",
    "OPERADOR_ADMIN_ELEVADO=SI",
    "JELLYFIN_COMPARTE_SID_OPERADOR=SI",
    "QBIT_COMPARTE_SID_OPERADOR=SI",
    "PUBLICADOR_COMPARTE_SID_OPERADOR=SI",
    "DIRECTORIOS_RAIZ_ACL_PROTEGIDAS=1_DE_4",
    "CUENTAS_EFIMERAS_SIN_LIMPIAR=0",
    "BROKER_SID_DISTINTO_EN_PRODUCCION=NO_VERIFICADO",
    "LECTORES_SIN_FILE_WRITE_ATTRIBUTES_EN_PRODUCCION=NO_VERIFICADO",
    "AISLAMIENTO_KERNEL_ARCHIVOS_PRODUCCION=NO_VERIFICADO",
    "RETIRADA_POR_SIDS_PREPARADA=NO",
    "PERMISO_DE_BORRADO_OTORGADO=NO",
    "ARCHIVOS_REALES_ELIMINADOS=0",
    "TORRENTS_REALES_MODIFICADOS=0",
))
FAILED = "\n".join((
    "SIDS_WINDOWS_0037=EVIDENCIA_INCOMPLETA",
    "RETIRADA_POR_SIDS_PREPARADA=NO",
    "AISLAMIENTO_KERNEL_ARCHIVOS_PRODUCCION=NO_VERIFICADO",
    "PERMISO_DE_BORRADO_OTORGADO=NO",
    "ARCHIVOS_REALES_ELIMINADOS=0",
    "TORRENTS_REALES_MODIFICADOS=0",
))


def test_inventario_realista_bloquea_sids_compartidos():
    assert parsear_auditoria_sids_0037(OK)["CUENTAS_EFIMERAS_SIN_LIMPIAR"] == "0"
    answer = evaluar_aislamiento_sids_0037(OK, OK)
    assert answer["estado"] == "bloqueada"
    assert not answer["permiso_de_borrado_otorgado"]
    assert "jellyfin_sin_segregar" in answer["motivos"]
    assert "qbittorrent_sin_segregar" in answer["motivos"]
    assert "herencia_acl_de_raices_no_sellada" in answer["motivos"]


def test_todos_sids_distintos_y_acls_selladas_aun_bloquean_sin_prueba_kernel():
    no_shared = (
        OK.replace("SID_OPERADOR=SI", "SID_OPERADOR=NO")
        .replace("1_DE_4", "4_DE_4")
        .replace("OPERADOR_ADMIN_ELEVADO=SI", "OPERADOR_ADMIN_ELEVADO=NO")
    )
    answer = evaluar_aislamiento_sids_0037(no_shared, no_shared)
    assert "jellyfin_sin_segregar" not in answer["motivos"]
    assert "permisos_kernel_por_file_id_no_demostrados" in answer["motivos"]
    assert not answer["permiso_de_borrado_otorgado"]


def test_dos_lecturas_distintas_no_son_exclusion():
    changed = OK.replace("QBIT_COMPARTE_SID_OPERADOR=SI",
                         "QBIT_COMPARTE_SID_OPERADOR=NO")
    answer = evaluar_aislamiento_sids_0037(OK, changed)
    assert "auditorias_windows_distintas" in answer["motivos"]
    assert not answer["permiso_de_borrado_otorgado"]


def test_dato_desconocido_y_cuentas_sin_limpiar_bloquean():
    partial = OK.replace(
        "QBIT_COMPARTE_SID_OPERADOR=SI",
        "QBIT_COMPARTE_SID_OPERADOR=DESCONOCIDO",
    ).replace("CUENTAS_EFIMERAS_SIN_LIMPIAR=0",
              "CUENTAS_EFIMERAS_SIN_LIMPIAR=2")
    verdict = evaluar_aislamiento_sids_0037(partial, partial)
    assert "dueño_de_proceso_no_verificado" in verdict["motivos"]
    assert "cuentas_de_laboratorio_pendientes" in verdict["motivos"]


def test_fallo_cerrado_tiene_esquema_propio():
    assert parsear_auditoria_sids_0037(FAILED)[
        "SIDS_WINDOWS_0037"
    ] == "EVIDENCIA_INCOMPLETA"
    assert "estado_host_incompleto" in evaluar_aislamiento_sids_0037(
        FAILED, FAILED,
    )["motivos"]


@pytest.mark.parametrize("mutate", (
    lambda t: t + "\nSIDS_WINDOWS_0037=OBSERVADOS_SOLO_LECTURA",
    lambda t: t + "\nPASS=SI",
    lambda t: t + "\nRUTA_MEDIA=C:\\VIEWTV\\video.mkv",
    lambda t: t + "\nSID_OPERADOR=S-1-5-21-12",
    lambda t: t.replace("OPERADOR_ADMIN_ELEVADO=SI",
                        "OPERADOR_ADMIN_ELEVADO=admin"),
    lambda t: t.replace("JELLYFIN_COMPARTE_SID_OPERADOR=SI",
                        "JELLYFIN_COMPARTE_SID_OPERADOR="),
    lambda t: t.replace("DIRECTORIOS_RAIZ_ACL_PROTEGIDAS=1_DE_4",
                        "DIRECTORIOS_RAIZ_ACL_PROTEGIDAS=5_DE_4"),
    lambda t: t.replace("CUENTAS_EFIMERAS_SIN_LIMPIAR=0",
                        "CUENTAS_EFIMERAS_SIN_LIMPIAR=-1"),
    lambda t: t.replace("CUENTAS_EFIMERAS_SIN_LIMPIAR=0",
                        "CUENTAS_EFIMERAS_SIN_LIMPIAR=01"),
    lambda t: t.replace("BROKER_SID_DISTINTO_EN_PRODUCCION=NO_VERIFICADO",
                        "BROKER_SID_DISTINTO_EN_PRODUCCION=SI"),
    lambda t: t.replace("AISLAMIENTO_KERNEL_ARCHIVOS_PRODUCCION=NO_VERIFICADO",
                        "AISLAMIENTO_KERNEL_ARCHIVOS_PRODUCCION=SI"),
    lambda t: t.replace("PERMISO_DE_BORRADO_OTORGADO=NO",
                        "PERMISO_DE_BORRADO_OTORGADO=SI"),
    lambda t: t.replace("ARCHIVOS_REALES_ELIMINADOS=0",
                        "ARCHIVOS_REALES_ELIMINADOS=1"),
    lambda t: t.replace("TORRENTS_REALES_MODIFICADOS=0",
                        "TORRENTS_REALES_MODIFICADOS=1"),
    lambda t: t.replace("JELLYFIN_COMPARTE_SID_OPERADOR=SI\n", ""),
    lambda t: t + "\r\n",
    lambda t: t + "x" * 4000,
    lambda t: t + "\nNOMBRE=ñoño",
))
def test_fuentes_alteradas_no_autorizan(mutate):
    tampered = mutate(OK)
    with pytest.raises(SidsNoVerificables):
        parsear_auditoria_sids_0037(tampered)
    assert not evaluar_aislamiento_sids_0037(
        tampered, OK,
    )["permiso_de_borrado_otorgado"]


@pytest.mark.parametrize("raw", (None, {}, [], b"error", "", 42))
def test_fallo_sin_datos_no_autoriza(raw):
    with pytest.raises(SidsNoVerificables):
        parsear_auditoria_sids_0037(raw)
    assert "evidencia_sids_no_verificable" in evaluar_aislamiento_sids_0037(
        raw, OK,
    )["motivos"]
