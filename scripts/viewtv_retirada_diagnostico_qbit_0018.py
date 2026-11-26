"""Solo GET: por qué un inventario qBit no puede autorizar retirada.

Salida agregada, sin nombres de archivos, rutas, IDs, títulos ni hashes.
"""
from sqlmodel import Session, select

from app.database import engine
from app.models import Descarga
from app.qbittorrent import QBittorrentClient, QBittorrentError

with Session(engine) as session:
    organized = session.exec(
        select(Descarga).where(Descarga.organizacion_estado == "organizada")
    ).all()
counts = {
    "descargas": len(organized),
    "archivos": 0,
    "size_cero": 0,
    "incompletos": 0,
    "prioridad_excluida": 0,
    "nombre_vacio": 0,
    "sin_listado": 0,
    "consulta_fallida": 0,
}
client = QBittorrentClient()
for d in organized:
    try:
        if not isinstance(d.qbittorrent_hash, str):
            counts["sin_listado"] += 1
            continue
        files = client.torrent_files(d.qbittorrent_hash)
    except (QBittorrentError, ValueError):
        counts["consulta_fallida"] += 1
        continue
    if not files:
        counts["sin_listado"] += 1
    for f in files:
        counts["archivos"] += 1
        if not isinstance(f.get("size"), int) or f["size"] <= 0:
            counts["size_cero"] += 1
        if f.get("progress") != 1:
            counts["incompletos"] += 1
        if not isinstance(f.get("priority"), int) or f["priority"] <= 0:
            counts["prioridad_excluida"] += 1
        if not isinstance(f.get("name"), str) or not f["name"]:
            counts["nombre_vacio"] += 1

for key, value in counts.items():
    print("QBIT_DIAGNOSTICO_" + key.upper() + "=" + str(value))
print("TALLES_DE_ARCHIVO_NI_RUTAS_DIVULGADOS=NO")
print("ESCRITURAS_QBIT=0")
