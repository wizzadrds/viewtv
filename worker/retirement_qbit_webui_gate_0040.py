"""0040: gate de evidencia WebUI/GUI qBit, SIEMPRE DENEGATORIO.

No accede a contraseñas, redes, archivos ni al cliente real. Evalúa dos
auditorías Windows en formato cerrado sin rutas o identificadores. Incluso
WebUI con contraseña + API key puede ser una vía externa a la custodia
SQLite de VIEWTV 0038/0039; jamás se infiere exclusividad de credenciales.
"""
from __future__ import annotations

from typing import Final

STATUS: Final = "QBIT_WEBUI_0040"
YES_NO: Final = frozenset({
    "QBIT_INSTANCIA_NATIVA_UNICA",
    "QBIT_PROCESO_SID_OPERADOR",
    "WEBUI_HABILITADA_CONFIG_OPERADOR",
    "WEBUI_APIKEY_EN_CONFIG",
    "WEBUI_PASSWORD_HASH_EN_CONFIG",
    "QBIT_LISTENER_EXTERNO",
    "QBIT_FIREWALL_ALLOW_AMPLIA",
    "WEBUI_CONEXION_REMOTA_OBSERVADA",
})
FIXED: Final = {
    "WEBUI_CONFIG_VINCULADA_A_PROCESO": "NO_VERIFICADA",
    "BROKER_SECRETO_EXCLUSIVO": "NO_VERIFICADO",
    "GUI_BLOQUEADA_PARA_REANUDAR": "NO_VERIFICADA",
    "FILE_ID_SIN_ESCRITORES": "NO_VERIFICADO",
    "PERMISO_DE_BORRADO_OTORGADO": "NO",
    "ARCHIVOS_ELIMINADOS": "0",
    "TORRENTS_MODIFICADOS": "0",
}
INCOMPLETE: Final = {
    STATUS: "INCOMPLETA",
    "BROKER_SECRETO_EXCLUSIVO": "NO_VERIFICADO",
    "GUI_BLOQUEADA_PARA_REANUDAR": "NO_VERIFICADA",
    "FILE_ID_SIN_ESCRITORES": "NO_VERIFICADO",
    "PERMISO_DE_BORRADO_OTORGADO": "NO",
    "ARCHIVOS_ELIMINADOS": "0",
    "TORRENTS_MODIFICADOS": "0",
    "CAUSA": "EVIDENCIA_NO_DISPONIBLE",
}
ALL_FIELDS: Final = YES_NO | set(FIXED) | {STATUS}


class WebUiQbit0040NoVerificable(ValueError):
    """El informe no puede respaldar una decisión de custodia."""


def parsear_webui_qbit_0040(raw: object) -> dict[str, str]:
    """Contrato canónico, sin SIDs, claves, hashes, URLs, puertos ni rutas."""
    if not isinstance(raw, str) or not 90 <= len(raw) <= 2048:
        raise WebUiQbit0040NoVerificable("Informe ausente o demasiado grande.")
    if not raw.isascii() or "\r" in raw or "\x00" in raw:
        raise WebUiQbit0040NoVerificable("Informe contiene datos no públicos.")
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if not line or line.count("=") != 1:
            raise WebUiQbit0040NoVerificable("Formato de línea inválido.")
        key, value = line.split("=", 1)
        if (
            not key or not value or len(key) > 64 or len(value) > 64
            or key in values or value.strip() != value
            or not key.isupper()
        ):
            raise WebUiQbit0040NoVerificable("Campo duplicado o mal formado.")
        values[key] = value

    if values.get(STATUS) == "INCOMPLETA":
        if values != INCOMPLETE:
            raise WebUiQbit0040NoVerificable("Fallo cerrado inconsistente.")
        return values
    if values.get(STATUS) != "OBSERVACION_SOLO_LECTURA":
        raise WebUiQbit0040NoVerificable("Origen no verificable.")
    if set(values) != ALL_FIELDS:
        raise WebUiQbit0040NoVerificable("Faltan datos o sobran campos.")
    if any(values[k] not in {"SI", "NO"} for k in YES_NO):
        raise WebUiQbit0040NoVerificable("Indicador booleano incorrecto.")
    if values["QBIT_INSTANCIA_NATIVA_UNICA"] != "SI":
        raise WebUiQbit0040NoVerificable("Identidad de instancia no única.")
    if any(values[k] != v for k, v in FIXED.items()):
        raise WebUiQbit0040NoVerificable("El informe intenta autorizar retirada.")
    return values


def evaluar_webui_qbit_0040(
    primera: object,
    segunda: object,
) -> dict[str, object]:
    """Dos observaciones Windows no prueban barrera de GUI, API o NTFS."""
    reasons: set[str] = {
        "broker_sin_credencial_webui_exclusiva_verificada",
        "gui_o_clientes_externos_sin_barrera_compartida",
        "reanudacion_qbit_fuera_de_viewtv_no_excluida",
        "permisos_ntfs_file_id_sin_exclusion",
        "administrador_y_retirada_no_evaluados",
    }
    try:
        before = parsear_webui_qbit_0040(primera)
        after = parsear_webui_qbit_0040(segunda)
        if before != after:
            reasons.add("evidencia_webui_inestable")
        if after[STATUS] != "OBSERVACION_SOLO_LECTURA":
            reasons.add("auditoria_host_incompleta")
        else:
            for flag, issue in (
                ("QBIT_PROCESO_SID_OPERADOR", "gui_qbit_en_sid_operador"),
                ("WEBUI_HABILITADA_CONFIG_OPERADOR", "webui_habilitada_en_config"),
                ("QBIT_LISTENER_EXTERNO", "qbit_puerto_no_local"),
                ("QBIT_FIREWALL_ALLOW_AMPLIA", "firewall_qbit_allow_amplio"),
                (
                    "WEBUI_CONEXION_REMOTA_OBSERVADA",
                    "sesion_webui_remota_detectada",
                ),
            ):
                if after[flag] == "SI":
                    reasons.add(issue)
            if after["WEBUI_APIKEY_EN_CONFIG"] == "SI":
                reasons.add("api_key_configurada_no_equivale_a_exclusividad")
            if after["WEBUI_PASSWORD_HASH_EN_CONFIG"] == "SI":
                reasons.add("password_configurada_no_equivale_a_exclusividad")
    except (WebUiQbit0040NoVerificable, TypeError, KeyError):
        reasons.add("evidencia_webui_no_verificable")

    return {
        "estado": "bloqueada",
        "custodia_exclusiva_qbit_verificada": False,
        "permiso_de_borrado_otorgado": False,
        "puede_desplegar_borrado": False,
        "motivos": sorted(reasons),
    }
