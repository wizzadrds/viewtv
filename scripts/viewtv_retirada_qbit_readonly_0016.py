"""Comprobación GET de qBit, sin mostrar hashes/títulos/rutas ni escribir."""
from pathlib import PureWindowsPath

from app.database import engine
from app.models import Descarga
from app.qbittorrent import QBittorrentClient, QBittorrentError
from sqlmodel import Session, select

from worker.organization_torrent_guard import EXPECTED_SAVE_PATH

with Session(engine) as db:
    organized = db.exec(select(Descarga).where(
        Descarga.organizacion_estado == "organizada",
    )).all()

result = {
    "registros": len(organized), "propiedad": 0, "detenidos": 0,
    "en_uso": 0, "ausentes": 0, "errores_consulta": 0,
}
client = QBittorrentClient()
for d in organized:
    try:
        if not isinstance(d.qbittorrent_hash, str):
            result["ausentes"] += 1
            continue
        torrents = client.torrents_info(hashes=[d.qbittorrent_hash])
    except (QBittorrentError, ValueError):
        result["errores_consulta"] += 1
        continue
    if (
        len(torrents) != 1
        or torrents[0].get("hash", "").casefold() != d.qbittorrent_hash.casefold()
    ):
        result["ausentes"] += 1
        continue
    torrent = torrents[0]
    tags = torrent.get("tags")
    path = torrent.get("save_path")
    if (
        not isinstance(tags, str)
        or f"viewtv-descarga-{d.id}" not in [t.strip() for t in tags.split(",")]
        or not isinstance(path, str)
        or str(PureWindowsPath(path)).casefold()
        != str(PureWindowsPath(EXPECTED_SAVE_PATH)).casefold()
    ):
        continue
    result["propiedad"] += 1
    if torrent.get("state") in {"pausedUP", "stoppedUP"} and torrent.get("progress") == 1:
        result["detenidos"] += 1
    else:
        result["en_uso"] += 1

for key, value in result.items():
    print("QBIT_" + key.upper() + "=" + str(value))
print("TORRENTS_BORRADOS=0")
print("SOLICITUDES_CREADAS=0")
