"""Identidad qBittorrent de lectura para el futuro organizador.

NO se usa en worker/main.py ni ejecuta POST, copia o borrado.
Exige hash, etiqueta de propiedad de VIEWTV y carpeta autorizada.
"""

import re
from pathlib import Path, PureWindowsPath

from app.models import Descarga
from app.qbittorrent import QBittorrentClient
from worker.completed_files import COMPLETE_STATES
from worker.file_validator import InvalidTorrentFiles, validate_torrent_files

EXPECTED_SAVE_PATH = r"C:\VIEWTV\media\descargas_temporales"
HASH_PATTERN = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


def verify_organization_torrent_identity(
    client: QBittorrentClient,
    download: Descarga,
    media_root: Path,
    *,
    expected_save_path: str = EXPECTED_SAVE_PATH,
) -> list[Path]:
    """Recomprueba una descarga propia antes de construir su plan de copia.

    Consulta exclusivamente torrents/info y torrents/files.
    No equivale a una autorización general para escribir en bibliotecas.
    """
    if (
        not isinstance(download, Descarga)
        or isinstance(download.id, bool)
        or not isinstance(download.id, int)
        or download.id <= 0
        or download.estado != "completada"
        or download.progreso != 1
        or download.estado_verificacion != "verificada"
        or download.verificada_en is None
        or download.organizacion_estado != "pendiente"
    ):
        raise InvalidTorrentFiles("La descarga no está habilitada para organizarse.")

    torrent_hash = download.qbittorrent_hash
    if not isinstance(torrent_hash, str) or HASH_PATTERN.fullmatch(torrent_hash) is None:
        raise InvalidTorrentFiles("Hash de descarga no válido.")

    expected_tag = f"viewtv-descarga-{download.id}"
    torrents = client.torrents_info(hashes=[torrent_hash])
    if not isinstance(torrents, list) or len(torrents) != 1:
        raise InvalidTorrentFiles("No existe una coincidencia exclusiva del torrent.")
    torrent = torrents[0]
    if (
        not isinstance(torrent, dict)
        or not isinstance(torrent.get("hash"), str)
        or torrent["hash"].casefold() != torrent_hash.casefold()
    ):
        raise InvalidTorrentFiles("El torrent no coincide con el registro de VIEWTV.")

    tags_value = torrent.get("tags")
    if not isinstance(tags_value, str):
        raise InvalidTorrentFiles("El torrent no presenta etiquetas válidas.")
    tags = [value.strip() for value in tags_value.split(",")]
    if (
        expected_tag not in tags
        or len(tags) != len(set(tags))
        or any(
            tag.startswith("viewtv-descarga-") and tag != expected_tag
            for tag in tags
        )
    ):
        raise InvalidTorrentFiles("El torrent no pertenece de forma exclusiva a VIEWTV.")

    if torrent.get("state") not in COMPLETE_STATES:
        raise InvalidTorrentFiles("El torrent no está finalizado.")

    save_path = torrent.get("save_path")
    if (
        not isinstance(save_path, str)
        or str(PureWindowsPath(save_path)).casefold()
        != str(PureWindowsPath(expected_save_path)).casefold()
    ):
        raise InvalidTorrentFiles("La carpeta del torrent no está autorizada.")

    files = client.torrent_files(torrent_hash)
    return validate_torrent_files(
        torrent,
        files,
        media_root,
        expected_save_path=expected_save_path,
    )
