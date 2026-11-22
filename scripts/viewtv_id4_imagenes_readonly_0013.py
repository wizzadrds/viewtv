"""Verifica que portada y fondo ID4 se pueden recuperar de Jellyfin.

Solo lectura; no imprime imágenes, títulos ni identificadores de servicio.
"""
from sqlmodel import Session, select
from app.database import engine
from app.jellyfin import JellyfinClient
from app.models import Descarga, Solicitud, Medio

with Session(engine) as session:
    download = session.get(Descarga, 4)
    if download is None or download.organizacion_estado != "organizada":
        raise RuntimeError("ID4_NO_ORGANIZADA")
    request = session.get(Solicitud, download.solicitud_id)
    matches = [
        m for m in session.exec(select(Medio)).all()
        if m.titulo.strip().casefold() == request.titulo.strip().casefold()
        and m.disponible_en_jellyfin
    ]
    if len(matches) != 1:
        raise RuntimeError("MEDIO_ID4_NO_UNICO")
    item = matches[0]
    print("ID4_FICHA_SINOPSIS="+str(bool(item.sinopsis)))
    print("ID4_FICHA_ANIO="+str(isinstance(item.anio,int)))
    print("ID4_FICHA_GENEROS="+str(bool(item.generos)))
    print("ID4_FICHA_PORTADA="+str(bool(item.imagen_portada)))
    print("ID4_FICHA_FONDO="+str(bool(item.imagen_fondo)))
    media_id = item.jellyfin_id

client = JellyfinClient()
for kind in ("primary", "backdrop"):
    data, mime = client.get_image(media_id, kind)
    if not data or not mime.startswith("image/"):
        raise RuntimeError("IMAGEN_NO_DISPONIBLE")
    print(f"IMAGEN_{kind.upper()}_VALIDA=SI")
    print(f"IMAGEN_{kind.upper()}_BYTES={len(data)}")
print("ID4_IMAGENES_DISPONIBLES=SI")

# Probar también el proxy autenticado de la aplicación. La dependencia de
# sesión se sustituye SOLO en TestClient en memoria, nunca en API real.
from fastapi.testclient import TestClient
from app.auth import get_current_profile
from app.main import app

app.dependency_overrides[get_current_profile] = lambda: object()
try:
    with TestClient(app) as browser:
        for kind in ("primary", "backdrop"):
            response = browser.get(f"/jellyfin/media/{item.id}/images/{kind}")
            if response.status_code != 200:
                raise RuntimeError(f"PROXY_{kind}_HTTP_{response.status_code}")
            if not response.headers.get("content-type", "").startswith("image/"):
                raise RuntimeError("PROXY_IMAGEN_TIPO_INVALIDO")
            if len(response.content) < 10000:
                raise RuntimeError("PROXY_IMAGEN_VACIA")
            print(f"VIEWTV_PROXY_{kind.upper()}_HTTP=200")
    print("VIEWTV_PROXY_IMAGENES_ID4=OK")
finally:
    app.dependency_overrides.clear()
