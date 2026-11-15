"""Endpoint autenticado para crear solicitudes de descarga desde el catálogo."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlmodel import Session, select

from app.auth import get_current_profile
from app.database import get_session
from app.models import Medio, Perfil, Solicitud

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])

ESTADOS_ACTIVOS = ("pendiente", "procesando", "vigilando")


class CrearSolicitudInput(BaseModel):
    medio_id: int = Field(gt=0)


def _begin_write(session: Session) -> None:
    """Inicia una escritura inmediata sin descartar cambios pendientes."""
    if session.in_transaction():
        if session.new or session.dirty or session.deleted:
            raise RuntimeError(
                "Confirma o revierte los cambios pendientes antes de crear la solicitud"
            )
        # La autenticación puede haber abierto una transacción de lectura
        # utilizando la misma sesión de base de datos.
        session.rollback()
    session.exec(text("BEGIN IMMEDIATE"))


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_solicitud(
    payload: CrearSolicitudInput,
    perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int | str | datetime]:
    if perfil.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Perfil no autenticado.",
        )

    _begin_write(session)

    try:
        medio = session.get(Medio, payload.medio_id)

        if medio is None or not medio.disponible_en_jellyfin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Elemento no encontrado.",
            )

        duplicada = session.exec(
            select(Solicitud.id)
            .where(
                Solicitud.perfil_id == perfil.id,
                Solicitud.jellyfin_item_id == medio.jellyfin_id,
                Solicitud.estado.in_(ESTADOS_ACTIVOS),
            )
            .limit(1)
        ).first()

        if duplicada is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una solicitud activa para este elemento.",
            )

        solicitud = Solicitud(
            perfil_id=perfil.id,
            jellyfin_item_id=medio.jellyfin_id,
            titulo=medio.titulo,
        )
        session.add(solicitud)
        session.commit()
        session.refresh(solicitud)

        return {
            "id": solicitud.id,
            "medio_id": medio.id,
            "titulo": solicitud.titulo,
            "estado": solicitud.estado,
            "creado_en": solicitud.creado_en,
        }
    except HTTPException:
        session.rollback()
        raise
