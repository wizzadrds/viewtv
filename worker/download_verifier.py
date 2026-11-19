"""Coordinación de verificaciones pendientes de descargas."""

import logging
from pathlib import Path

from sqlmodel import Session, select
from worker.completed_files import verify_completed_files
from worker.file_validator import InvalidTorrentFiles

from app.database import engine
from app.models import Descarga
from app.qbittorrent import QBittorrentClient, QBittorrentError
from app.queue import record_download_verification

logger = logging.getLogger("viewtv.download_verifier")

DOWNLOAD_ROOT = Path("/media/descargas_temporales")


def verify_pending_downloads_once(
    client: QBittorrentClient | None = None,
    media_root: Path = DOWNLOAD_ROOT,
) -> int:
    """Verifica descargas completadas pendientes, sin publicar archivos."""
    qbittorrent = client if client is not None else QBittorrentClient()

    with Session(engine) as session:
        descargas = session.exec(
            select(Descarga).where(
                Descarga.estado == "completada",
                Descarga.progreso == 1,
                Descarga.estado_verificacion == "pendiente",
                Descarga.qbittorrent_hash.is_not(None),
            )
        ).all()

        pendientes = [
            (descarga.id, descarga.qbittorrent_hash)
            for descarga in descargas
        ]

    actualizadas = 0

    for download_id, torrent_hash in pendientes:
        if download_id is None or not torrent_hash:
            continue

        try:
            verify_completed_files(
                qbittorrent,
                torrent_hash,
                media_root,
            )
        except QBittorrentError:
            logger.warning(
                "Comunicación fallida al verificar descarga %s",
                download_id,
            )
            continue
        except (InvalidTorrentFiles, OSError) as exc:
            logger.warning(
                "Archivos no válidos para descarga %s: %s",
                download_id,
                exc,
            )
            with Session(engine) as session:
                changed = record_download_verification(
                    session,
                    download_id,
                    torrent_hash,
                    verified=False,
                    error=str(exc),
                )
        else:
            with Session(engine) as session:
                changed = record_download_verification(
                    session,
                    download_id,
                    torrent_hash,
                    verified=True,
                )

        if changed:
            actualizadas += 1

    return actualizadas
