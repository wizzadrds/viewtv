"""Fotografía read-only SQL + Jellyfin + qBittorrent para preflight 0018.

Ejecutar únicamente dentro de viewtv-api-1. Emite JSON privado al proceso
orquestador local (nunca a navegador, logs, GitHub ni STDOUT de usuario).
No abre archivos de películas ni ejecuta POST, DELETE, INSERT ni UPDATE.
"""
import json

from app.database import engine
from app.jellyfin import JellyfinClient, JellyfinError
from app.models import (
    Descarga,
    Medio,
    PeliculaVista,
    Perfil,
    Solicitud,
    SolicitudRetirada,
)
from app.qbittorrent import QBittorrentClient, QBittorrentError
from sqlmodel import Session, select


def collect_movies() -> list[dict]:
    with Session(engine) as session:
        active = {
            p.id for p in session.exec(
                select(Perfil).where(Perfil.activo.is_(True))
            ).all() if p.id is not None
        }
        media = session.exec(
            select(Medio).where(
                Medio.tipo == "pelicula",
                Medio.disponible_en_jellyfin.is_(True),
            )
        ).all()
        watched = session.exec(select(PeliculaVista)).all()
        pending = session.exec(
            select(SolicitudRetirada).where(
                SolicitudRetirada.estado == "pendiente_revision",
            )
        ).all()
        downloads = session.exec(
            select(Descarga).where(Descarga.organizacion_estado == "organizada")
        ).all()
        requests = {
            d.solicitud_id: session.get(Solicitud, d.solicitud_id)
            for d in downloads
        }
        result = {
            "perfiles_activos": sorted(active),
            "peliculas": [
                {
                    "medio_id": m.id,
                    "jellyfin_id": m.jellyfin_id,
                    "tmdb_id": m.tmdb_id,
                    "visto_perfiles": sorted(
                        p.perfil_id for p in watched
                        if p.medio_id == m.id and p.perfil_id in active
                    ),
                    "pendiente_perfiles": sorted(
                        p.perfil_id for p in pending
                        if p.medio_id == m.id and p.perfil_id in active
                    ),
                }
                for m in media
            ],
            "descargas": [
                {
                    "id": d.id,
                    "solicitud_id": d.solicitud_id,
                    "hash": d.qbittorrent_hash,
                    "estado": d.estado,
                    "estado_verificacion": d.estado_verificacion,
                    "progreso": d.progreso,
                    "verificada": d.verificada_en is not None,
                    "organizacion_estado": d.organizacion_estado,
                    "organizacion_bloqueada": d.organizacion_locked_by is not None,
                    "verificacion_bloqueada": d.verificacion_locked_by is not None,
                    "inicio_bloqueado": d.inicio_locked_by is not None,
                    "solicitud": (
                        {
                            "id": requests[d.solicitud_id].id,
                            "tipo_medio": requests[d.solicitud_id].tipo_medio,
                            "jellyfin_item_id": requests[d.solicitud_id].jellyfin_item_id,
                            "tmdb_id": requests[d.solicitud_id].tmdb_id,
                        }
                        if requests[d.solicitud_id] is not None else None
                    ),
                }
                for d in downloads
            ],
        }
    return result


def jellyfin_paths() -> dict:
    entries: list[dict] = []
    try:
        client = JellyfinClient()
        for offset in range(0, 10_000, 100):
            page = client._get("/Items", {
                "Recursive": "true",
                "IncludeItemTypes": "Movie",
                "Fields": "Path",
                "StartIndex": offset,
                "Limit": 100,
            })
            chunk = page.get("Items")
            total = page.get("TotalRecordCount")
            if (
                not isinstance(chunk, list)
                or not isinstance(total, int)
                or isinstance(total, bool)
                or not 0 <= total <= 10_000
                or not all(isinstance(item, dict) for item in chunk)
            ):
                raise ValueError("Paginación Jellyfin no verificable")
            entries.extend({
                "id": item.get("Id"),
                "tipo": item.get("Type"),
                "path": item.get("Path"),
            } for item in chunk)
            if len(entries) >= total:
                if len(entries) != total:
                    raise ValueError("Número Jellyfin inconsistente")
                return {"estado": "ok", "elementos": entries}
            if len(chunk) != 100:
                raise ValueError("Página Jellyfin incompleta")
    except (JellyfinError, ValueError, TypeError, KeyError):
        return {"estado": "consulta_fallida", "elementos": []}
    return {"estado": "limite", "elementos": []}


def torrents_lectura(descargas: list[dict]) -> dict:
    results: dict = {}
    client = QBittorrentClient()
    for download in descargas:
        key = str(download["id"])
        hash_ = download.get("hash")
        if not isinstance(hash_, str):
            results[key] = {"estado_consulta": "sin_hash"}
            continue
        try:
            torrents = client.torrents_info(hashes=[hash_])
            if (
                not isinstance(torrents, list)
                or len(torrents) != 1
                or not isinstance(torrents[0], dict)
            ):
                results[key] = {"estado_consulta": "no_unico"}
                continue
            torrent = torrents[0]
            if torrent.get("hash", "").casefold() != hash_.casefold():
                results[key] = {"estado_consulta": "identidad_invalida"}
                continue
            entries = client.torrent_files(hash_)
            results[key] = {
                "estado_consulta": "ok",
                "torrent": {
                    "hash": torrent.get("hash"),
                    "tags": torrent.get("tags"),
                    "save_path": torrent.get("save_path"),
                    "state": torrent.get("state"),
                    "progress": torrent.get("progress"),
                },
                "files": [{
                    "name": f.get("name"),
                    "size": f.get("size"),
                    "progress": f.get("progress"),
                    "priority": f.get("priority"),
                } for f in entries],
            }
        except (QBittorrentError, ValueError, TypeError, AttributeError):
            results[key] = {"estado_consulta": "error_consulta"}
    return results


def main() -> None:
    snapshot = collect_movies()
    snapshot["jellyfin"] = jellyfin_paths()
    snapshot["qbittorrent"] = torrents_lectura(snapshot["descargas"])
    print(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
