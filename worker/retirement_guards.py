"""Validación estricta qBittorrent para la retirada de una publicación propia.

Solo evalúa datos GET. No ejecuta borrados, ni inicia ni para torrents.
Si no se puede comprobar propiedad y quiescencia, rechaza.
"""
from pathlib import PureWindowsPath

from app.models import Descarga

from worker.organization_torrent_guard import EXPECTED_SAVE_PATH, HASH_PATTERN

STOPPED_STATES = frozenset({"pausedUP", "stoppedUP"})


def comprobar_torrent_para_retirada(
    download: Descarga,
    torrents: list[dict],
    *,
    expected_save_path: str = EXPECTED_SAVE_PATH,
) -> str:
    """Retorna apto_parcialmente o motivo genérico, nunca una autorización.

    Aun con torrent detenido, hace falta comprobar ruta Jellyfin, journal
    NTFS, exclusividad, uso, permisos y confirmación de administrador.
    """
    if (
        not isinstance(download.id, int) or isinstance(download.id, bool)
        or download.id <= 0
        or download.organizacion_estado != "organizada"
        or download.estado != "completada"
        or download.estado_verificacion != "verificada"
        or download.progreso != 1
        or not download.verificada_en
        or not isinstance(download.qbittorrent_hash, str)
        or HASH_PATTERN.fullmatch(download.qbittorrent_hash) is None
    ):
        return "registro_no_verificado"
    if not isinstance(torrents, list) or len(torrents) != 1:
        return "torrent_ausente_o_ambiguo"
    torrent = torrents[0]
    if not isinstance(torrent, dict) or not isinstance(torrent.get("hash"), str):
        return "identidad_incorrecta"
    if torrent["hash"].casefold() != download.qbittorrent_hash.casefold():
        return "identidad_incorrecta"
    tags_value = torrent.get("tags")
    if not isinstance(tags_value, str):
        return "propiedad_no_acreditada"
    tags = [tag.strip() for tag in tags_value.split(",")]
    own = f"viewtv-descarga-{download.id}"
    if (
        own not in tags or len(tags) != len(set(tags))
        or any(tag.startswith("viewtv-descarga-") and tag != own for tag in tags)
    ):
        return "propiedad_no_acreditada"
    path = torrent.get("save_path")
    if (
        not isinstance(path, str)
        or str(PureWindowsPath(path)).casefold()
        != str(PureWindowsPath(expected_save_path)).casefold()
    ):
        return "carpeta_no_autorizada"
    if torrent.get("state") not in STOPPED_STATES:
        return "torrent_en_uso_o_estado_desconocido"
    if torrent.get("progress") != 1:
        return "torrent_no_completado"
    return "apto_parcialmente"
