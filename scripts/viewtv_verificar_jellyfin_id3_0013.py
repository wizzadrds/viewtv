"""Verifica en solo lectura que Jellyfin y el catálogo VIEWTV reconocen #3.
No muestra títulos, IDs Jellyfin, rutas privadas ni tokens.
"""
import unicodedata
from sqlmodel import Session, select
from app.database import engine
from app.jellyfin import JellyfinClient
from app.models import Descarga, Solicitud, Medio

with Session(engine) as session:
    download = session.get(Descarga, 3)
    if download is None or download.organizacion_estado != "organizada":
        raise SystemExit("La descarga 3 no consta organizada.")
    request = session.get(Solicitud, download.solicitud_id)
    if request is None or request.tipo_medio != "pelicula":
        raise SystemExit("La solicitud no corresponde a una película.")
    expected = unicodedata.normalize("NFKC", request.titulo).strip().casefold()
    local = session.exec(select(Medio)).all()
    local_matches = [
        m for m in local
        if isinstance(m.titulo, str)
        and unicodedata.normalize("NFKC", m.titulo).strip().casefold() == expected
        and m.disponible_en_jellyfin
    ]
    print(f"CATALOGO_VIEWTV_COINCIDENCIAS={len(local_matches)}")
    print(f"CATALOGO_VIEWTV_PORTADA={any(bool(m.imagen_portada) for m in local_matches)}")
client = JellyfinClient()
items = []
for page in range(10):
    chunk = client.get_items(page * 100, 100)
    items.extend(chunk.get("Items", []))
    if len(chunk.get("Items", [])) < 100:
        break
matches = [
    item for item in items
    if isinstance(item, dict)
    and item.get("Type") == "Movie"
    and isinstance(item.get("Name"), str)
    and unicodedata.normalize("NFKC", item["Name"]).strip().casefold() == expected
]
print(f"JELLYFIN_PELICULAS_COINCIDENTES={len(matches)}")
print(f"JELLYFIN_PORTADA={any(bool((m.get('ImageTags') or {}).get('Primary')) for m in matches)}")
print(f"JELLYFIN_RUTA_DISPONIBLE={any(isinstance(m.get('Path'), str) for m in matches)}")
print(f"JELLYFIN_TOTAL_ELEMENTOS={len(items)}")
if not matches:
    raise SystemExit(2)
