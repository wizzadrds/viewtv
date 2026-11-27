"""Barrera de reproducciones Jellyfin, pura y SIN autoridad destructiva.

Un informe de /Sessions no congela streams: incluso con cero sesiones se
necesitan bloqueo Windows, qBit y aprobación administrativa. Devuelve siempre
habilita_borrado=False y no exporta nombres, usuarios, rutas ni IDs.
"""
from __future__ import annotations

from collections import Counter

MAX_SESIONES = 200
MAX_PELICULAS = 1000


class SesionesNoConfiables(ValueError):
    """Denegar ante dato incompleto o protocolo fuera de contrato."""


def _id(value: object) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 128
        and value.isascii()
        and all(ch.isalnum() or ch in "-_" for ch in value)
    )


def evaluar_sesiones(sessions: object, media_ids: object) -> dict:
    """Los usuarios de Jellyfin ajenos a VIEWTV también cuentan.

    Sesión activa = NowPlayingItem no nulo, incluso si está en pausa.
    Sesión con ítem inválido / stream sin ítem => se bloquea todo.
    Una película diferente no bloquea a otra si la identidad es válida.
    """
    if (
        not isinstance(sessions, list)
        or len(sessions) > MAX_SESIONES
        or not isinstance(media_ids, list)
        or not 1 <= len(media_ids) <= MAX_PELICULAS
        or any(not _id(value) for value in media_ids)
        or len(set(media_ids)) != len(media_ids)
    ):
        raise SesionesNoConfiables("Inventario o identidad no verificable.")
    target = set(media_ids)
    active: Counter[str] = Counter()
    ambiguity = 0
    unrelated = 0
    session_ids: set[str] = set()
    for s in sessions:
        if not isinstance(s, dict):
            raise SesionesNoConfiables("Sesión no verificable.")
        session_id = s.get("Id")
        if not _id(session_id) or session_id in session_ids:
            raise SesionesNoConfiables("Sesión sin identidad única.")
        session_ids.add(session_id)
        item = s.get("NowPlayingItem")
        if item is None:
            if s.get("TranscodingInfo") is not None:
                ambiguity += 1
            continue
        if not isinstance(item, dict) or not _id(item.get("Id")):
            ambiguity += 1
            continue
        if item.get("Id") in target:
            active[item["Id"]] += 1
        else:
            unrelated += 1

    blocked = sum(1 for item_id in media_ids if active[item_id] > 0 or ambiguity > 0)
    return {
        "estado": "bloqueada" if blocked else "sin_reproduccion_reportada",
        "peliculas_comprobadas": len(media_ids),
        "peliculas_bloqueadas": blocked,
        "sesiones_jellyfin": len(sessions),
        "sesiones_pelicula_objetivo": sum(active.values()),
        "sesiones_otras_peliculas": unrelated,
        "sesiones_ambiguas": ambiguity,
        "habilita_borrado_fisico": False,
        "aviso": "Lectura instantanea sin bloqueo de reproductores.",
    }


def instantanea_sesiones(sessions: object) -> tuple:
    """Fingerprint para detectar cambios entre dos lecturas GET.

    Nunca devuelve rutas, nombre del usuario o título del contenido.
    """
    if not isinstance(sessions, list) or len(sessions) > MAX_SESIONES:
        raise SesionesNoConfiables("Número de sesiones incorrecto.")
    normalized: list[tuple[str, str, bool]] = []
    seen: set[str] = set()
    for session in sessions:
        if not isinstance(session, dict) or not _id(session.get("Id")):
            raise SesionesNoConfiables("Sesión sin identidad.")
        identifier = session["Id"]
        if identifier in seen:
            raise SesionesNoConfiables("ID de sesión duplicado.")
        seen.add(identifier)
        item = session.get("NowPlayingItem")
        item_id = ""
        if item is not None:
            if not isinstance(item, dict) or not _id(item.get("Id")):
                item_id = "AMBIGUO"
            else:
                item_id = item["Id"]
        transcoding = session.get("TranscodingInfo") is not None
        normalized.append((identifier, item_id, transcoding))
    return tuple(sorted(normalized))
