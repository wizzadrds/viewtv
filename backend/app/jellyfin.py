from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import get_current_profile
from app.config import Settings, get_settings
from app.database import get_session
from app.models import Medio, Perfil

router = APIRouter(prefix="/jellyfin", tags=["Jellyfin"])


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

    def _get(self, path: str, params: dict[str, str | int] | None = None) -> dict:
        headers = {
            "Authorization": f'MediaBrowser Token="{self.api_key}"',
            "Accept": "application/json",
        }
        try:
            with httpx.Client(
                base_url=self.base_url,
                headers=headers,
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
    media.imagen_portada = (
        f"/Items/{jellyfin_id}/Images/Primary" if item.get("ImageTags", {}).get("Primary") else None
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
    client = JellyfinClient()
    total_synced = 0
    start_index = 0
    page_size = 100
    now = datetime.now(UTC)

    try:
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
