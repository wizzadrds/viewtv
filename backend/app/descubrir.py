"""Exploración de películas y series SIN descargar medios ni modificar catálogo Jellyfin.

Solo consulta TMDB (metadatos). Una solicitud de descarga requiere pulsación
separada y usa la cola existente; el usuario elige después una fuente autorizada.
"""
import re
import unicodedata
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlmodel import Session, select

from app.auth import get_current_profile
from app.config import get_settings
from app.database import get_session
from app.models import Medio, Perfil
from app.solicitudes import CrearSolicitudInput, crear_solicitud
from app.tmdb import TMDBClient, TMDBError

router = APIRouter(prefix="/descubrir", tags=["descubrimiento"])
Tipo = Literal["pelicula", "serie"]
IMAGE_PATH = re.compile(r"/[A-Za-z0-9_-]{1,128}\.(?:jpg|jpeg|png|webp)\Z")
MAX_TMDB_ID = 2_147_483_647


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _image(path: object, size: str) -> str | None:
    if not isinstance(path, str) or IMAGE_PATH.fullmatch(path) is None:
        return None
    return TMDBClient.image_url(path, size)


def _year(value: object) -> int | None:
    if not isinstance(value, str) or not re.match(r"\A\d{4}-\d{2}-\d{2}\Z", value):
        return None
    year = int(value[:4])
    return year if 1870 <= year <= 2200 else None


def _current_media(session: Session, kind: Tipo) -> list[Medio]:
    return session.exec(
        select(Medio).where(Medio.tipo == kind, Medio.disponible_en_jellyfin.is_(True))
    ).all()


def _installed(item: dict[str, object], local: list[Medio]) -> int | None:
    tmdb_id = item["tmdb_id"]
    kind = item["tipo"]
    by_id = [m.id for m in local if m.tipo == kind and m.tmdb_id == tmdb_id]
    if len(by_id) == 1:
        return by_id[0]
    if by_id:
        return None
    # Un resultado sin ID TMDB enlazada sólo se asocia cuando año Y nombre
    # coinciden exactamente y existe un único medio local disponible.
    title = item["titulo"]
    year = item["anio"]
    if not isinstance(title, str) or not isinstance(year, int):
        return None
    by_title = [
        m.id for m in local
        if m.tmdb_id is None and m.tipo == kind and m.anio == year
        and _normalize(m.titulo) == _normalize(title)
    ]
    return by_title[0] if len(by_title) == 1 else None


def _item(data: dict, kind: Tipo, local: list[Medio], detail: bool = False) -> dict | None:
    # Jamás mostrar ni permitir solicitar entradas marcadas como adultas.
    if data.get("adult") is True:
        return None
    tmdb_id = data.get("id")
    key = "title" if kind == "pelicula" else "name"
    date = "release_date" if kind == "pelicula" else "first_air_date"
    title = data.get(key)
    if (
        type(tmdb_id) is not int or not 1 <= tmdb_id <= MAX_TMDB_ID
        or not isinstance(title, str) or not title.strip()
        or len(title.strip()) > 500
        or any(ord(ch) < 32 for ch in title)
    ):
        return None
    overview = data.get("overview")
    synopsis = overview[:8000] if isinstance(overview, str) else None
    result = {
        "tmdb_id": tmdb_id,
        "tipo": kind,
        "titulo": title.strip(),
        "sinopsis": synopsis,
        "anio": _year(data.get(date)),
        "imagen_portada": _image(data.get("poster_path"), "w500"),
        "imagen_fondo": _image(data.get("backdrop_path"), "w1280"),
    }
    media_id = _installed(result, local)
    result["disponible_local"] = media_id is not None
    result["medio_id"] = media_id
    if detail:
        genres = data.get("genres")
        result["generos"] = [
            entry["name"] for entry in genres
            if isinstance(entry, dict) and isinstance(entry.get("name"), str)
            and 1 <= len(entry["name"]) <= 80
        ][:12] if isinstance(genres, list) else []
        duration = data.get("runtime") if kind == "pelicula" else None
        result["duracion_minutos"] = (
            duration if type(duration) is int and 1 <= duration <= 1000 else None
        )
    return result


