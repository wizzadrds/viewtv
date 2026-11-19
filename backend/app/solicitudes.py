"""Endpoint autenticado para crear solicitudes de descarga desde el catálogo."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth import get_current_profile
from app.database import get_session
from app.metadatos_resultado import extraer_metadatos
from app.models import (
    Descarga,
    Medio,
    Perfil,
    ResultadoBusqueda,
    Solicitud,
)

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])

ESTADOS_ACTIVOS = (
    "pendiente",
    "procesando",
    "vigilando",
    "esperando_seleccion",
)
ESTADOS_DESCARGA_ACTIVOS = (
    "seleccionada",
    "enviada",
    "descargando",
    "pausada",
)


class CrearSolicitudInput(BaseModel):
    medio_id: int | None = Field(default=None, gt=0)
    titulo: str | None = Field(default=None, min_length=1, max_length=500)
    tipo_medio: Literal["pelicula", "serie"] | None = None
    anio: int | None = Field(default=None, ge=1870, le=2200)

    @model_validator(mode="after")
    def validar_modalidad(self):
        catalogo = self.medio_id is not None
        manual = self.titulo is not None or self.tipo_medio is not None or self.anio is not None

        if catalogo == manual:
            raise ValueError(
                "Indica medio_id o los datos de una solicitud manual."
            )

        if manual:
            if self.titulo is None or not self.titulo.strip():
                raise ValueError("El título no puede estar vacío.")
            if self.tipo_medio is None:
                raise ValueError("El tipo de medio es obligatorio.")

            self.titulo = self.titulo.strip()

        return self


class SeleccionarResultadoInput(BaseModel):
    resultado_id: int = Field(gt=0)


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
) -> dict[str, int | str | datetime | None]:
    if perfil.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Perfil no autenticado.",
        )

    _begin_write(session)

    try:
        medio = None

        if payload.medio_id is not None:
            medio = session.get(Medio, payload.medio_id)

            if medio is None or not medio.disponible_en_jellyfin:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Elemento no encontrado.",
                )

            titulo = medio.titulo
            tipo_medio = medio.tipo
            anio = medio.anio
            jellyfin_item_id = medio.jellyfin_id

            duplicada = session.exec(
                select(Solicitud.id)
                .where(
                    Solicitud.perfil_id == perfil.id,
                    Solicitud.jellyfin_item_id == jellyfin_item_id,
                    Solicitud.estado.in_(ESTADOS_ACTIVOS),
                )
                .limit(1)
            ).first()

        else:
            titulo = payload.titulo
            tipo_medio = payload.tipo_medio
            anio = payload.anio
            jellyfin_item_id = None

            duplicados = [
                Solicitud.perfil_id == perfil.id,
                Solicitud.jellyfin_item_id.is_(None),
                func.lower(func.trim(Solicitud.titulo)) == titulo.lower(),
                Solicitud.tipo_medio == tipo_medio,
                Solicitud.estado.in_(ESTADOS_ACTIVOS),
            ]

            if anio is None:
                duplicados.append(Solicitud.anio.is_(None))
            else:
                duplicados.append(Solicitud.anio == anio)

            duplicada = session.exec(
                select(Solicitud.id).where(*duplicados).limit(1)
            ).first()

        if duplicada is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una solicitud activa para este elemento.",
            )

        solicitud = Solicitud(
            perfil_id=perfil.id,
            jellyfin_item_id=jellyfin_item_id,
            titulo=titulo,
            tipo_medio=tipo_medio,
            anio=anio,
        )
        session.add(solicitud)
        session.commit()
        session.refresh(solicitud)

        return {
            "id": solicitud.id,
            "medio_id": medio.id if medio is not None else None,
            "titulo": solicitud.titulo,
            "estado": solicitud.estado,
            "creado_en": solicitud.creado_en,
        }

    except HTTPException:
        session.rollback()
        raise


@router.get("")
def listar_solicitudes(
    perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, int | str | datetime | None]]:
    if perfil.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Perfil no autenticado.",
        )

    solicitudes = session.exec(
        select(Solicitud)
        .where(Solicitud.perfil_id == perfil.id)
        .order_by(Solicitud.creado_en.desc())
    ).all()

    return [
        {
            "id": solicitud.id,
            "titulo": solicitud.titulo,
            "tipo_medio": solicitud.tipo_medio,
            "anio": solicitud.anio,
            "estado": solicitud.estado,
            "creado_en": solicitud.creado_en,
        }
        for solicitud in solicitudes
    ]


@router.get("/descargas")
def listar_descargas(
    perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    """Seguimiento de descargas del perfil, sin datos internos del torrent."""
    if perfil.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Perfil no autenticado.",
        )

    filtro_perfil = Solicitud.perfil_id == perfil.id
    total = session.exec(
        select(func.count(Descarga.id))
        .join(Solicitud, Descarga.solicitud_id == Solicitud.id)
        .where(filtro_perfil)
    ).one()

    descargas = session.exec(
        select(Descarga)
        .join(Solicitud, Descarga.solicitud_id == Solicitud.id)
        .where(filtro_perfil)
        .order_by(Descarga.creado_en.desc(), Descarga.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return {
        "elementos": [
            {
                "id": descarga.id,
                "solicitud_id": descarga.solicitud_id,
                "titulo": descarga.titulo,
                "estado": descarga.estado,
                "progreso": descarga.progreso,
                "tamano_bytes": descarga.tamano_bytes,
                "inicio_estado": descarga.inicio_estado,
                "estado_verificacion": descarga.estado_verificacion,
                "creado_en": descarga.creado_en,
                "actualizado_en": descarga.actualizado_en,
            }
            for descarga in descargas
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{solicitud_id}/resultados")
def listar_resultados(
    solicitud_id: int,
    perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, int | str | list | None]]:
    if perfil.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Perfil no autenticado.",
        )

    solicitud = session.exec(
        select(Solicitud).where(
            Solicitud.id == solicitud_id,
            Solicitud.perfil_id == perfil.id,
        )
    ).first()

    if solicitud is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada.",
        )

    if solicitud.estado != "esperando_seleccion":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La solicitud no está esperando una selección.",
        )

    resultados = session.exec(
        select(ResultadoBusqueda)
        .where(ResultadoBusqueda.solicitud_id == solicitud_id)
    ).all()

    orden_resolucion = {
        "2160p": 0,
        "1080p": 1,
        "720p": 2,
        "576p": 3,
        "480p": 4,
    }

    respuesta = []

    for resultado in resultados:
        respuesta.append(
            {
                "id": resultado.id,
                "titulo": resultado.titulo,
                "indexador": resultado.indexador,
                "seeders": resultado.seeders,
                "peers": resultado.peers,
                "tamano_bytes": resultado.tamano_bytes,
                "categorias": resultado.categorias,
                "publicado_en": resultado.publicado_en,
                **extraer_metadatos(resultado.titulo),
            }
        )

    return sorted(
        respuesta,
        key=lambda item: (
            orden_resolucion.get(item["resolucion"], 5),
            -(item["seeders"] or 0),
            item["titulo"].casefold(),
        ),
    )


@router.post("/{solicitud_id}/seleccion", status_code=status.HTTP_201_CREATED)
def seleccionar_resultado(
    solicitud_id: int,
    payload: SeleccionarResultadoInput,
    perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int | str | datetime | None]:
    if perfil.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Perfil no autenticado.",
        )

    _begin_write(session)

    try:
        solicitud = session.exec(
            select(Solicitud).where(
                Solicitud.id == solicitud_id,
                Solicitud.perfil_id == perfil.id,
            )
        ).first()

        if solicitud is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud no encontrada.",
            )

        if solicitud.estado != "esperando_seleccion":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La solicitud no está esperando una selección.",
            )

        descarga_existente = session.exec(
            select(Descarga.id)
            .where(
                Descarga.solicitud_id == solicitud_id,
                Descarga.estado.in_(ESTADOS_DESCARGA_ACTIVOS),
            )
            .limit(1)
        ).first()

        if descarga_existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La solicitud ya tiene una descarga activa.",
            )

        resultado = session.exec(
            select(ResultadoBusqueda).where(
                ResultadoBusqueda.id == payload.resultado_id,
                ResultadoBusqueda.solicitud_id == solicitud_id,
            )
        ).first()

        if resultado is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resultado no encontrado para esta solicitud.",
            )

        descarga = Descarga(
            solicitud_id=solicitud_id,
            resultado_busqueda_id=resultado.id,
            info_hash=resultado.info_hash,
            titulo=resultado.titulo,
            indexador=resultado.indexador,
            tamano_bytes=resultado.tamano_bytes,
            estado="seleccionada",
        )

        solicitud.estado = "completada"

        session.add(descarga)
        session.commit()
        session.refresh(descarga)

        return {
            "id": descarga.id,
            "solicitud_id": descarga.solicitud_id,
            "resultado_id": descarga.resultado_busqueda_id,
            "titulo": descarga.titulo,
            "estado": descarga.estado,
            "creado_en": descarga.creado_en,
        }

    except HTTPException:
        session.rollback()
        raise
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El resultado ya tiene una descarga activa.",
        ) from exc
