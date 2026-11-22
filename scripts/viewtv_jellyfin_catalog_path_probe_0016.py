"""Compara IDs y rutas de catálogo con Jellyfin sin revelar contenido."""
import re

from sqlmodel import Session, select

from app.database import engine
from app.jellyfin import JellyfinClient, JellyfinError
from app.models import Medio

with Session(engine) as db:
    movies = db.exec(select(Medio).where(
        Medio.tipo == "pelicula", Medio.disponible_en_jellyfin.is_(True),
    )).all()
print("CATALOGO_VIEWTV_PELICULAS=" + str(len(movies)))
print("CATALOGO_VIEWTV_ID_UUID_32_HEX=" + str(sum(
    bool(re.fullmatch(r"[0-9a-fA-F]{32}", m.jellyfin_id)) for m in movies
)))
try:
    data = JellyfinClient()._get(
        "/Items", {
            "Recursive": "true",
            "IncludeItemTypes": "Movie",
            "Fields": "Path",
            "StartIndex": 0,
            "Limit": 100,
        },
    )
    entries = data.get("Items", [])
    print("JELLYFIN_ITEMS_CONSULTA=OK")
    print("JELLYFIN_PELICULAS_LEIDAS=" + str(len(entries)))
    print("JELLYFIN_RUTA_PRESENTE=" + str(sum(
        isinstance(row.get("Path"), str) for row in entries
    )))
    ids = {row.get("Id") for row in entries}
    print("ID_MATCH_VIEWTV_JELLYFIN=" + str(sum(
        m.jellyfin_id in ids for m in movies
    )))
except (JellyfinError, ValueError):
    print("JELLYFIN_ITEMS_CONSULTA=FALLIDA")
