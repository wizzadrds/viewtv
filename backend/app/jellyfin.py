from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.auth import get_current_profile
from app.config import Settings, get_settings
from app.database import get_session
from app.models import Medio, Perfil

router = APIRouter(prefix="/jellyfin", tags=["Jellyfin"])
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class JellyfinError(Exception):
    """Error de comunicación con Jellyfin sin exponer credenciales ni respuestas internas."""


class JellyfinClient:
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.jellyfin_base_url.rstrip("/")
        self.api_key = self.settings.jellyfin_api_key
        self.timeout = self.settings.jellyfin_timeout_seconds
        self.transport = transport
        if not self.base_url or not self.api_key:
            raise JellyfinError("Jellyfin no está configurado.")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f'MediaBrowser Token="{self.api_key}"',
            "Accept": "application/json",
        }

    def _get(self, path: str, params: dict[str, str | int] | None = None) -> dict:
        try:
            with httpx.Client(
                base_url=self.base_url,
                headers=self._headers,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = client.get(path, params=params)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise JellyfinError("No se pudo consultar Jellyfin.") from exc
        if not isinstance(data, dict):
            raise JellyfinError("Jellyfin devolvió una respuesta no válida.")
        return data

    def system_info(self) -> dict:
        return self._get("/System/Info")

    def get_items(self, start_index: int, limit: int) -> dict:
        return self._get(
            "/Items",
            {
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Series",
                "Fields": "Overview,Genres,ProductionYear,ImageTags,BackdropImageTags",
                "StartIndex": start_index,
                "Limit": limit,
            },
        )

    def get_image(
        self,
        jellyfin_id: str,
        image_kind: Literal["primary", "backdrop"],
    ) -> tuple[bytes, str]:
        encoded_id = quote(jellyfin_id, safe="")
        image_path = (
            f"/Items/{encoded_id}/Images/Primary"
            if image_kind == "primary"
            else f"/Items/{encoded_id}/Images/Backdrop/0"
        )
        headers = {
            "Authorization": f'MediaBrowser Token="{self.api_key}"',
            "Accept": ", ".join(sorted(ALLOWED_IMAGE_TYPES)),
        }
        try:
            with httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                with client.stream("GET", image_path) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";")[0].lower()
                    if content_type not in ALLOWED_IMAGE_TYPES:
                        raise JellyfinError("Jellyfin devolvió un formato de imagen no permitido.")
                    declared_size = response.headers.get("content-length")
                    if declared_size is not None and int(declared_size) > MAX_IMAGE_BYTES:
                        raise JellyfinError("La imagen supera el tamaño máximo permitido.")
                    image = bytearray()
                    for chunk in response.iter_bytes():
                        image.extend(chunk)
                        if len(image) > MAX_IMAGE_BYTES:
                            raise JellyfinError("La imagen supera el tamaño máximo permitido.")
        except JellyfinError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise JellyfinError("No se pudo obtener la imagen de Jellyfin.") from exc
        return bytes(image), content_type


def _upsert_media(session: Session, item: dict, now: datetime) -> bool:
    jellyfin_id = item.get("Id")
    title = item.get("Name")
    item_type = item.get("Type")
    if not isinstance(jellyfin_id, str) or not jellyfin_id or not isinstance(title, str):
        return False
    if item_type not in {"Movie", "Series"}:
        return False

    media = session.exec(
        select(Medio).where(Medio.jellyfin_id == jellyfin_id)
    ).first()
    if media is None:
        media = Medio(
            jellyfin_id=jellyfin_id,
            tipo="pelicula" if item_type == "Movie" else "serie",
            titulo=title[:500],
        )

    year = item.get("ProductionYear")
    media.tipo = "pelicula" if item_type == "Movie" else "serie"
    media.titulo = title[:500]
    media.sinopsis = item.get("Overview")
    media.anio = year if isinstance(year, int) and 1870 <= year <= 2200 else None
    media.generos = [genre for genre in item.get("Genres", []) if isinstance(genre, str)]
    has_primary_image = bool((item.get("ImageTags") or {}).get("Primary"))
    media.imagen_portada = (
        f"/Items/{jellyfin_id}/Images/Primary" if has_primary_image else None
    )
    media.imagen_fondo = (
        f"/Items/{jellyfin_id}/Images/Backdrop/0"
        if item.get("BackdropImageTags")
        else None
    )
    media.actualizado_en = now
    session.add(media)
    return True


@router.get("/status")
def jellyfin_status(
    _profile: Annotated[Perfil, Depends(get_current_profile)],
) -> dict[str, object]:
    try:
        info = JellyfinClient().system_info()
    except JellyfinError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None
    return {
        "estado": "conectado",
        "servidor": info.get("ServerName"),
        "version": info.get("Version"),
    }


@router.post("/catalog/sync")
def sync_catalog(
    _profile: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int | str]:
    total_synced = 0
    start_index = 0
    page_size = 100
    now = datetime.now(UTC)

    try:
        client = JellyfinClient()
        while True:
            page = client.get_items(start_index, page_size)
            items = page.get("Items", [])
            if not isinstance(items, list):
                raise JellyfinError("Jellyfin devolvió un catálogo no válido.")
            for item in items:
                if isinstance(item, dict) and _upsert_media(session, item, now):
                    total_synced += 1
            session.commit()
            start_index += len(items)
            total_count = page.get("TotalRecordCount")
            if not items or len(items) < page_size:
                break
            if isinstance(total_count, int) and start_index >= total_count:
                break
    except JellyfinError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None
    except Exception:
        session.rollback()
        raise

    return {"estado": "sincronizado", "elementos_procesados": total_synced}


@router.get("/media/{media_id}/images/{image_kind}")
def media_image(
    media_id: int,
    image_kind: Literal["primary", "backdrop"],
    _profile: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    media = session.get(Medio, media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Elemento no encontrado.")
    image_path = media.imagen_portada if image_kind == "primary" else media.imagen_fondo
    if not image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no disponible.")

    try:
        image, content_type = JellyfinClient().get_image(media.jellyfin_id, image_kind)
    except JellyfinError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None

    return Response(
        content=image,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )
