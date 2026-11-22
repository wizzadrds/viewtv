"""Solo lectura: relación Jellyfin ID4 -> registro ViewTV -> portada, sin nombres/IDs."""
from sqlmodel import Session,select
from app.database import engine
from app.jellyfin import JellyfinClient
from app.models import Descarga,Solicitud,Medio
from unicodedata import normalize

def norm(x):
    return normalize('NFKC', x or '').strip().casefold()
with Session(engine) as s:
    d=s.get(Descarga,4)
    q=s.get(Solicitud,d.solicitud_id)
    local=s.exec(select(Medio)).all()
    print("LOCAL_MEDIA_COUNT="+str(len(local)))
    j=JellyfinClient().get_items(0,100).get('Items',[])
    print("JF_ITEMS_COUNT="+str(len(j)))
    matched=[x for x in j if isinstance(x,dict) and norm(x.get("Name"))==norm(q.titulo) and x.get('Type')=='Movie']
    print("JF_REQUEST_TITLE_MATCH="+str(len(matched)))
    for remote in matched:
        localids=[m for m in local if m.jellyfin_id==remote.get('Id')]
        print("JF_ID4_TITLE_MATCH_LOCAL_IDS="+str(len(localids)))
        for m in localids:
            print(f"LOCAL_RECORD_ID={m.id}")
            print(f"LOCAL_AVAILABLE={m.disponible_en_jellyfin}")
            print(f"LOCAL_HAS_COVER={bool(m.imagen_portada)}")
            print(f"LOCAL_HAS_BACKDROP={bool(m.imagen_fondo)}")
            print(f"LOCAL_TITLE_EQUALS_REQUEST={norm(m.titulo)==norm(q.titulo)}")
            print(f"LOCAL_TITLE_EQUALS_JF={norm(m.titulo)==norm(remote.get('Name'))}")
            print(f"REMOTE_HAS_COVER={bool((remote.get('ImageTags') or {}).get('Primary'))}")
            print(f"REMOTE_HAS_BACKDROP={bool(remote.get('BackdropImageTags'))}")
    for m in local:
        print(f"LOCAL_SUMMARY_ID={m.id} MOVIE={m.tipo=='pelicula'} AVAILABLE={m.disponible_en_jellyfin} COVER={bool(m.imagen_portada)} BACKDROP={bool(m.imagen_fondo)}")
