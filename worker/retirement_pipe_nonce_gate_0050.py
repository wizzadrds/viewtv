"""0050: verifica la unión Win32 peer kernel + nonce durable SOLO TEMP.

Nunca autoriza medios ni acredita un broker con SID independiente.
"""
from __future__ import annotations

EXPECTED_0050 = (
    "SID_PEER_Y_COMMIT_ANTES_DE_CRASH=PASS",
    "REPLAY_EN_NUEVA_PIPE_DENEGADO=PASS",
    "SID_FALSO_EN_MENSAJE_DENEGADO=PASS",
    "HASH_AJENO_DENEGADO=PASS",
    "IDENTIDAD_NO_VERIFICADA_DENEGADA=PASS",
    "NONCE_NUEVO_ACEPTADO_SOLO_MOCK=PASS",
    "CUATRO_PIPE_CLIENTS_UNICA_RESERVA=PASS",
    "JOURNAL_MANIPULADO_FALLA_CERRADA=PASS",
    "SANDBOX_GUID_LIMPIADO=SI",
    "BROKER_PRODUCTIVO_INSTALADO=NO",
    "QBIT_REAL_CONTACTADO=NO",
    "ARCHIVOS_REALES_ELIMINADOS=0",
    "TORRENTS_REALES_MODIFICADOS=0",
)


class PeerNonceNoConfiable(ValueError):
    """Informe incompleto, manipulado o incorrecto."""


def validar_peer_nonce_0050(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, str) or not 230 <= len(raw) <= 1400:
        raise PeerNonceNoConfiable("Tamaño o tipo de reporte no verificable.")
    if not raw.isascii() or "\x00" in raw or "\ufeff" in raw:
        raise PeerNonceNoConfiable("Reporte no ASCII o contaminado.")
    canonical = raw.replace("\r\n", "\n")
    if "\r" in canonical or tuple(canonical.splitlines()) != EXPECTED_0050:
        raise PeerNonceNoConfiable("Contrato de seguridad no satisfecho.")
    return EXPECTED_0050


def evaluar_peer_nonce_0050(first: object, second: object) -> dict[str, object]:
    pending = {
        "sid_broker_real_no_independiente",
        "webui_gui_qbit_y_jellyfin_sin_aislamiento",
        "ntfs_kernel_y_admin_por_pelicula_no_integrados",
        "journal_solo_temp_y_sin_prueba_de_apagon",
        "pipe_sandbox_no_es_ejecutor_productivo",
    }
    validated = 0
    for idx, source in enumerate((first, second), 1):
        try:
            validar_peer_nonce_0050(source)
            validated += 1
        except PeerNonceNoConfiable:
            pending.add(f"auditoria_{idx}_no_verificable")
    if (
        validated == 2 and isinstance(first, str)
        and isinstance(second, str)
        and first.replace("\r\n", "\n") != second.replace("\r\n", "\n")
    ):
        pending.add("dos_informes_contradictorios")
    return {
        "estado": "bloqueada",
        "auditorias_validas": validated,
        "auditorias_exigidas": 2,
        "win32_peer_y_nonce_en_mismo_ensayo": validated == 2,
        "sid_broker_productivo_instalado": False,
        "autoriza_borrado_fisico": False,
        "puede_iniciar_unlink": False,
        "motivos": sorted(pending),
    }
