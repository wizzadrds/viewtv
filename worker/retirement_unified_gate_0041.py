"""0041: barrera de evidencias integrada SIN capacidad de borrar.

Contratos estrictos de 0018/0019/0026/0027/0033/0037/0040. La
repetición 0018 antes/después detecta algunos cambios, nunca congela
procesos, NTFS, red o sesiones ni convierte un informe en permiso.
Sin red, archivos, procesos ni información privada en las respuestas.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

SOURCES = (
    "0018_inicial", "0019", "0026", "0027", "0033",
    "0037", "0040", "0018_final",
)
REQUIRED: dict[str, dict[str, str | None]] = {
    "0018": {
        "PREFLIGHT_0018": "REALIZADO_SOLO_LECTURA",
        "PELICULAS_ANALIZADAS": None,
        "DIARIOS_NTFS_VERIFICADOS": None,
        "DIARIOS_VERIFICADOS_EN_SNAPSHOT": None,
        "PELICULAS_BLOQUEADAS": None,
        "PERMISO_DE_BORRADO_OTORGADO": "NO",
        "ARCHIVOS_ELIMINADOS": "0",
        "TORRENTS_MODIFICADOS": "0",
    },
    "0019": {
        "ADMIN_PREFLIGHT_0019": "SOLO_LECTURA",
        "PELICULAS_ANALIZADAS": None,
        "CANDIDATAS_SIN_OTROS_BLOQUEOS": None,
        "HAY_CLAVE_ADMINISTRATIVA_EN_API": "NO",
        "APROBACIONES_EMITIDAS": "0",
        "PERMISO_BORRADO_FISICO": "NO",
        "OPERACIONES_BORRADO_Y_QBIT": "0",
    },
    "0026": {
        "CUSTODIA_QBIT_0026": "SOLO_GET",
        "DOBLE_SNAPSHOT_SQL_JELLYFIN_QBIT": "COINCIDENTE",
        "DOBLE_EVIDENCIA_DIARIOS_Y_NTFS": "COINCIDENTE",
        "BYTES_LOGICOS_EXTRAS_NO_SON_ESPACIO_RECUPERABLE": "SI",
        "EXTRAS_CONSERVADOS": "SI",
        "QUIETUD_TRANSACCIONAL_QBIT_JELLYFIN": "NO",
        "PERMISO_BORRADO_FISICO": "NO",
        "ARCHIVOS_ELIMINADOS": "0",
        "TORRENTS_MODIFICADOS": "0",
    },
    "0027": {
        "SUPERFICIE_PLAYBACK_0027": "SOLO_LECTURA",
        "RUTAS_AUTENTICADAS_CONTADAS": None,
        "TTL_HLS_SEGUNDOS": None,
        "PUERTO_JELLYFIN_PUBLICADO_SOLO_LOOPBACK": "SI",
        "OTROS_ACCESOS_JELLYFIN_DESCARTADOS": "NO",
        "PROTOCOLO_ADMISION_0027_INSTALADO": "NO",
        "BLOQUEO_REAL_DE_NUEVOS_STREAMS": "NO",
        "PERMISO_BORRADO_FISICO": "NO",
        "SERVICIOS_MODIFICADOS": "0",
        "REPRODUCCIONES_MODIFICADAS": "0",
    },
    "0033": {
        "RETIRADA_ACCESOS_0033": "AUDITORIA_REAL_SOLO_LECTURA",
        "ESTADO_RETIRADA_0033": "BLOQUEADA",
        "PERMISO_DE_BORRADO_OTORGADO": "NO",
        "ARCHIVOS_ELIMINADOS": "0",
        "TORRENTS_MODIFICADOS": "0",
    },
    "0037": {
        "RETIRADA_SIDS_0037": "AUDITORIA_REAL_SOLO_LECTURA",
        "ESTADO_RETIRADA_0037": "BLOQUEADA",
        "PERMISO_DE_BORRADO_OTORGADO": "NO",
        "ARCHIVOS_REALES_ELIMINADOS": "0",
        "TORRENTS_REALES_MODIFICADOS": "0",
    },
    "0040": {
        "RETIRADA_WEBUI_QBIT_0040": "AUDITORIA_REAL_SOLO_LECTURA",
        "ESTADO_RETIRADA_0040": "BLOQUEADA",
        "PERMISO_DE_BORRADO_OTORGADO": "NO",
        "ARCHIVOS_ELIMINADOS": "0",
        "TORRENTS_MODIFICADOS": "0",
    },
}
QBIT_COUNTERS = frozenset({
    "DESCARGAS", "TORRENT_COMPLETO_Y_EN_REPOSO_REPORTADO",
    "TORRENT_NO_EN_REPOSO_O_INCOMPLETO",
    "TORRENT_PROPIEDAD_O_RUTA_INCONSISTENTE",
    "TORRENTS_CON_ARCHIVOS_EXTRA", "ARCHIVOS_QBIT",
    "ARCHIVOS_PUBLICADOS_CORRELACIONADOS", "ARCHIVOS_EXTRA_PROTEGIDOS",
    "EXTRAS_CON_NOMBRE_NO_NORMALIZABLE", "EXTRAS_TIPO_VIDEO",
    "EXTRAS_TIPO_SUBTITULO", "EXTRAS_TIPO_METADATO",
    "EXTRAS_TIPO_OTRO", "BYTES_LOGICOS_EXTRAS_PROTEGIDOS",
    "ARCHIVOS_CON_TAMANO_INCOMPATIBLE",
    "ARCHIVOS_CON_PROGRESO_INCOMPLETO",
    "ARCHIVOS_CON_PRIORIDAD_EXCLUIDA",
})
EXTRA: dict[str, set[str]] = {
    "0018": {"MOTIVO", "MEDIO"},
    "0019": {"BLOQUEO"},
    "0026": set(),
    "0027": set(),
    "0033": {"BARRERA"},
    "0037": {"BARRERA"},
    "0040": {"BARRERA"},
}
LINE = re.compile(r"([A-Z][A-Z0-9_]{0,79})=([A-Z0-9_]{1,85})\Z")
COUNT = re.compile(r"(?:0|[1-9][0-9]{0,7})\Z")
MEDIA = re.compile(r"MEDIO_([1-9][0-9]{0,8})\Z")
NUMBER_KEYS = {
    "PELICULAS_ANALIZADAS", "DIARIOS_NTFS_VERIFICADOS",
    "DIARIOS_VERIFICADOS_EN_SNAPSHOT", "PELICULAS_BLOQUEADAS",
    "CANDIDATAS_SIN_OTROS_BLOQUEOS", "RUTAS_AUTENTICADAS_CONTADAS",
    "TTL_HLS_SEGUNDOS",
}


class InterlockNoConfiable(ValueError):
    """Una fuente no cumple su contrato de solo lectura."""


def _count(value: str) -> int:
    if COUNT.fullmatch(value) is None:
        raise InterlockNoConfiable("Contador no canónico.")
    return int(value)


def parsear_fuente_0041(source: str, raw: object) -> dict[str, str]:
    """Admite sólo el informe reducido; rechaza secretos y campos nuevos."""
    if source not in REQUIRED or not isinstance(raw, str):
        raise InterlockNoConfiable("Fuente no reconocida.")
    if not 80 <= len(raw) <= 16384 or not raw.isascii():
        raise InterlockNoConfiable("Tamaño o codificación de informe inválidos.")
    if "\r" in raw or "\x00" in raw:
        raise InterlockNoConfiable("Contaminación de informe.")
    result: dict[str, str] = {}
    for line in raw.splitlines():
        match = LINE.fullmatch(line)
        if match is None:
            raise InterlockNoConfiable("Línea no canónica.")
        key, value = match.groups()
        prefix = key.split("_", 1)[0]
        allowed = (
            key in REQUIRED[source]
            or (source == "0026" and key in QBIT_COUNTERS)
            or (prefix in EXTRA[source] and len(key) > len(prefix) + 1)
        )
        if not allowed or key in result:
            raise InterlockNoConfiable("Campo no permitido o duplicado.")
        if source == "0018" and prefix == "MEDIO":
            if MEDIA.fullmatch(key) is None or value != "BLOQUEADA":
                raise InterlockNoConfiable("Película fuera de estado seguro.")
        elif (
            key in NUMBER_KEYS or key in QBIT_COUNTERS
            or (source == "0018" and prefix == "MOTIVO")
            or (source == "0019" and prefix == "BLOQUEO")
        ):
            _count(value)
        elif prefix == "BARRERA" and value != "PENDIENTE":
            raise InterlockNoConfiable("Barrera no declarada pendiente.")
        result[key] = value
    required = REQUIRED[source]
    if not set(required).issubset(result) or any(
        result[k] != v for k, v in required.items() if v is not None
    ):
        raise InterlockNoConfiable("Fuente incompleta o autorizadora.")
    if source == "0026" and not QBIT_COUNTERS.issubset(result):
        raise InterlockNoConfiable("Faltan contadores de archivos qBit.")
    if source in {"0033", "0037", "0040"} and not any(
        key.startswith("BARRERA_") for key in result
    ):
        raise InterlockNoConfiable("No se informaron barreras externas.")
    if source == "0018":
        analysed = _count(result["PELICULAS_ANALIZADAS"])
        blocked = _count(result["PELICULAS_BLOQUEADAS"])
        count_rows = sum(1 for k in result if k.startswith("MEDIO_"))
        if not analysed or analysed != blocked or analysed != count_rows:
            raise InterlockNoConfiable("No todas las películas están bloqueadas.")
        if _count(result["DIARIOS_NTFS_VERIFICADOS"]) > _count(
            result["DIARIOS_VERIFICADOS_EN_SNAPSHOT"]
        ):
            raise InterlockNoConfiable("Prueba NTFS mayor que diarios registrados.")
    if source == "0019" and _count(
        result["CANDIDATAS_SIN_OTROS_BLOQUEOS"]
    ) > _count(result["PELICULAS_ANALIZADAS"]):
        raise InterlockNoConfiable("Candidatas no verificables.")
    if source == "0026":
        if (
            _count(result["TORRENT_COMPLETO_Y_EN_REPOSO_REPORTADO"])
            + _count(result["TORRENT_NO_EN_REPOSO_O_INCOMPLETO"])
            != _count(result["DESCARGAS"])
        ):
            raise InterlockNoConfiable("Contadores torrent incompatibles.")
        if (
            _count(result["ARCHIVOS_PUBLICADOS_CORRELACIONADOS"])
            + _count(result["ARCHIVOS_EXTRA_PROTEGIDOS"])
            != _count(result["ARCHIVOS_QBIT"])
        ):
            raise InterlockNoConfiable("Archivos qBit desaparecidos.")
        if sum(_count(result[k]) for k in (
            "EXTRAS_TIPO_VIDEO", "EXTRAS_TIPO_SUBTITULO",
            "EXTRAS_TIPO_METADATO", "EXTRAS_TIPO_OTRO",
        )) != _count(result["ARCHIVOS_EXTRA_PROTEGIDOS"]):
            raise InterlockNoConfiable("Tipos de extras inconsistentes.")
    return result


def evaluar_interlock_0041(
    reports: object,
) -> dict[str, object]:
    """La auditoría jamás sustituye permiso administrativo ni lock kernel."""
    reasons = {
        "aislamiento_kernel_ntfs_no_instalado",
        "custodia_qbit_exclusiva_no_instalada",
        "hls_v2_y_drenaje_jellyfin_no_desplegados",
        "broker_windows_sid_aislado_no_instalado",
        "consumo_admin_de_pelicula_no_demostrado",
        "ejecutor_y_journal_de_borrado_no_desplegados",
    }
    parsed: dict[str, dict[str, str]] = {}
    if not isinstance(reports, Mapping) or set(reports) != set(SOURCES):
        reasons.add("inventario_de_fuentes_incompleto")
    else:
        for key in SOURCES:
            source = key.split("_", 1)[0]
            try:
                parsed[key] = parsear_fuente_0041(source, reports[key])
            except (InterlockNoConfiable, TypeError, KeyError):
                reasons.add("fuente_" + source + "_no_verificable")
        if (
            "0018_inicial" in parsed
            and "0018_final" in parsed
            and parsed["0018_inicial"] != parsed["0018_final"]
        ):
            reasons.add("preflight_0018_cambio_durante_auditoria")
        if (
            "0018_final" in parsed
            and "0019" in parsed
            and parsed["0018_final"]["PELICULAS_ANALIZADAS"]
            != parsed["0019"]["PELICULAS_ANALIZADAS"]
        ):
            reasons.add("recuento_de_peliculas_incoherente")
        if (
            "0018_final" in parsed
            and "0026" in parsed
            and _count(parsed["0018_final"]["DIARIOS_VERIFICADOS_EN_SNAPSHOT"])
            > _count(parsed["0026"]["ARCHIVOS_PUBLICADOS_CORRELACIONADOS"])
        ):
            reasons.add("diarios_ntfs_no_cubiertos_por_qbit")

    return {
        "estado": "bloqueada",
        "puede_retirar_archivos": False,
        "permiso_de_borrado_otorgado": False,
        "fuentes_verificadas": len(parsed),
        "fuentes_exigidas": len(SOURCES),
        "motivos": sorted(reasons),
    }
