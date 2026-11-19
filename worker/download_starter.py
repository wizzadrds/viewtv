"""Inicio conservador de torrents registrados por VIEWTV."""

import logging
from pathlib import PureWindowsPath

from app.database import engine
from app.download_start_queue import (
    claim_next_start,
    confirm_start_command,
    defer_start_command,
    mark_start_needs_review,
)
from app.qbittorrent import QBittorrentClient, QBittorrentError
from sqlmodel import Session

logger = logging.getLogger("viewtv.download_starter")

ACTIVE_STATES = {
    "downloading",
    "forcedDL",
    "stalledDL",
    "uploading",
    "stalledUP",
    "queuedUP",
    "forcedUP",
    "stoppedUP",
}


def process_one_start(
    worker_id: str,
    client: QBittorrentClient | None = None,
) -> bool:
    """Procesa como máximo un inicio recuperable.

    True indica que se reclamó un trabajo, no necesariamente
    que el torrent haya comenzado a transferir datos.
    """
    with Session(engine) as session:
        download = claim_next_start(session, worker_id)
        if download is None:
            return False

        download_id = download.id
        torrent_hash = download.qbittorrent_hash
        attempt = download.inicio_intentos

    if download_id is None or not torrent_hash:
        return True

    qbittorrent = client if client is not None else QBittorrentClient()
    accepted = False

    try:
        torrents = qbittorrent.torrents_info(
            tag=f"viewtv-descarga-{download_id}"
        )
        matching = [
            torrent
            for torrent in torrents
            if isinstance(torrent.get("hash"), str)
            and torrent["hash"].lower() == torrent_hash.lower()
        ]

        # Exigimos una coincidencia exclusiva de etiqueta y hash.
        if len(torrents) != 1 or len(matching) != 1:
            logger.warning(
                "Inicio %s aplazado: identidad del torrent "
                "no confirmada",
                download_id,
            )
        else:
            torrent = matching[0]
            state = torrent.get("state")
            save_path = torrent.get("save_path")

            expected_path = PureWindowsPath(
                r"C:\VIEWTV\media\descargas_temporales"
            )
            authorized = (
                isinstance(save_path, str)
                and str(PureWindowsPath(save_path)).casefold()
                == str(expected_path).casefold()
            )

            if not authorized:
                logger.warning(
                    "Inicio %s rechazado: carpeta no autorizada",
                    download_id,
                )
            elif state in ACTIVE_STATES:
                # Ya está activo o terminado; no enviamos POST.
                accepted = True

            elif state == "stoppedDL" and attempt == 1:
                # Primer intento, antes de cualquier orden ambigua.
                qbittorrent.start_torrent(torrent_hash)
                accepted = True

            else:
                # No reanudar una pausa manual ni repetir órdenes
                # cuyo resultado anterior pudo ser ambiguo.
                logger.warning(
                    "Inicio %s pendiente de reconciliación; "
                    "estado=%s, intento=%s",
                    download_id,
                    state,
                    attempt,
                )

    except (QBittorrentError, ValueError):
        logger.warning(
            "No se pudo confirmar el inicio %s con qBittorrent",
            download_id,
        )
    except Exception:
        logger.exception(
            "Error inesperado durante inicio %s",
            download_id,
        )

    with Session(engine) as session:
        if accepted:
            changed = confirm_start_command(
                session, download_id, worker_id
            )
        elif attempt >= 2:
            changed = mark_start_needs_review(
                session, download_id, worker_id
            )
        else:
            changed = defer_start_command(
                session, download_id, worker_id
            )

    if not changed:
        logger.warning(
            "El lease del inicio %s ya no es válido",
            download_id,
        )

    return True
