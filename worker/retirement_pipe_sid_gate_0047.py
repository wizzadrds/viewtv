"""0047: contrato estricto de un pipe Win32 ficticio; NUNCA permiso de borrar.

No inicia procesos, no usa qBit ni conoce credenciales, hashes o SIDs.
El testigo solo demuestra que UNA pipe temporal aplica su DACL al token.
"""
from __future__ import annotations

EXPECTED_0047 = (
    "PIPE_ACL_UNICAMENTE_SID_DESIGNADO=PASS",
    "TOKEN_RESTRINGIDO_NO_CONECTA=PASS",
    "ORDEN_START_ALL_RECHAZADA_POR_POLICY=PASS",
    "SID_PERMITIDO_SOLO_HASH_SINTETICO=PASS",
    "GUI_WEBUI_QBIT_PRODUCCION_AISLADA=NO",
    "BROKER_PRODUCTIVO_INSTALADO=NO",
    "CUENTAS_LOCALES_CREADAS=0",
    "ACL_PRODUCTIVAS_MODIFICADAS=0",
    "POST_QBIT_REAL=0",
    "ARCHIVOS_REALES_ELIMINADOS=0",
)


class EvidenciaPipeNoConfiable(ValueError):
    """El testigo Windows no acredita ni siquiera el ensayo."""


def validar_pipe_0047(raw: object) -> tuple[str, ...]:
    """Acepta exclusivamente los diez resultados del ensayo Windows."""
    if not isinstance(raw, str):
        raise EvidenciaPipeNoConfiable("Respuesta no textual.")
    if not 150 <= len(raw) <= 1000 or not raw.isascii():
        raise EvidenciaPipeNoConfiable("Informe ilegible o demasiado grande.")
    if "\x00" in raw or "\ufeff" in raw:
        raise EvidenciaPipeNoConfiable("Contaminación del informe.")
    # Windows PowerShell usa CRLF. Prohibir cualquier CR adicional.
    normalized = raw.replace("\r\n", "\n")
    if "\r" in normalized:
        raise EvidenciaPipeNoConfiable("Retorno de carro inesperado.")
    actual = tuple(normalized.splitlines())
    if actual != EXPECTED_0047:
        raise EvidenciaPipeNoConfiable(
            "Prueba de aislamiento incompleta, engañosa o alterada."
        )
    return actual


def evaluar_pipe_0047(
    primero: object,
    segundo: object,
) -> dict[str, object]:
    """Aunque 2/2 sean correctos, el acceso productivo sigue sin aislar."""
    reasons = {
        "qbit_webui_gui_real_no_aisladas",
        "identidad_broker_productiva_no_instalada",
        "ntfs_y_jellyfin_fuera_de_la_pipe",
        "administrador_y_pelicula_no_autorizados",
    }
    valid = 0
    for index, raw in enumerate((primero, segundo), start=1):
        try:
            validar_pipe_0047(raw)
            valid += 1
        except EvidenciaPipeNoConfiable:
            reasons.add(f"auditoria_pipe_{index}_no_verificable")
    if (
        valid == 2
        and isinstance(primero, str)
        and isinstance(segundo, str)
        and primero.replace("\r\n", "\n")
        != segundo.replace("\r\n", "\n")
    ):
        reasons.add("dos_auditorias_incompatibles")
    return {
        "estado": "bloqueada",
        "auditorias_validas": valid,
        "auditorias_exigidas": 2,
        "pipe_sandbox_solo_sid_verificada": valid == 2,
        "broker_productivo_aislado": False,
        "puede_borrar_archivos": False,
        "autoriza_borrado_fisico": False,
        "motivos": sorted(reasons),
    }
