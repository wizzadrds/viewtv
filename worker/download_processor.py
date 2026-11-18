
"""Procesamiento de descargas seleccionadas por el usuario."""

import logging

from sqlmodel import Session, select

from app.database import engine
from app.models import ResultadoBusqueda
from app.qbittorrent import QBittorrentClient, QBittorrentError
from app.queue import (
    claim_next_download,
    fail_download,
    mark_download_submitted,
    record_download_attempt,
)

logger = logging.getLogger("viewtv.worker.download_processor")


def _torrent_hash(torrents: list[dict]) -> str | None:
    """Obtiene un hash válido de la respuesta de qBittorrent."""
    for torrent in torrents:
        value = torrent.get("hash")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def _record_failure(
    download_id: int,
    worker_id: str,
    message: str,
    *,
    permanent: bool = False,
) -> None:
    with Session(engine) as session:
        failed = fail_download(
            session,
            download_id,
            worker_id,
            message,
            permanent=permanent,
        )

    if not failed:
        logger.warning(
            "No se pudo registrar el fallo de la descarga %s: lease perdido",
            download_id,
        )


def process_one_download(
    worker_id: str,
    client: QBittorrentClient | None = None,
) -> bool:
    """Procesa una descarga seleccionada; False indica que no había trabajo."""
    with Session(engine) as session:
        download = claim_next_download(session, worker_id)

        if download is None:
            return False

        download_id = download.id
        request_id = download.solicitud_id
        result_id = download.resultado_busqueda_id
        attempts = download.intentos_envio
        max_attempts = download.max_intentos_envio

        result = None
        if result_id is not None:
            result = session.exec(
                select(ResultadoBusqueda).where(
                    ResultadoBusqueda.id == result_id,
                    ResultadoBusqueda.solicitud_id == request_id,
                )
            ).first()

        magnet_url = result.magnet_url if result else None
        download_url = result.download_url if result else None

    if download_id is None:
        return True

    # La selección debe apuntar a un resultado de la misma solicitud.
    if result is None:
        _record_failure(
            download_id,
            worker_id,
            "No se encuentra el resultado de búsqueda seleccionado.",
            permanent=True,
        )
        return True

    # Preferimos el magnet; usamos la URL torrent como alternativa.
    torrent_url = magnet_url or download_url
    if not torrent_url or not torrent_url.strip():
        _record_failure(
            download_id,
            worker_id,
            "El resultado seleccionado no tiene un enlace utilizable.",
            permanent=True,
        )
        return True

    tag = f"viewtv-descarga-{download_id}"

    try:
        qbittorrent = client or QBittorrentClient()

        # Primero reconciliamos: el envío pudo completarse antes de
        # que un worker anterior perdiera su lease o se interrumpiera.
        existing = qbittorrent.torrents_info(tag=tag)
        existing_hash = _torrent_hash(existing)

        if existing:
            if existing_hash is None:
                raise QBittorrentError(
                    "qBittorrent encontró la etiqueta, pero no devolvió su hash."
                )

            with Session(engine) as session:
                saved = mark_download_submitted(
                    session,
                    download_id,
                    worker_id,
                    existing_hash,
                )

            if not saved:
                logger.warning(
                    "Lease perdido al reconciliar la descarga %s",
                    download_id,
                )
            else:
                logger.info(
                    "Descarga %s ya estaba en qBittorrent; envío reconciliado",
                    download_id,
                )
            return True

        # Si ya se consumieron todos los intentos, no volvemos a enviar.
        if attempts >= max_attempts:
            _record_failure(
                download_id,
                worker_id,
                "No se encontró el torrent en qBittorrent tras agotar los intentos.",
            )
            return True

        # Consumimos el intento justo antes de llamar a qBittorrent.
        with Session(engine) as session:
            recorded = record_download_attempt(
                session,
                download_id,
                worker_id,
            )

        if not recorded:
            logger.warning(
                "No se pudo consumir un intento para la descarga %s",
                download_id,
            )
            return True

        qbittorrent.add_torrent(
            torrent_url,
            tags=[tag],
            stopped=True,
        )

        # Confirmamos mediante la etiqueta, no suponiendo que el alta
        # HTTP equivale a que el torrent ya esté registrado.
        submitted = qbittorrent.torrents_info(tag=tag)
        torrent_hash = _torrent_hash(submitted)

        if torrent_hash is None:
            raise QBittorrentError(
                "qBittorrent aceptó el envío, pero todavía no aparece "
                "el torrent con su etiqueta."
            )

        with Session(engine) as session:
            saved = mark_download_submitted(
                session,
                download_id,
                worker_id,
                torrent_hash,
            )

        if saved:
            logger.info(
                "Descarga %s enviada a qBittorrent",
                download_id,
            )
        else:
            logger.warning(
                "Lease perdido al confirmar la descarga %s",
                download_id,
            )

    except Exception as error:
        logger.exception(
            "Error procesando la descarga %s",
            download_id,
        )

        message = (
            str(error)
            if isinstance(error, QBittorrentError)
            else f"Error interno: {error.__class__.__name__}"
        )

        try:
            _record_failure(
                download_id,
                worker_id,
                message,
            )
        except Exception:
            logger.exception(
                "No se pudo registrar el fallo de la descarga %s",
                download_id,
            )

    return True
