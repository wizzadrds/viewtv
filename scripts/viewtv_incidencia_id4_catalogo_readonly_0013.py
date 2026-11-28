"""Diagnóstico SOLO LECTURA de la película nueva ID4 en Jellyfin/ViewTV.
No imprime títulos, rutas, hashes, Jellyfin IDs ni credenciales.
"""
import unicodedata

from app.database import engine
from app.jellyfin import JellyfinClient
from app.models import Descarga, Medio, Solicitud
from sqlmodel import Session, select


def norm(t):
    return unicodedata.normalize("NFKC", t).strip().casefold()

with Session(engine) as session:
    d = session.get(Descarga, 4)
    if d is None:
        raise SystemExit("ID4_INEXISTENTE")
    print(f"ID4_DESCARGA={d.estado}")
    print(f"ID4_VERIFICACION={d.estado_verificacion}")
    print(f"ID4_ORGANIZACION={d.organizacion_estado}")
    q = session.get(Solicitud, d.solicitud_id)
    if q is None or q.tipo_medio != "pelicula":
        raise SystemExit("ID4_NO_PELICULA")
    expected=norm(q.titulo)
    local=session.exec(select(Medio)).all()
    matches=[m for m in local if isinstance(m.titulo,str) and norm(m.titulo)==expected and m.disponible_en_jellyfin]
    print(f"VIEWTV_ID4_COINCIDENCIAS={len(matches)}")
    print(f"VIEWTV_ID4_CARATULA={any(bool(m.imagen_portada) for m in matches)}")
    print(f"VIEWTV_TOTAL_MEDIOS={len(local)}")
items=[]
client=JellyfinClient()
for page in range(10):
    result=client.get_items(page*100,100)
    chunk=result.get("Items",[])
    items.extend(chunk)
    if len(chunk)<100:break
matches=[x for x in items if isinstance(x,dict) and x.get("Type")=="Movie" and isinstance(x.get("Name"),str) and norm(x["Name"])==expected]
print(f"JELLYFIN_ID4_COINCIDENCIAS={len(matches)}")
print(f"JELLYFIN_ID4_CARATULA={any(bool((x.get('ImageTags') or {}).get('Primary')) for x in matches)}")
print(f"JELLYFIN_TOTAL_MEDIOS={len(items)}")
