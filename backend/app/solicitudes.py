"""Endpoint autenticado para crear solicitudes de descarga desde el catálogo."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, PrivateAttr, model_validator
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from worker.torrent_metadata import (
    TorrentMetadata,
    TorrentMetadataError,
    TorrentMetadataNotFoundError,
    es_url_jackett_dl,
    obtener_metadatos_jackett,
    tamano_incoherente,
)

from app.auth import get_current_profile
from app.config import get_settings
from app.database import get_session
from app.metadatos_resultado import extraer_metadatos
from app.models import (
    Descarga,
    Medio,
    Perfil,
    ResultadoBusqueda,
    Solicitud,
    utc_now,
)
from app.qbittorrent import QBittorrentClient, QBittorrentError
from app.relevancia_resultado import coincide_con_solicitud
from app.titulo_cohesion import aliases_para_solicitud, solicitud_sin_anio_ambigua

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])

ESTADOS_ACTIVOS = (
    "pendiente",
    "procesando",
    "vigilando",
    "esperando_seleccion",
)
MARCA_DESCARTE_USUARIO = "Selección incorrecta descartada por el usuario."

ESTADOS_DESCARGA_ACTIVOS = (
    "seleccionada",
    "enviada",
    "descargando",
    "pausada",
)


def _rechazar_ambiguedad(solicitud: Solicitud) -> None:
    if (solicitud.tmdb_id is None and solicitud.anio is None
            and solicitud_sin_anio_ambigua(
                solicitud.titulo, solicitud.tipo_medio,
            )):
        raise HTTPException(
            status_code=409,
            detail="TMDB conoce varios títulos iguales: solicita la película con año.",
        )


def _aliases_de_solicitud(solicitud: Solicitud) -> tuple[str, ...]:
    """API y worker respetan el mismo ID TMDB sin delegarlo al navegador."""
    if solicitud.tmdb_id is not None:
        return aliases_para_solicitud(
            solicitud.titulo, solicitud.tipo_medio, solicitud.anio, solicitud.tmdb_id,
        )
    return aliases_para_solicitud(
        solicitud.titulo, solicitud.tipo_medio, solicitud.anio,
    )


def _verificar_metadatos_para_perfil(
    resultado: ResultadoBusqueda,
    perfil_id: int,
    session: Session,
) -> tuple[dict[str, object], TorrentMetadata | None]:
    """Datos públicos para la PWA y metainfo privado para persistencia.

    Solo se consulta a Jackett por URL del resultado guardado; el usuario
    nunca puede suministrar una URL arbitraria al verificador.
    """
    anunciado = resultado.tamano_bytes
    base = get_settings().jackett_base_url
    if not resultado.download_url or not es_url_jackett_dl(resultado.download_url, base):
        return ({
            "estado": "no_verificable",
            "puede_seleccionar": False,
            "tamano_anunciado_bytes": anunciado,
            "tamano_real_bytes": None,
            "advertencias": [
                "Este resultado no ofrece metadatos .torrent verificables desde Jackett."
            ],
        }, None)

    try:
        metainfo = obtener_metadatos_jackett(resultado.download_url, base)
    except TorrentMetadataNotFoundError:
        return ({
            "estado": "no_verificable",
            "motivo": "enlace_no_encontrado",
            "puede_seleccionar": False,
            "tamano_anunciado_bytes": anunciado,
            "tamano_real_bytes": None,
            "advertencias": [
                "Jackett ya no encuentra este resultado. Actualiza la búsqueda."
            ],
        }, None)
    except TorrentMetadataError:
        return ({
            "estado": "no_verificable",
            "puede_seleccionar": False,
            "tamano_anunciado_bytes": anunciado,
            "tamano_real_bytes": None,
            "advertencias": [
                "No se han podido leer los metadatos del torrent. No lo selecciones todavía."
            ],
        }, None)

    advertencias: list[str] = []
    if tamano_incoherente(anunciado, metainfo.size_bytes):
        advertencias.append(
            "El tamaño anunciado por Jackett es distinto; se utilizará "
            "el tamaño real del archivo .torrent. Revisa el espacio necesario."
        )

    # Solo comprobamos metainfo real. No vetar por hash duplicado
    # ni por acciones históricas: la nueva selección es voluntaria.
    return ({
        "estado": "apto",
        "puede_seleccionar": True,
        "tamano_anunciado_bytes": anunciado,
        "tamano_real_bytes": metainfo.size_bytes,
        "advertencias": advertencias,
    }, metainfo)


class CrearSolicitudInput(BaseModel):
    medio_id: int | None = Field(default=None, gt=0)
    titulo: str | None = Field(default=None, min_length=1, max_length=500)
    tipo_medio: Literal["pelicula", "serie"] | None = None
    anio: int | None = Field(default=None, ge=1870, le=2200)
    # Solo lo establece el servidor al pulsar una carátula TMDB.
    # Nunca se acepta de JSON enviado por un cliente externo.
    _tmdb_id: int | None = PrivateAttr(default=None)

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
            tmdb_id=(medio.tmdb_id if medio is not None else payload._tmdb_id),
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
    solo_activas: bool = False,
) -> list[dict[str, int | str | datetime | None]]:
    if perfil.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Perfil no autenticado.",
        )

    filtros = [Solicitud.perfil_id == perfil.id]
    if solo_activas:
        filtros.append(Solicitud.estado.in_(ESTADOS_ACTIVOS))

    solicitudes = session.exec(
        select(Solicitud)
        .where(*filtros)
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
    incluir_descartadas: bool = False,
) -> dict[str, object]:
    """Seguimiento de descargas del perfil, sin datos internos del torrent."""
    if perfil.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Perfil no autenticado.",
        )

    filtro_perfil = Solicitud.perfil_id == perfil.id
    filtro_visibilidad = () if incluir_descartadas else (
        or_(
            Descarga.estado != "fallida",
            Descarga.ultimo_error.is_(None),
            Descarga.ultimo_error != MARCA_DESCARTE_USUARIO,
        ),
    )
    total = session.exec(
        select(func.count(Descarga.id))
        .join(Solicitud, Descarga.solicitud_id == Solicitud.id)
        .where(filtro_perfil, *filtro_visibilidad)
    ).one()

    descargas = session.exec(
        select(Descarga)
        .join(Solicitud, Descarga.solicitud_id == Solicitud.id)
        .where(filtro_perfil, *filtro_visibilidad)
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


@router.post("/descargas/{descarga_id}/descartar-incorrecta")
def descartar_descarga_incorrecta(
    descarga_id: int,
    perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int | str]:
    """Descarta una selección que el usuario retiró manualmente de qBittorrent.

    No detiene ni borra torrents: exige comprobar que la descarga ya no
    existe en qBittorrent por su hash ni por su etiqueta propia.
    Conserva registros históricos y evita cualquier inicio posterior.
    """
    if perfil.id is None:
        raise HTTPException(status_code=401, detail="Perfil no autenticado.")

    def es_descartable(descarga: Descarga) -> bool:
        return (
            descarga.estado == "enviada"
            and descarga.inicio_estado == "pendiente"
            and descarga.progreso == 0
            and descarga.inicio_intentos == 0
            and bool(descarga.qbittorrent_hash)
            and descarga.locked_by is None
            and descarga.locked_until is None
            and descarga.inicio_locked_by is None
            and descarga.inicio_locked_until is None
        )

    descarga = session.exec(
        select(Descarga)
        .join(Solicitud, Descarga.solicitud_id == Solicitud.id)
        .where(
            Descarga.id == descarga_id,
            Solicitud.perfil_id == perfil.id,
        )
    ).first()
    if descarga is None:
        raise HTTPException(status_code=404, detail="Descarga no encontrada.")
    if not es_descartable(descarga):
        raise HTTPException(
            status_code=409,
            detail="Esta descarga no puede descartarse de forma segura.",
        )

    torrent_hash = descarga.qbittorrent_hash
    # Nunca tomar la ausencia por cierta si no responde qBittorrent.
    try:
        qbit = QBittorrentClient()
        por_hash = qbit.torrents_info(hashes=[torrent_hash])
        por_etiqueta = qbit.torrents_info(tag=f"viewtv-descarga-{descarga_id}")
    except (QBittorrentError, ValueError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail="No se pudo comprobar qBittorrent. La selección no se ha modificado.",
        ) from exc
    if por_hash or por_etiqueta:
        raise HTTPException(
            status_code=409,
            detail="El torrent aún existe en qBittorrent. No se ha descartado.",
        )

    _begin_write(session)
    try:
        descarga = session.exec(
            select(Descarga)
            .join(Solicitud, Descarga.solicitud_id == Solicitud.id)
            .where(
                Descarga.id == descarga_id,
                Solicitud.perfil_id == perfil.id,
            )
        ).first()
        if descarga is None or not es_descartable(descarga):
            raise HTTPException(
                status_code=409,
                detail="El estado cambió. La selección no se ha descartado.",
            )
        if descarga.qbittorrent_hash != torrent_hash:
            raise HTTPException(
                status_code=409,
                detail="La identidad del torrent cambió. Revisa su estado.",
            )

        solicitud = session.exec(
            select(Solicitud).where(
                Solicitud.id == descarga.solicitud_id,
                Solicitud.perfil_id == perfil.id,
                Solicitud.estado == "completada",
            )
        ).first()
        if solicitud is None:
            raise HTTPException(status_code=409, detail="Solicitud no descartable.")

        # El esquema 0012 restringe estado a valores existentes:
        # "fallida" + marcador inequívoco evita una migración de SQLite.
        descarga.estado = "fallida"
        descarga.inicio_estado = "requiere_revision"
        descarga.inicio_disponible_desde = None
        descarga.ultimo_error = MARCA_DESCARTE_USUARIO
        descarga.actualizado_en = utc_now()
        solicitud.estado = "cancelada"
        solicitud.actualizado_en = utc_now()
        session.add(descarga)
        session.add(solicitud)
        session.commit()
        return {"id": descarga_id, "estado": "descartada"}
    except HTTPException:
        session.rollback()
        raise


@router.post("/descargas/{descarga_id}/deshacer-seleccion")
def deshacer_seleccion(
    descarga_id: int,
    perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, str | int]:
    """Permite retirar SOLO una selección que nunca llegó a qBittorrent."""
    if perfil.id is None:
        raise HTTPException(status_code=401, detail="Perfil no autenticado.")

    _begin_write(session)
    try:
        descarga = session.exec(
            select(Descarga)
            .join(Solicitud, Descarga.solicitud_id == Solicitud.id)
            .where(Descarga.id == descarga_id, Solicitud.perfil_id == perfil.id)
        ).first()
        if descarga is None:
            raise HTTPException(status_code=404, detail="Descarga no encontrada.")
        if not (
            descarga.estado == "seleccionada"
            and descarga.qbittorrent_hash is None
            and descarga.intentos_envio == 0
            and descarga.progreso == 0
            and descarga.locked_by is None
            and descarga.locked_until is None
            and descarga.inicio_estado == "no_requerido"
        ):
            raise HTTPException(
                status_code=409,
                detail="La selección ya ha comenzado a procesarse y no se puede deshacer.",
            )

        solicitud = session.exec(
            select(Solicitud).where(
                Solicitud.id == descarga.solicitud_id,
                Solicitud.perfil_id == perfil.id,
                Solicitud.estado == "completada",
            )
        ).first()
        if solicitud is None:
            raise HTTPException(status_code=409, detail="Solicitud no reversible.")

        # Único registro descartado: una selección NO enviada. Mantener
        # solicitud y resultados para elegir un candidato correcto.
        session.delete(descarga)
        solicitud.estado = "esperando_seleccion"
        session.add(solicitud)
        session.commit()
        return {"solicitud_id": solicitud.id, "estado": "esperando_seleccion"}
    except HTTPException:
        session.rollback()
        raise


@router.post("/{solicitud_id}/actualizar-resultados", status_code=status.HTTP_202_ACCEPTED)
def actualizar_resultados(
    solicitud_id: int,
    perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int | str]:
    """Vuelve a buscar enlaces vigentes sin elegir ni iniciar torrent alguno."""
    if perfil.id is None:
        raise HTTPException(status_code=401, detail="Perfil no autenticado.")

    _begin_write(session)
    try:
        solicitud = session.exec(
            select(Solicitud).where(
                Solicitud.id == solicitud_id,
                Solicitud.perfil_id == perfil.id,
            )
        ).first()
        if solicitud is None:
            raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
        if solicitud.estado not in {"esperando_seleccion", "sin_resultados"}:
            raise HTTPException(
                status_code=409, detail="La solicitud no admite actualizar resultados."
            )
        descarga = session.exec(
            select(Descarga.id)
            .where(Descarga.solicitud_id == solicitud_id)
            .limit(1)
        ).first()
        if descarga is not None:
            raise HTTPException(
                status_code=409,
                detail="No se pueden renovar resultados de una solicitud con descarga.",
            )

        # Los resultados antiguos no se borran hasta que la nueva búsqueda
        # termine con éxito; evitar perder datos ante un error de Jackett.
        solicitud.estado = "pendiente"
        solicitud.intentos = 0
        solicitud.disponible_desde = utc_now()
        solicitud.ultimo_error = None
        solicitud.locked_by = None
        solicitud.locked_until = None
        solicitud.heartbeat = None
        solicitud.actualizado_en = utc_now()
        session.add(solicitud)
        session.commit()
        return {"solicitud_id": solicitud_id, "estado": "pendiente"}
    except HTTPException:
        session.rollback()
        raise


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

    _rechazar_ambiguedad(solicitud)
    respuesta = []
    aliases = _aliases_de_solicitud(solicitud)

    for resultado in resultados:
        if not coincide_con_solicitud(
            solicitud.titulo, solicitud.tipo_medio, solicitud.anio,
            resultado.titulo, aliases,
        ):
            continue
        respuesta.append(
            {
                "id": resultado.id,
                "titulo": resultado.titulo,
                "indexador": resultado.indexador,
                "seeders": resultado.seeders,
                "peers": resultado.peers,
                "tamano_bytes": resultado.tamano_bytes,
                "categorias": resultado.categorias,
                "publicado_en": (
                    resultado.publicado_en.isoformat()
                    if resultado.publicado_en is not None
                    else None
                ),
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


@router.get("/{solicitud_id}/resultados/{resultado_id}/verificacion")
def verificar_resultado(
    solicitud_id: int,
    resultado_id: int,
    perfil: Annotated[Perfil, Depends(get_current_profile)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    """Verifica tamaño y descarte antes de ofrecer selección en la PWA."""
    if perfil.id is None:
        raise HTTPException(status_code=401, detail="Perfil no autenticado.")
    solicitud = session.exec(
        select(Solicitud).where(
            Solicitud.id == solicitud_id,
            Solicitud.perfil_id == perfil.id,
        )
    ).first()
    if solicitud is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    if solicitud.estado != "esperando_seleccion":
        raise HTTPException(status_code=409, detail="La solicitud ya no admite selección.")

    resultado = session.exec(
        select(ResultadoBusqueda).where(
            ResultadoBusqueda.id == resultado_id,
            ResultadoBusqueda.solicitud_id == solicitud_id,
        )
    ).first()
    if resultado is None:
        raise HTTPException(status_code=404, detail="Resultado no encontrado.")
    _rechazar_ambiguedad(solicitud)
    if not coincide_con_solicitud(
        solicitud.titulo, solicitud.tipo_medio, solicitud.anio, resultado.titulo,
        _aliases_de_solicitud(solicitud),
    ):
        raise HTTPException(status_code=409, detail="El título no corresponde a la solicitud.")
    respuesta, _metainfo_privado = _verificar_metadatos_para_perfil(
        resultado, perfil.id, session
    )
    return respuesta


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

    # Prevalidar antes de BEGIN IMMEDIATE: nunca mantener el bloqueo
    # de SQLite durante una petición de red a Jackett.
    resultado_pre = session.exec(
        select(ResultadoBusqueda)
        .join(Solicitud, ResultadoBusqueda.solicitud_id == Solicitud.id)
        .where(
            ResultadoBusqueda.id == payload.resultado_id,
            ResultadoBusqueda.solicitud_id == solicitud_id,
            Solicitud.perfil_id == perfil.id,
            Solicitud.estado == "esperando_seleccion",
        )
    ).first()
    snapshot = None
    metainfo_validado: TorrentMetadata | None = None
    # Resolver nombres oficiales antes de BEGIN IMMEDIATE para no bloquear
    # SQLite mientras se consulta TMDB (o Jackett).
    solicitud_pre = session.exec(
        select(Solicitud).where(
            Solicitud.id == solicitud_id,
            Solicitud.perfil_id == perfil.id,
        )
    ).first()
    if solicitud_pre is not None:
        _rechazar_ambiguedad(solicitud_pre)
    aliases_pre = (
        _aliases_de_solicitud(solicitud_pre) if solicitud_pre is not None else ()
    )
    if resultado_pre is not None:
        snapshot = (
            resultado_pre.download_url,
            resultado_pre.tamano_bytes,
            resultado_pre.titulo,
            resultado_pre.info_hash,
        )
        base = get_settings().jackett_base_url
        if resultado_pre.download_url and es_url_jackett_dl(
            resultado_pre.download_url, base
        ):
            verificacion, metainfo_validado = _verificar_metadatos_para_perfil(
                resultado_pre, perfil.id, session
            )
            if not verificacion["puede_seleccionar"]:
                raise HTTPException(
                    status_code=409,
                    detail="No se pudieron validar los metadatos del torrent.",
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
        if snapshot is not None and (
            resultado.download_url,
            resultado.tamano_bytes,
            resultado.titulo,
            resultado.info_hash,
        ) != snapshot:
            raise HTTPException(
                status_code=409,
                detail="Los metadatos del resultado han cambiado. Compruébalo de nuevo.",
            )
        if not coincide_con_solicitud(
            solicitud.titulo, solicitud.tipo_medio, solicitud.anio,
            resultado.titulo, aliases_pre,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El resultado no corresponde al título o tipo solicitado.",
            )

        descarga = Descarga(
            solicitud_id=solicitud_id,
            resultado_busqueda_id=resultado.id,
            # Jackett puede publicar tamaños y hashes erróneos:
            # para un .torrent comprobado usamos SIEMPRE el metainfo.
            info_hash=(
                metainfo_validado.info_hash
                if metainfo_validado else resultado.info_hash
            ),
            titulo=resultado.titulo,
            indexador=resultado.indexador,
            tamano_bytes=(
                metainfo_validado.size_bytes
                if metainfo_validado else resultado.tamano_bytes
            ),
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
