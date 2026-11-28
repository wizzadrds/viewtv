"""0033: pruebas del parser de evidencias y denegación incondicional."""
from __future__ import annotations

import pytest
from worker.retirement_external_gate_0033 import (
    evaluar_accesos_externos_0033,
    parsear_accesos_0033,
)

VALID = "\n".join((
    "ACCESOS_EXTERNOS_0033=AUDITORIA_SOLO_LECTURA",
    "JELLYFIN_NATIVO_ESCUCHA_EXTERNA=SI",
    "JELLYFIN_FIREWALL_ALLOW=SI",
    "QBIT_ESCUCHA_EXTERNA=SI",
    "QBIT_FIREWALL_ALLOW=SI",
    "DOCKER_JELLYFIN_SOLO_LOCAL=SI",
    "NTFS_EXCLUSION_KERNEL=NO_VERIFICADA",
    "CUSTODIA_QBIT=NO_VERIFICADA",
    "DRENAJE_EXTERNO=NO_VERIFICADO",
    "PERMISO_DE_BORRADO_OTORGADO=NO",
    "ARCHIVOS_ELIMINADOS=0",
    "TORRENTS_MODIFICADOS=0",
))


def test_observacion_con_rutas_abiertas_bloquea_borrado():
    verdict = evaluar_accesos_externos_0033(VALID, VALID)
    assert verdict["estado"] == "bloqueada"
    assert verdict["permiso_de_borrado_otorgado"] is False
    assert "jellyfin_nativo_expuesto" in verdict["motivos"]
    assert "firewall_qbittorrent_permisivo" in verdict["motivos"]


def test_sin_listeners_aparentes_tampoco_autoriza_borrar():
    closed = (
        VALID.replace("EXTERNA=SI", "EXTERNA=NO")
        .replace("ALLOW=SI", "ALLOW=NO")
    )
    verdict = evaluar_accesos_externos_0033(closed, closed)
    assert not verdict["permiso_de_borrado_otorgado"]
    assert "ntfs_exclusion_kernel_pendiente" in verdict["motivos"]
    assert "custodia_qbittorrent_pendiente" in verdict["motivos"]


def test_evidencia_cambia_entre_observaciones_y_bloquea():
    changed = VALID.replace(
        "JELLYFIN_FIREWALL_ALLOW=SI", "JELLYFIN_FIREWALL_ALLOW=NO",
    )
    verdict = evaluar_accesos_externos_0033(VALID, changed)
    assert "evidencias_cambiantes" in verdict["motivos"]


def test_auditoria_incompleta_bloquea():
    unavailable = (
        VALID.replace("AUDITORIA_SOLO_LECTURA", "INCOMPLETO")
        .replace("EXTERNA=SI", "EXTERNA=DESCONOCIDO")
        .replace("ALLOW=SI", "ALLOW=DESCONOCIDO")
        .replace("SOLO_LOCAL=SI", "SOLO_LOCAL=DESCONOCIDO")
        + "\nCAUSA=EVIDENCIA_NO_DISPONIBLE"
    )
    assert parsear_accesos_0033(unavailable)[
        "ACCESOS_EXTERNOS_0033"
    ] == "INCOMPLETO"
    verdict = evaluar_accesos_externos_0033(unavailable, unavailable)
    assert "fuente_externa_incompleta" in verdict["motivos"]
    assert not verdict["permiso_de_borrado_otorgado"]


@pytest.mark.parametrize("corrupt", (
    lambda t: t + "\nJELLYFIN_FIREWALL_ALLOW=NO",
    lambda t: t + "\nCLAVE_JELLYFIN=secreto",
    lambda t: t.replace("NO_VERIFICADO", "SI"),
    lambda t: t.replace("ARCHIVOS_ELIMINADOS=0", "ARCHIVOS_ELIMINADOS=1"),
    lambda t: t.replace(
        "PERMISO_DE_BORRADO_OTORGADO=NO",
        "PERMISO_DE_BORRADO_OTORGADO=SI",
    ),
    lambda t: t.replace("QBIT_FIREWALL_ALLOW=SI", "QBIT_FIREWALL_ALLOW=SIN_DATO"),
    lambda t: t.replace("DOCKER_JELLYFIN_SOLO_LOCAL=SI\n", ""),
    lambda t: t + "\r\n",
    lambda t: t + "\nRUTA=C:\\VIEWTV\\media",
    lambda t: t + "x" * 5000,
    lambda t: t.replace("AUDITORIA_SOLO_LECTURA", "APROBADO"),
    lambda t: t.replace("JELLYFIN_FIREWALL_ALLOW=SI",
                        "JELLYFIN_FIREWALL_ALLOW=SI "),
))
def test_evidencia_corrupta_falla_cerrada(corrupt):
    changed = corrupt(VALID)
    with pytest.raises(ValueError):
        parsear_accesos_0033(changed)
    verdict = evaluar_accesos_externos_0033(changed, changed)
    assert "evidencia_externa_no_verificable" in verdict["motivos"]
    assert not verdict["permiso_de_borrado_otorgado"]


def test_bytes_none_objetos_y_vacio_fallan_cerrados():
    for candidate in (None, b"invalid", {}, [], ""):
        with pytest.raises(ValueError):
            parsear_accesos_0033(candidate)
        assert not evaluar_accesos_externos_0033(
            candidate, VALID,
        )["permiso_de_borrado_otorgado"]
