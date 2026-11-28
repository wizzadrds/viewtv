"""0048: validar el token del CLIENTE de una pipe Win32 ficticia.

Sin secretos, puertos, clientes qBit ni autorizaciones físicas. El reporte
constata identidad del cliente por RunAsClient, no via texto enviado.
"""
from __future__ import annotations

EXPECTED_0048 = (
    "SID_DEL_CLIENTE_OBTENIDO_POR_WIN32=PASS",
    "SID_EN_PAYLOAD_NO_ES_AUTORIDAD=PASS",
    "START_ALL_Y_HASH_AJENO_DENEGADOS=PASS",
    "NONCE_REUTILIZADO_DENEGADO=PASS",
    "SID_NO_VERIFICADO_DENEGADO=PASS",
    "SOLO_MOCK_START_SIN_EFECTOS=PASS",
    "REPLAY_DURABLE_TRAS_REINICIO_INSTALADO=NO",
    "BROKER_SID_DISTINTO_PRODUCTIVO=NO",
    "QBIT_REAL_CONTACTADO=NO",
    "ARCHIVOS_REALES_ELIMINADOS=0",
    "TORRENTS_REALES_MODIFICADOS=0",
)


class ProtocoloPipeNoConfiable(ValueError):
    """La fuente no prueba su contrato limitado de ensayo."""


def validar_protocolo_pipe_0048(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, str) or not 170 <= len(raw) <= 1200:
        raise ProtocoloPipeNoConfiable("Tamaño o tipo inválido.")
    if not raw.isascii() or "\x00" in raw:
        raise ProtocoloPipeNoConfiable("Informe no ASCII o contaminado.")
    body = raw.replace("\r\n", "\n")
    if "\r" in body:
        raise ProtocoloPipeNoConfiable("Retorno de carro no permitido.")
    lines = tuple(body.splitlines())
    if lines != EXPECTED_0048:
        raise ProtocoloPipeNoConfiable("Líneas incompletas o manipuladas.")
    return lines


def evaluar_protocolo_pipe_0048(
    anterior: object, posterior: object,
) -> dict[str, object]:
    """Las dos pruebas pueden pasar y el permiso sigue SIEMPRE denegado."""
    pending = {
        "sid_broker_real_no_separado",
        "qbit_gui_webui_fuera_del_canal",
        "nonces_sin_ledger_persistente_de_pipe",
        "ntfs_jellyfin_y_admin_fuera_del_ensayo",
    }
    valid = 0
    for index, report in enumerate((anterior, posterior), start=1):
        try:
            validar_protocolo_pipe_0048(report)
            valid += 1
        except ProtocoloPipeNoConfiable:
            pending.add(f"auditoria_{index}_no_verificable")
    if (
        valid == 2 and isinstance(anterior, str) and isinstance(posterior, str)
        and anterior.replace("\r\n", "\n") != posterior.replace("\r\n", "\n")
    ):
        pending.add("dos_informes_diferentes")
    return {
        "estado": "bloqueada",
        "auditorias_validas": valid,
        "auditorias_exigidas": 2,
        "comprobacion_peer_windows_sandbox": valid == 2,
        "sid_broker_productivo_verificado": False,
        "qbit_real_aislado": False,
        "puede_borrar_archivos": False,
        "permiso_de_borrado_otorgado": False,
        "motivos": sorted(pending),
    }
