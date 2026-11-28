"""Sincronización puntual de la biblioteca Jellyfin->VIEWTV tras publicar ID3.

Guarda y verifica la transacción mediante synchronize_catalog existente;
falla cerrado si ID3 no está organizada o Jellyfin no contiene su título.
No modifica torrents ni archivos, ni registra credenciales.
"""
import unicodedata

from app.database import engine
from app.jellyfin import JellyfinClient, synchronize_catalog
from app.models import Descarga, Medio, Solicitud
from sqlmodel import Session, select


def norm(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()

with Session(engine) as session:
    download = session.get(Descarga, 3)
    if download is None or download.organizacion_estado != "organizada":
        raise RuntimeError("Descarga 3 aún no organizada.")
    request = session.get(Solicitud, download.solicitud_id)
    if request is None or request.tipo_medio != "pelicula":
        raise RuntimeError("Solicitud no es película.")
    title = norm(request.titulo)
    client = JellyfinClient()
    remote = client.get_items(0, 100)
    items = remote.get("Items")
    if (
        not isinstance(items, list)
        or len(items) < 3
        or not any(
            isinstance(item, dict)
            and item.get("Type") == "Movie"
            and isinstance(item.get("Name"), str)
            and norm(item["Name"]) == title
            and bool((item.get("ImageTags") or {}).get("Primary"))
            for item in items
        )
    ):
        raise RuntimeError("Jellyfin no confirma la película o la carátula.")
    count = synchronize_catalog(session, client)
    actual = [
        medio for medio in session.exec(select(Medio)).all()
        if isinstance(medio.titulo, str)
        and norm(medio.titulo) == title
        and medio.disponible_en_jellyfin
    ]
    if len(actual) != 1 or not actual[0].imagen_portada:
        raise RuntimeError("VIEWTV no reflejó la película con carátula.")
print(f"SINCRONIZACION_JELLYFIN_ELEMENTOS={count}")
print("PELICULA_ID3_EN_VIEWTV=SI")
print("CARATULA_ID3_EN_VIEWTV=SI")
