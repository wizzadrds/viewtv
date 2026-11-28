"""0049: valida crash/replay NTFS TEMP del nonce de IPC simulado.

No acredita credenciales de pipe, qBit real ni permisos de retirada.
"""
from __future__ import annotations

EXPECTED_0049 = (
    "MUERTE_REAL_TRAS_INTENCION_DURABLE=PASS",
    "REPLAY_TRAS_REINICIO_DENEGADO=PASS",
    "NONCE_OTRO_HASH_RECHAZADO=PASS",
    "OTRO_NONCE_INDEPENDIENTE_Y_UNICO=PASS",
    "CUATRO_PROCESOS_UNICA_RESERVA=PASS",
    "BITACORA_CORRUPTA_FALLA_CERRADA=PASS",
    "SANDBOX_GUID_LIMPIADO=SI",
    "BROKER_PRODUCTIVO_INSTALADO=NO",
    "NONCE_PRODUCTIVO_DURABLE=NO",
    "QBIT_REAL_CONTACTADO=NO",
    "ARCHIVOS_REALES_ELIMINADOS=0",
    "TORRENTS_REALES_MODIFICADOS=0",
)


class EvidenciaNonceNoConfiable(ValueError):
    """Un ensayo TEMP nunca puede conceder permiso de borrado."""


def validar_nonce_0049(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, str) or not 200 <= len(raw) <= 1400:
        raise EvidenciaNonceNoConfiable("Informe de longitud/tipo inválidos.")
    if not raw.isascii() or "\x00" in raw:
        raise EvidenciaNonceNoConfiable("Evidencia contaminada.")
    normalized = raw.replace("\r\n", "\n")
    if "\r" in normalized or tuple(normalized.splitlines()) != EXPECTED_0049:
        raise EvidenciaNonceNoConfiable("Contrato nonce Windows no verificable.")
    return EXPECTED_0049


def evaluar_nonce_0049(first: object, second: object) -> dict[str, object]:
    """Dos ventanas de crash válidas tampoco habilitan un ejecutor real."""
    pending = {
        "ledger_nonce_solo_sandbox_desconectado_de_pipe",
        "broker_sin_sid_exclusivo_productivo",
        "qbit_gui_webui_siguen_fuera_del_broker",
        "jellyfin_ntfs_y_firma_admin_no_integrados",
    }
    valid = 0
    for i, report in enumerate((first, second), 1):
        try:
            validar_nonce_0049(report)
            valid += 1
        except EvidenciaNonceNoConfiable:
            pending.add(f"ensayo_{i}_no_verificable")
    if (
        valid == 2 and isinstance(first, str) and isinstance(second, str)
        and first.replace("\r\n", "\n") != second.replace("\r\n", "\n")
    ):
        pending.add("lecturas_contradictorias")
    return {
        "estado": "bloqueada",
        "auditorias_validas": valid,
        "auditorias_exigidas": 2,
        "nonce_durable_en_windows_sandbox": valid == 2,
        "nonce_durable_en_broker_real": False,
        "puede_borrar_archivos": False,
        "permiso_de_borrado_otorgado": False,
        "motivos": sorted(pending),
    }