def _tmdb_client() -> TMDBClient:
    try:
        return TMDBClient()
    except TMDBError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El catálogo de descubrimiento necesita una clave TMDB en el servidor.",
        ) from None


def _tmdb_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No se pudieron consultar los metadatos. La biblioteca local sigue disponible.",
    )


@router.get("/estado")
def estado_descubrimiento(
    _perfil: Annotated[Perfil, Depends(get_current_profile)],
) -> dict[str, bool]:
    """Solo informa si TMDB está configurado, nunca devuelve la clave."""
    return {"tmdb_configurado": bool(get_settings().tmdb_api_key)}


def _page(data: dict, kind: Tipo, session: Session, page: int) -> dict:
    raw = data.get("results")
    if not isinstance(raw, list):
        raise _tmdb_error()
    local = _current_media(session, kind)
    results = [
        parsed for row in raw
        if isinstance(row, dict)
        if (parsed := _item(row, kind, local)) is not None
    ][:20]
    pages = data.get("total_pages")
    safe_pages = min(pages, 10) if type(pages) is int and pages >= 1 else 1
    return {"elementos": results, "pagina": page, "paginas": safe_pages}


@router.get("/tendencias")
def tendencias(
    _perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
    tipo: Tipo = "pelicula",
    pagina: Annotated[int, Query(ge=1, le=10)] = 1,
) -> dict:
    try:
        data = _tmdb_client().trending(tipo, pagina)
        return _page(data, tipo, session, pagina)
    except TMDBError:
        raise _tmdb_error() from None


@router.get("/buscar")
def buscar(
    _perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
    titulo: Annotated[str, Query(min_length=2, max_length=100)],
    tipo: Tipo = "pelicula",
    pagina: Annotated[int, Query(ge=1, le=10)] = 1,
) -> dict:
    if len(titulo.strip()) < 2:
        raise HTTPException(status_code=422, detail="Escribe al menos dos caracteres.")
    try:
        data = _tmdb_client().search_page(tipo, titulo, pagina)
        return _page(data, tipo, session, pagina)
    except TMDBError:
        raise _tmdb_error() from None


def _detail_data(kind: Tipo, tmdb_id: int, session: Session) -> dict:
    try:
        data = _tmdb_client().details(kind, tmdb_id)
    except TMDBError:
        raise _tmdb_error() from None
    item = _item(data, kind, _current_media(session, kind), detail=True)
    if item is None or item["tmdb_id"] != tmdb_id:
        raise HTTPException(status_code=404, detail="Ficha de TMDB no disponible.")
    return item


@router.get("/{tipo}/{tmdb_id}")
def detalle(
    tipo: Tipo,
    tmdb_id: Annotated[int, Path(ge=1, le=MAX_TMDB_ID)],
    _perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return _detail_data(tipo, tmdb_id, session)


@router.post("/{tipo}/{tmdb_id}/solicitar", status_code=201)
def solicitar_descarga(
    tipo: Tipo,
    tmdb_id: int,
    perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Una pulsación autoriza la solicitud, nunca descarga automática de tendencias.

    El flujo existente muestra resultados y exige seleccionar uno. El servidor
    vuelve a consultar TMDB, sin confiar en título/año enviados por navegador.
    """
    if tmdb_id < 1 or tmdb_id > MAX_TMDB_ID:
        raise HTTPException(status_code=422, detail="Identificador inválido.")
    item = _detail_data(tipo, tmdb_id, session)
    if item["disponible_local"]:
        raise HTTPException(status_code=409, detail="Este contenido ya está en tu biblioteca.")
    request = CrearSolicitudInput(
        titulo=item["titulo"], tipo_medio=tipo, anio=item["anio"],
    )
    result = crear_solicitud(request, perfil, session)
    return {
        "estado": "solicitud_creada",
        "solicitud_id": result["id"],
        "mensaje": "Solicitud creada. Elige una fuente autorizada en «Buscar y pedir».",
    }
