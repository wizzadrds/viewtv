"""Sondeo GET Jellyfin por código de respuesta sin exponer rutas o IDs."""
from urllib.parse import quote

import httpx
from app.config import get_settings
from app.database import engine
from app.models import Medio
from sqlmodel import Session, select

settings = get_settings()
with Session(engine) as db:
    movie = db.exec(select(Medio).where(Medio.tipo == "pelicula")).first()
assert movie is not None
item = quote(movie.jellyfin_id, safe="")
paths = {"items": f"/Items/{item}"}
if settings.jellyfin_user_id:
    user = quote(settings.jellyfin_user_id, safe="")
    paths["user_items"] = f"/Users/{user}/Items/{item}"

for label, path in paths.items():
    try:
        with httpx.Client(
            base_url=settings.jellyfin_base_url.rstrip("/"),
            headers={"Authorization": f'MediaBrowser Token="{settings.jellyfin_api_key}"'},
            timeout=5,
        ) as client:
            response = client.get(path)
            print("RUTA_" + label + "_HTTP=" + str(response.status_code))
            if response.status_code == 200:
                body = response.json()
                print("RUTA_" + label + "_TIPO_MOVIE=" +
                      str(body.get("Type") == "Movie"))
                print("RUTA_" + label + "_PATH_PRESENTE=" +
                      str(isinstance(body.get("Path"), str)))
    except (httpx.HTTPError, ValueError):
        print("RUTA_" + label + "_HTTP=ERROR")
