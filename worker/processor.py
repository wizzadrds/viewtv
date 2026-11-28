"""Procesamiento de búsquedas de la cola durable."""

import base64
import hashlib
import logging
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlsplit

from app.database import engine
from app.jackett import JackettClient, JackettError
from app.models import ResultadoBusqueda
from app.queue import claim_next_request, fail_request, finish_search_request
from app.relevancia_resultado import coincide_con_solicitud
from app.titulo_cohesion import (
    aliases_para_solicitud,
    consultas_jackett,
    solicitud_sin_anio_ambigua,
)
from sqlmodel import Session

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
    def normalize_hash(value: str) -> str | None:
        value = value.strip().lower()
        if re.fullmatch(r"[0-9a-f]{40}", value):
            return value
        if re.fullmatch(r"[a-z2-7]{32}", value):
            try:
                return base64.b32decode(value.upper()).hex()
            except ValueError:
                return None
        return None

    canonical = normalize_hash(info_hash) if info_hash else None
    if not canonical and magnet_url and magnet_url.lower().startswith("magnet:?"):
        for xt in parse_qs(urlsplit(magnet_url).query).get("xt", []):
            if xt.casefold().startswith("urn:btih:"):
                canonical = normalize_hash(xt[9:])
                if canonical:
                    break

    if canonical:
        identity = f"hash:{canonical}"
    elif info_hash:
        identity = f"hash-literal:{info_hash.strip().lower()}"
    elif magnet_url:
        identity = f"magnet:{magnet_url.strip()}"
    else:
        identity = f"url:{(download_url or '').strip()}"

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
        tmdb_id = request.tmdb_id

    if request_id is None:
        return True

    try:
        aliases = (
            aliases_para_solicitud(title, media_type, year, tmdb_id)
            if tmdb_id is not None else
            aliases_para_solicitud(title, media_type, year)
        )
        queries = consultas_jackett(title, media_type, year, aliases)
        jackett = client or JackettClient()
        found = []
        ambiguous = (
            tmdb_id is None and year is None
            and solicitud_sin_anio_ambigua(title, media_type)
        )
        if ambiguous:
            logger.warning(
                "Solicitud %s: título ambiguo; indicar año o elegir carátula TMDB",
                request_id,
            )
        for query in (() if ambiguous else queries):
            try:
                found.extend(jackett.search(
                    query, search_type=_search_type(media_type),
                ))
            except JackettError:
                # No descartar resultados anteriores si falla un alias alternativo.
                if not found:
                    raise
                logger.warning("Una consulta alternativa de Jackett no respondió")
        results = [
            item for item in _to_database_results(request_id, found)
            if coincide_con_solicitud(title, media_type, year, item.titulo, aliases)
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
