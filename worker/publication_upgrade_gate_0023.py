"""Barrera pura, sin acciones, para informes de actualización Windows 0023.

No emite tokens, rutas, PINs ni permisos de parada. Nunca autoriza instalar
ni eliminar medios. Niega si hay proceso, tarea habilitada, drift o fuente
ambigua. La sustitución requerirá aprobación administrativa fuera de la API.
"""
from __future__ import annotations

import re

YES_NO_KEYS = frozenset({
    "PUBLICADOR_INSTALADO_COINCIDE_CON_FUENTE_0022",
    "HELPER_MUTEX_0022_INSTALADO",
    "HELPER_INSTALADO_COINCIDE_CON_FUENTE_0022",
    "TAREA_PROGRAMADA_CON_USUARIO_LIMITADO",
    "ACCION_TAREA_ES_ESPERADA",
    "WRAPPER_TAREA_COINCIDE_CON_FUENTE",
    "TAREA_EN_EJECUCION",
    "SERVICIO_SCM_EXISTE",
    "SERVICIO_SCM_ACTIVO",
    "VERSION_LISTA_PARA_REVISION_DE_MUTEX",
    "PUEDE_AFIRMARSE_EXCLUSION_PRODUCTIVA",
    "REEMPLAZO_AUTOMATICO_DESDE_AUDITORIA",
})
INTEGER_KEYS = frozenset({
    "PROCESOS_PUBLICADOR_OBSERVADOS",
    "PROCESOS_POWERSHELL_SIN_LINEA_VISIBLE",
    "PROCESOS_DETENIDOS",
    "TAREAS_MODIFICADAS",
    "ARCHIVOS_MEDIA_MODIFICADOS",
    "TORRENTS_MODIFICADOS",
})
OTHER_KEYS = frozenset({"UPGRADE_0023", "ESTADO_TAREA"})
EXPECTED_KEYS = YES_NO_KEYS | INTEGER_KEYS | OTHER_KEYS
BOOLEAN = frozenset({"SI", "NO"})
STATES = frozenset({"READY", "DISABLED", "RUNNING", "QUEUED"})


class InformeNoConfiable(ValueError):
    """Denegar si un informe de Windows no cumple el contrato exacto."""


def evaluar_informe(text: str) -> dict:
    """Devuelve únicamente motivos agregados; nunca permiso de actualizar."""
    if not isinstance(text, str) or not 20 <= len(text) <= 4000:
        raise InformeNoConfiable("No existe un informe limitado.")
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line or len(line) > 130 or "=" not in line:
            raise InformeNoConfiable("Formato de campo no reconocible.")
        key, value = line.split("=", 1)
        if (
            key not in EXPECTED_KEYS
            or key in values
            or not re.fullmatch(r"[A-Z0-9_]{1,60}", value)
        ):
            raise InformeNoConfiable("Campo duplicado o ajeno.")
        values[key] = value
    if set(values) != EXPECTED_KEYS:
        raise InformeNoConfiable("Faltan campos de seguridad.")
    if values["UPGRADE_0023"] != "SOLO_LECTURA":
        raise InformeNoConfiable("No se confirmó lectura.")
    if values["ESTADO_TAREA"] not in STATES:
        raise InformeNoConfiable("Estado de tarea no reconocible.")
    if any(values[name] not in BOOLEAN for name in YES_NO_KEYS):
        raise InformeNoConfiable("Valor booleano no verificable.")
    if any(
        re.fullmatch(r"(?:0|[1-9][0-9]{0,4})", values[name]) is None
        for name in INTEGER_KEYS
    ):
        raise InformeNoConfiable("Conteo no verificable.")
    if any(values[k] != "0" for k in (
        "PROCESOS_DETENIDOS", "TAREAS_MODIFICADAS",
        "ARCHIVOS_MEDIA_MODIFICADOS", "TORRENTS_MODIFICADOS",
    )):
        raise InformeNoConfiable("Fuente modificó algo.")
    if any(values[k] != "NO" for k in (
        "PUEDE_AFIRMARSE_EXCLUSION_PRODUCTIVA",
        "REEMPLAZO_AUTOMATICO_DESDE_AUDITORIA",
    )):
        raise InformeNoConfiable("Fuente declara permiso de forma indebida.")
    if (
        values["HELPER_MUTEX_0022_INSTALADO"] == "NO"
        and values["HELPER_INSTALADO_COINCIDE_CON_FUENTE_0022"] == "SI"
    ):
        raise InformeNoConfiable("Helper inexistente no puede coincidir.")
    if (
        values["ESTADO_TAREA"] in ("RUNNING", "QUEUED")
    ) != (values["TAREA_EN_EJECUCION"] == "SI"):
        raise InformeNoConfiable("Tarea activa contradictoria.")

    reasons: list[str] = []
    if values["ESTADO_TAREA"] != "DISABLED":
        reasons.append("tarea_no_deshabilitada")
    if values["TAREA_PROGRAMADA_CON_USUARIO_LIMITADO"] != "SI":
        reasons.append("privilegios_tarea_no_confiables")
    if values["ACCION_TAREA_ES_ESPERADA"] != "SI":
        reasons.append("accion_tarea_diferente")
    if values["WRAPPER_TAREA_COINCIDE_CON_FUENTE"] != "SI":
        reasons.append("wrapper_tarea_diferente")
    if values["PUBLICADOR_INSTALADO_COINCIDE_CON_FUENTE_0022"] != "SI":
        reasons.append("publicador_instalado_desactualizado")
    if values["HELPER_MUTEX_0022_INSTALADO"] != "SI":
        reasons.append("biblioteca_mutex_no_instalada")
    elif values["HELPER_INSTALADO_COINCIDE_CON_FUENTE_0022"] != "SI":
        reasons.append("biblioteca_mutex_version_diferente")
    if values["SERVICIO_SCM_EXISTE"] == "SI":
        reasons.append("servicio_publicador_detectado")
    if values["SERVICIO_SCM_ACTIVO"] == "SI":
        reasons.append("servicio_publicador_activo")
    if values["PROCESOS_PUBLICADOR_OBSERVADOS"] != "0":
        reasons.append("procesos_publicador_observados")
    if values["PROCESOS_POWERSHELL_SIN_LINEA_VISIBLE"] != "0":
        reasons.append("procesos_no_inspeccionables")
    if values["VERSION_LISTA_PARA_REVISION_DE_MUTEX"] == "NO":
        reasons.append("instalacion_no_validada")

    return {
        "estado": "requiere_intervencion_supervisada",
        "bloqueos": sorted(set(reasons)),
        "comprobacion_solo_lectura": True,
        "permite_actualizar_automaticamente": False,
        "permite_eliminar_peliculas": False,
    }
