"""Resumen de revisión por película a partir de fuentes independientes.

Una petición confirmada desde un perfil NO autoriza el retiro compartido.
Solo permite observar requisitos pendientes; ningún resultado emite permiso
ni altera una base de datos, torrent, original o hardlink.
"""
from __future__ import annotations

from typing import Any


class RevisionNoConfiable(ValueError):
    """Inconsistencia de un snapshot o identidad de la película."""


def _ids(values: Any) -> set[int]:
    if not isinstance(values, list) or any(
        type(i) is not int or i <= 0 for i in values
    ) or len(values) != len(set(values)):
        raise RevisionNoConfiable("Perfiles no verificables.")
    return set(values)


def resumir_revision(
    snapshot: dict,
    preflight: list[dict],
    detalle: dict,
) -> dict:
    """Falla cerrado ante cambios de estado entre SQLite y el preflight."""
    if not isinstance(snapshot, dict) or not isinstance(detalle, dict):
        raise RevisionNoConfiable("Datos no verificables.")
    if not isinstance(preflight, list) or detalle.get("estado") != "unica":
        raise RevisionNoConfiable("Película no identificada unívocamente.")
    media_id = detalle.get("medio_id")
    if type(media_id) is not int or media_id <= 0:
        raise RevisionNoConfiable("ID de medio no válido.")
    media = [
        item for item in snapshot.get("peliculas", [])
        if isinstance(item, dict) and item.get("medio_id") == media_id
    ]
    rows = [
        row for row in preflight
        if isinstance(row, dict) and row.get("medio_id") == media_id
    ]
    if len(media) != 1 or len(rows) != 1:
        raise RevisionNoConfiable("Película o preflight duplicado.")
    item, assessment = media[0], rows[0]
    if item.get("jellyfin_id") != detalle.get("jellyfin_id"):
        raise RevisionNoConfiable("Identidad Jellyfin no corresponde.")

    active = _ids(snapshot.get("perfiles_activos"))
    watched = _ids(item.get("visto_perfiles"))
    requests = _ids(item.get("pendiente_perfiles"))
    if not active or not watched.issubset(active) or not requests.issubset(active):
        raise RevisionNoConfiable("Perfil ajeno en snapshot.")
    if (
        active != _ids(detalle.get("perfiles_activos"))
        or watched != _ids(detalle.get("visto_perfiles"))
        or requests != _ids(detalle.get("pendiente_perfiles"))
    ):
        raise RevisionNoConfiable("Solicitud o marcas cambiaron entre consultas.")
    if type(detalle.get("solicitudes_canceladas")) is not int or (
        detalle["solicitudes_canceladas"] < 0
        or detalle["solicitudes_canceladas"] > len(active)
    ):
        raise RevisionNoConfiable("Solicitudes canceladas no verificables.")

    motives = assessment.get("motivos")
    if (
        assessment.get("estado") != "bloqueada"
        or assessment.get("puede_borrarse_ahora") is not False
        or not isinstance(motives, list)
        or any(not isinstance(r, str) or not r for r in motives)
        or len(motives) != len(set(motives))
        or "falta_autorizacion_administrador" not in motives
    ):
        raise RevisionNoConfiable("Preflight no conserva bloqueo administrativo.")
    if (watched != active) != ("hay_perfiles_sin_marcar_vista" in motives):
        raise RevisionNoConfiable("Bloqueo de vistas contradictorio.")
    valid_request = bool(requests and requests.issubset(watched))
    if (not valid_request) != ("sin_peticion_valida_de_retirada" in motives):
        raise RevisionNoConfiable("Bloqueo de solicitudes contradictorio.")

    return {
        "estado": "pendiente_revision_bloqueada" if valid_request else "sin_peticion_valida",
        "medio_id": media_id,
        "perfiles_activos": len(active),
        "perfiles_con_visto": len(watched),
        "perfiles_sin_visto": len(active - watched),
        "solicitudes_pendientes": len(requests),
        "solicitud_valida_registrada": valid_request,
        "vista_en_todos_los_perfiles": watched == active,
        "bloqueos": sorted(motives),
        "aprobacion_administrativa_emitida": False,
        "autoriza_borrado_fisico": False,
        "archivos_eliminados": 0,
        "torrents_modificados": 0,
    }
