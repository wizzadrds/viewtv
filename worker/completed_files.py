"""Verificación de descargas terminadas sin modificar archivos."""

from pathlib import Path

from app.qbittorrent import QBittorrentClient

from worker.file_validator import (
    InvalidTorrentFiles,
    validate_torrent_files,
)

COMPLETE_STATES = {
    "stoppedUP",
    "uploading",
    "stalledUP",
    "queuedUP",
    "forcedUP",
}


def verify_completed_files(
    client: QBittorrentClient,
    torrent_hash: str,
    media_root: Path,
) -> list[Path]:
    """Comprueba que un torrent terminado tiene archivos válidos."""

    torrents = client.torrents_info(hashes=[torrent_hash])

    matching = [
        torrent
        for torrent in torrents
        if isinstance(torrent.get("hash"), str)
        and torrent["hash"].lower() == torrent_hash.lower()
    ]

    if len(matching) != 1:
        raise InvalidTorrentFiles(
            "No se encontró exactamente el torrent esperado."
        )

    torrent = matching[0]

    if torrent.get("state") not in COMPLETE_STATES:
        raise InvalidTorrentFiles(
            "El torrent no está en un estado terminado verificable."
        )

    files = client.torrent_files(torrent_hash)

    return validate_torrent_files(
        torrent,
        files,
        media_root,
    )
