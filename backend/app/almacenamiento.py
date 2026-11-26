"""Gestión privada del espacio y seguimiento manual por perfil.

No ofrece eliminación automática de películas: la publicación es un hardlink
NTFS administrado por Windows y se necesita su propia autoridad de liberación.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as ApiPath
from pydantic import BaseModel, Field, StrictBool
from sqlalchemy import func
from sqlmodel import Session, select

from app.almacenamiento_archivos import (
    _cache_own_dir,
    limpiar_temporales,
    tamanio_logico,
    volumen,
)
from app.auth import get_current_profile
from app.cache_privada import CacheNoConfiable, estado_cache
from app.cache_privada import limpiar_cache as limpiar_cache_propia
from app.config import get_settings
from app.database import get_session
from app.models import (
    Medio,
    PeliculaVista,
    Perfil,
    SolicitudRetirada,
    utc_now,
)

CACHE_PROPIA_ROOT = Path("/cache-gestionada")

router = APIRouter(prefix="/almacenamiento", tags=["almacenamiento"])
SessionDep = Annotated[Session, Depends(get_session)]
ProfileDep = Annotated[Perfil, Depends(get_current_profile)]


class EstadoVisto(BaseModel):
    visto: StrictBool


class ConfirmacionRetirada(BaseModel):
    titulo: str = Field(min_length=1, max_length=500)


class ConfirmacionCache(BaseModel):
    confirmacion: str


def _perfil_id(profile: Perfil) -> int:
    if profile.id is None or not profile.activo:
        raise HTTPException(status_code=401, detail="Perfil no autenticado.")
    return profile.id


def _pelicula(session: Session, media_id: int) -> Medio:
    medio = session.get(Medio, media_id)
    if medio is None or medio.tipo != "pelicula" or not medio.disponible_en_jellyfin:
        raise HTTPException(status_code=404, detail="Película no disponible en la biblioteca.")
    return medio


def _vista(session: Session, perfil_id: int, media_id: int) -> PeliculaVista | None:
    return session.exec(
        select(PeliculaVista).where(
            PeliculaVista.perfil_id == perfil_id, PeliculaVista.medio_id == media_id,
        )
    ).first()


def _retirada(session: Session, perfil_id: int, media_id: int) -> SolicitudRetirada | None:
    return session.exec(
        select(SolicitudRetirada).where(
            SolicitudRetirada.perfil_id == perfil_id,
            SolicitudRetirada.medio_id == media_id,
        )
    ).first()


@router.get("/resumen")
def resumen(profile: ProfileDep) -> dict:
    _perfil_id(profile)
    settings = get_settings()
    cache_root = settings.cache_dir
    return {
        "disco": volumen(cache_root),
        "peliculas": tamanio_logico(Path("/media/Peliculas")),
        "descargas_temporales": tamanio_logico(Path("/media/descargas_temporales")),
        "cache_temporal": tamanio_logico(cache_root),
        "cache_gestionada": _cache_own_dir(cache_root) is not None,
        "cache_propia": estado_cache(
            CACHE_PROPIA_ROOT, settings.cache_quota_gb * 1024 ** 3,
        ),
        "cache_cuota_configurada_bytes": settings.cache_quota_gb * (1024 ** 3),
        "cache_cuota_aplicada": False,
        "catalogo_tmdb_bytes": (
            Path("/catalogo/metadatos.db").stat().st_size
            if Path("/catalogo/metadatos.db").is_file() else None
        ),
        "aviso": (
            "Los tamaños de biblioteca son lógicos; los enlaces NTFS compartidos "
            "pueden impedir liberar esos bytes al retirar una película. "
            "No se borran originales de torrent ni caché Jellyfin."
        ),
    }


@router.get("/peliculas")
def peliculas(
    profile: ProfileDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> dict:
    perfil_id = _perfil_id(profile)
    query = select(Medio).where(
        Medio.tipo == "pelicula", Medio.disponible_en_jellyfin.is_(True),
    )
    count = session.exec(
        select(func.count()).select_from(Medio).where(
            Medio.tipo == "pelicula", Medio.disponible_en_jellyfin.is_(True),
        )
    ).one()
    rows = session.exec(query.order_by(Medio.titulo, Medio.id).offset(offset).limit(limit)).all()
    ids = [r.id for r in rows if r.id is not None]
    vistas = session.exec(
        select(PeliculaVista).where(
            PeliculaVista.perfil_id == perfil_id, PeliculaVista.medio_id.in_(ids),
        )
    ).all() if ids else []
    retiradas = session.exec(
        select(SolicitudRetirada).where(
            SolicitudRetirada.perfil_id == perfil_id,
            SolicitudRetirada.medio_id.in_(ids),
        )
    ).all() if ids else []
    seen = {row.medio_id: row for row in vistas}
    removal = {row.medio_id: row for row in retiradas}
    return {
        "total": count,
        "limit": limit,
        "offset": offset,
        "elementos": [
            {
                "id": row.id,
                "titulo": row.titulo,
                "anio": row.anio,
                "visto": row.id in seen,
                "vista_en": (
                    seen[row.id].vista_en.isoformat() if row.id in seen else None
                ),
                "solicitud_retirada": (
                    removal[row.id].estado if row.id in removal else None
                ),
                "eliminacion_automatica_disponible": False,
            }
            for row in rows
        ],
    }


@router.post("/peliculas/{media_id}/visto")
def cambiar_visto(
    media_id: Annotated[int, ApiPath(gt=0)],
    payload: EstadoVisto,
    profile: ProfileDep,
    session: SessionDep,
) -> dict:
    perfil_id = _perfil_id(profile)
    _pelicula(session, media_id)
    mark = _vista(session, perfil_id, media_id)
    if payload.visto:
        if mark is None:
            session.add(PeliculaVista(perfil_id=perfil_id, medio_id=media_id))
        else:
            mark.vista_en = utc_now()
            session.add(mark)
        session.commit()
        return {"visto": True, "estado": "guardado"}
    removal = _retirada(session, perfil_id, media_id)
    if removal and removal.estado == "pendiente_revision":
        raise HTTPException(
            status_code=409,
            detail="Cancela primero la solicitud de retirada pendiente.",
        )
    if mark is not None:
        session.delete(mark)
        session.commit()
    return {"visto": False, "estado": "guardado"}


@router.post("/peliculas/{media_id}/retirada", status_code=202)
def solicitar_retirada(
    media_id: Annotated[int, ApiPath(gt=0)],
    payload: ConfirmacionRetirada,
    profile: ProfileDep,
    session: SessionDep,
) -> dict:
    perfil_id = _perfil_id(profile)
    media = _pelicula(session, media_id)
    if payload.titulo.strip() != media.titulo:
        raise HTTPException(
            status_code=409, detail="La confirmación no coincide con la película.",
        )
    if _vista(session, perfil_id, media_id) is None:
        raise HTTPException(
            status_code=409,
            detail="Marca la película como vista antes de solicitar su retirada.",
        )
    removal = _retirada(session, perfil_id, media_id)
    if removal and removal.estado == "pendiente_revision":
        raise HTTPException(status_code=409, detail="La retirada ya está pendiente.")
    if removal is None:
        removal = SolicitudRetirada(
            perfil_id=perfil_id, medio_id=media_id,
            estado="pendiente_revision",
        )
    else:
        removal.estado = "pendiente_revision"
        removal.actualizada_en = utc_now()
    session.add(removal)
    session.commit()
    return {
        "estado": "pendiente_revision",
        "mensaje": (
            "Petición registrada. NO se ha eliminado ningún archivo. "
            "Un proceso Windows de liberación segura debe comprobar la "
            "propiedad, los enlaces NTFS y el estado de qBittorrent."
        ),
    }


@router.delete("/peliculas/{media_id}/retirada")
def cancelar_retirada(
    media_id: Annotated[int, ApiPath(gt=0)],
    profile: ProfileDep,
    session: SessionDep,
) -> dict:
    perfil_id = _perfil_id(profile)
    _pelicula(session, media_id)
    removal = _retirada(session, perfil_id, media_id)
    if removal is None or removal.estado != "pendiente_revision":
        raise HTTPException(status_code=404, detail="No existe una retirada pendiente.")
    removal.estado = "cancelada"
    removal.actualizada_en = utc_now()
    session.add(removal)
    session.commit()
    return {"estado": "cancelada"}


@router.post("/cache/limpiar")
def limpiar_cache(payload: ConfirmacionCache, profile: ProfileDep) -> dict:
    _perfil_id(profile)
    if payload.confirmacion != "LIMPIAR TEMPORALES":
        raise HTTPException(status_code=422, detail="Confirmación inválida.")
    return limpiar_temporales(get_settings().cache_dir)


@router.post("/cache/propia/limpiar")
def limpiar_cache_viewtv(payload: ConfirmacionCache, profile: ProfileDep) -> dict:
    """Solo volumen privado independiente, nunca medios ni caché compartida."""
    _perfil_id(profile)
    if payload.confirmacion != "LIMPIAR CACHE PROPIA":
        raise HTTPException(status_code=422, detail="Confirmación inválida.")
    try:
        return limpiar_cache_propia(
            CACHE_PROPIA_ROOT, get_settings().cache_quota_gb * 1024 ** 3,
        )
    except (CacheNoConfiable, OSError) as exc:
        raise HTTPException(
            status_code=409,
            detail="La caché privada no supera las comprobaciones de seguridad.",
        ) from exc
