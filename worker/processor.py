"""Procesamiento de búsquedas de la cola durable."""

import hashlib
import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from sqlmodel import Session

from app.database import engine
from app.jackett import JackettClient, JackettError
from app.models import ResultadoBusqueda
from app.relevancia_resultado import coincide_con_solicitud
from app.queue import claim_next_request, fail_request, finish_search_request

logger = logging.getLogger("viewtv.worker.processor")


def _search_type(media_type: str | None) -> str:
    if media_type == "pelicula":
        return "movie"
    if media_type in {"serie", "temporada", "episodio"}:
        return "tvsearch"
    return "search"


def _result_key(
    info_hash: str | None,
    magnet_url: str | None,
    download_url: str | None,
) -> str:
    if info_hash:
        identity = f"hash:{info_hash.strip().lower()}"
    elif magnet_url:
        identity = f"magnet:{magnet_url.strip()}"
    else:
        identity = f"url:{download_url.strip()}"

    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _published_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)

def _nonnegative(value: int | None) -> int | None:
    return value if value is not None and value >= 0 else None

def _to_database_results(
    request_id: int,
    jackett_results: list,
) -> list[ResultadoBusqueda]:
    converted: dict[str, ResultadoBusqueda] = {}

    for item in jackett_results:
        download_url = item.download_url.strip() if item.download_url else None
        magnet_url = item.magnet_url.strip() if item.magnet_url else None

        # El modelo exige al menos una URL utilizable.
        if not download_url and not magnet_url:
            continue

        key = _result_key(item.info_hash, magnet_url, download_url)

        if key in converted:
            continue

        converted[key] = ResultadoBusqueda(
            solicitud_id=request_id,
            clave=key,
            info_hash=item.info_hash.strip() if item.info_hash else None,
            titulo=item.title.strip()[:500],
            indexador=(item.indexer or "desconocido")[:128],
            download_url=download_url,
            magnet_url=magnet_url,
            seeders=_nonnegative(item.seeders),
            peers=_nonnegative(item.peers),
            tamano_bytes=_nonnegative(item.size_bytes),
            categorias=list(item.categories),
            publicado_en=_published_datetime(item.published_at),
        )

    return list(converted.values())


def process_one_request(
    worker_id: str,
    client: JackettClient | None = None,
) -> bool:
    """Procesa una solicitud; devuelve False si no había trabajo disponible."""
    with Session(engine) as session:
        request = claim_next_request(session, worker_id)

        if request is None:
            return False

        # Copiamos los datos antes de cerrar la sesión.
        request_id = request.id
        title = request.titulo
        year = request.anio
        media_type = request.tipo_medio

    if request_id is None:
        return True

    query = f"{title} {year}" if year else title

    try:
        jackett = client or JackettClient()
        found = jackett.search(
            query,
            search_type=_search_type(media_type),
        )
        results = [
            item for item in _to_database_results(request_id, found)
            if coincide_con_solicitud(title, media_type, year, item.titulo)
        ]

        with Session(engine) as session:
            saved = finish_search_request(
                session,
                request_id,
                worker_id,
                results,
            )

        if saved:
            logger.info(
                "Solicitud %s procesada: %s resultados seleccionables",
                request_id,
                len(results),
            )
        else:
            logger.warning(
                "Se perdió el lease de la solicitud %s antes de guardar resultados",
                request_id,
            )

    except Exception as error:
        logger.exception("Error procesando la solicitud %s", request_id)

        # JackettError proporciona mensajes saneados. Para otros errores
        # evitamos guardar detalles internos o posibles datos sensibles.
        error_message = (
            str(error)
            if isinstance(error, JackettError)
            else f"Error interno: {error.__class__.__name__}"
        )

        try:
            with Session(engine) as session:
                failed = fail_request(
                    session,
                    request_id,
                    worker_id,
                    error_message,
                )
            if not failed:
                logger.warning(
                    "No se pudo registrar el fallo de la solicitud %s: lease perdido",
                    request_id,
                )
        except Exception:
            logger.exception(
                "No se pudo registrar el fallo de la solicitud %s",
                request_id,
            )

    return True
