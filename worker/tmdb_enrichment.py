"""Enriquecimiento conservador del catálogo mediante TMDB."""

import logging
import re
import unicodedata
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.config import get_settings
from app.database import engine
from app.models import Medio
from app.tmdb import TMDBClient, TMDBError

logger = logging.getLogger("viewtv.worker.tmdb")
BATCH_SIZE = 5
RETRY_DELAY = timedelta(hours=24)


def normalize_title(value: str) -> str:
    """Normaliza títulos para comparar coincidencias exactas."""
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", value)


def result_year(item: dict, media_type: str) -> int | None:
    field = "release_date" if media_type == "pelicula" else "first_air_date"
    value = item.get(field)
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


def enrich_pending_media() -> None:
    """Enriquece un máximo de cinco películas o series por ejecución."""
    settings = get_settings()
    if not settings.tmdb_api_key:
        logger.info("TMDB no está configurado; se omite el enriquecimiento.")
        return

    now = datetime.now(UTC)
    retry_before = now - RETRY_DELAY

    with Session(engine) as session:
        statement = (
            select(Medio)
            .where(
                Medio.disponible_en_jellyfin.is_(True),
                Medio.tipo.in_(["pelicula", "serie"]),
                Medio.tmdb_id.is_(None),
                Medio.tmdb_estado.in_(["pendiente", "error"]),
            )
            .where(
                (Medio.tmdb_intentado_en.is_(None))
                | (Medio.tmdb_intentado_en <= retry_before)
            )
            .order_by(Medio.id)
            .limit(BATCH_SIZE)
        )
        media_items = session.exec(statement).all()

        if not media_items:
            return

        try:
            client = TMDBClient()
        except TMDBError:
            logger.warning("No se pudo iniciar el cliente TMDB.")
            return

        for media in media_items:
            media.tmdb_intentado_en = now
            try:
                results = client.search(media.tipo, media.titulo, media.anio)
                title = normalize_title(media.titulo)
                matches = [
                    item for item in results
                    if normalize_title(
                        str(item.get("title") or item.get("name") or "")
                    ) == title
                    and (
                        media.anio is None
                        or result_year(item, media.tipo) == media.anio
                    )
                ]

                if not matches:
                    media.tmdb_estado = "sin_resultado"
                    session.add(media)
                    session.commit()
                    continue

                if len(matches) != 1 or media.anio is None:
                    media.tmdb_estado = "revisar"
                    session.add(media)
                    session.commit()
                    continue

                tmdb_id = matches[0].get("id")
                if not isinstance(tmdb_id, int) or tmdb_id <= 0:
                    media.tmdb_estado = "error"
                      session.add(media)
                      session.commit()
                    continue

                details = client.details(media.tipo, tmdb_id)
                media.tmdb_id = tmdb_id
                media.tmdb_sinopsis = details.get("overview") or None
                media.tmdb_anio = result_year(details, media.tipo)
                media.tmdb_generos = [
                    genre["name"]
                    for genre in details.get("genres", [])
                    if isinstance(genre, dict) and isinstance(genre.get("name"), str)
                ]
                media.tmdb_imagen_portada = client.image_url(
                    details.get("poster_path"), "w500"
                )
                media.tmdb_imagen_fondo = client.image_url(
                    details.get("backdrop_path"), "w1280"
                )
                media.tmdb_estado = "asociado"

            except TMDBError:
                media.tmdb_estado = "error"
                logger.warning("Error TMDB al enriquecer medio %s.", media.id)

            session.add(media)
            session.commit()

        logger.info("Lote TMDB procesado: %s medios.", len(media_items))
