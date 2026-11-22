from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class Perfil(SQLModel, table=True):
    __tablename__ = "perfil"

    id: int | None = Field(default=None, primary_key=True)
    nombre: str = Field(max_length=40, unique=True, index=True)
    pin_hash: str = Field(max_length=255)
    activo: bool = Field(default=True, index=True)
    creado_en: datetime = Field(default_factory=utc_now)


class Medio(SQLModel, table=True):
    """Metadatos persistentes del catálogo; no contiene archivos de vídeo."""

    __tablename__ = "medio"
    __table_args__ = (
        UniqueConstraint("jellyfin_id", name="uq_medio_jellyfin_id"),
        CheckConstraint(
            "tipo IN ('pelicula', 'serie', 'temporada', 'episodio')",
            name="ck_medio_tipo",
        ),
        CheckConstraint(
            "tmdb_estado IN ('pendiente', 'asociado', 'revisar', 'sin_resultado', 'error')",
            name="ck_medio_tmdb_estado",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    jellyfin_id: str = Field(max_length=128, index=True)
    tipo: str = Field(max_length=20, index=True)
    titulo: str = Field(max_length=500, index=True)
    sinopsis: str | None = None
    anio: int | None = Field(default=None, ge=1870, le=2200)
    imagen_portada: str | None = Field(default=None, max_length=1000)
    imagen_fondo: str | None = Field(default=None, max_length=1000)
    generos: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    actualizado_en: datetime = Field(default_factory=utc_now, index=True)
    disponible_en_jellyfin: bool = Field(default=True, index=True)
    tmdb_id: int | None = Field(default=None, index=True)
    tmdb_sinopsis: str | None = None
    tmdb_anio: int | None = Field(default=None, ge=1870, le=2200)
    tmdb_generos: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    tmdb_imagen_portada: str | None = Field(default=None, max_length=1000)
    tmdb_imagen_fondo: str | None = Field(default=None, max_length=1000)
    tmdb_estado: str = Field(default="pendiente", max_length=20, index=True)
    tmdb_intentado_en: datetime | None = None


class Solicitud(SQLModel, table=True):
    """Cola durable. El worker reclama tareas mediante un lease temporal."""

    __tablename__ = "solicitud"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente', 'procesando', 'completada', "
            "'fallida', 'cancelada', 'vigilando', "
            "'esperando_seleccion', 'sin_resultados')",
            name="ck_solicitud_estado",
        ),
        CheckConstraint(
            "tipo_medio IS NULL OR tipo_medio IN "
            "('pelicula', 'serie', 'temporada', 'episodio')",
            name="ck_solicitud_tipo_medio",
        ),
        CheckConstraint("intentos >= 0 AND max_intentos > 0", name="ck_solicitud_intentos"),
        CheckConstraint("prioridad BETWEEN 0 AND 100", name="ck_solicitud_prioridad"),
    )

    id: int | None = Field(default=None, primary_key=True)
    perfil_id: int = Field(foreign_key="perfil.id", index=True)
    jellyfin_item_id: str | None = Field(default=None, max_length=128, index=True)
    titulo: str = Field(max_length=500)
    tipo_medio: str | None = Field(default=None, max_length=20)
    anio: int | None = Field(default=None, ge=1870, le=2200)
    # Identidad exacta de la carátula elegida; nulo para solicitudes históricas.
    tmdb_id: int | None = Field(default=None, gt=0, index=True)
    estado: str = Field(default="pendiente", max_length=20, index=True)
    prioridad: int = Field(default=50, ge=0, le=100, index=True)
    intentos: int = Field(default=0, ge=0)
    max_intentos: int = Field(default=5, gt=0)
    disponible_desde: datetime = Field(default_factory=utc_now, index=True)
    locked_by: str | None = Field(default=None, max_length=128, index=True)
    locked_until: datetime | None = Field(default=None, index=True)
    heartbeat: datetime | None = None
    ultimo_error: str | None = None
    creado_en: datetime = Field(default_factory=utc_now, index=True)
    actualizado_en: datetime = Field(default_factory=utc_now)

class ResultadoBusqueda(SQLModel, table=True):
    """Resultado persistente de Jackett; las URL son exclusivamente internas."""

    __tablename__ = "resultado_busqueda"
    __table_args__ = (
        UniqueConstraint(
            "solicitud_id",
            "clave",
            name="uq_resultado_solicitud_clave",
        ),
        CheckConstraint(
            "tamano_bytes IS NULL OR tamano_bytes >= 0",
            name="ck_resultado_tamano_bytes",
        ),
        CheckConstraint(
            "(download_url IS NOT NULL AND length(trim(download_url)) > 0) "
            "OR (magnet_url IS NOT NULL AND length(trim(magnet_url)) > 0)",
            name="ck_resultado_url",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    solicitud_id: int = Field(foreign_key="solicitud.id", index=True)
    clave: str = Field(max_length=64)
    info_hash: str | None = Field(default=None, max_length=128, index=True)
    titulo: str = Field(max_length=500)
    indexador: str = Field(max_length=128)
    download_url: str | None = Field(default=None, sa_type=Text)
    magnet_url: str | None = Field(default=None, sa_type=Text)
    seeders: int | None = Field(default=None, ge=0)
    peers: int | None = Field(default=None, ge=0)
    tamano_bytes: int | None = Field(default=None, ge=0)
    categorias: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    publicado_en: datetime | None = None
    creado_en: datetime = Field(default_factory=utc_now)

class Descarga(SQLModel, table=True):
    """Seguimiento durable de un resultado enviado al gestor de descargas."""

    __tablename__ = "descarga"
    __table_args__ = (
        CheckConstraint(
            "tamano_bytes IS NULL OR tamano_bytes >= 0",
            name="ck_descarga_tamano_bytes",
        ),
        CheckConstraint(
            "intentos_envio >= 0 AND max_intentos_envio > 0",
            name="ck_descarga_intentos_envio",
        ),
        CheckConstraint(
            "estado IN ('seleccionada', 'enviada', 'descargando', "
            "'pausada', 'completada', 'fallida')",
            name="ck_descarga_estado",
        ),
        CheckConstraint(
            "progreso >= 0.0 AND progreso <= 1.0",
            name="ck_descarga_progreso",
        ),
        Index(
            "uq_descarga_info_hash",
            "info_hash",
            unique=True,
            sqlite_where=text(
                "info_hash IS NOT NULL "
                "AND estado IN ('seleccionada', 'enviada', "
                "'descargando', 'pausada')"
            ),
        ),
    )

    intentos_envio: int = Field(default=0, ge=0)
    max_intentos_envio: int = Field(default=5, gt=0)
    disponible_desde: datetime = Field(default_factory=utc_now, index=True)
    locked_by: str | None = Field(default=None, max_length=128)
    locked_until: datetime | None = None
    heartbeat: datetime | None = None

    id: int | None = Field(default=None, primary_key=True)
    solicitud_id: int = Field(foreign_key="solicitud.id", index=True)
    resultado_busqueda_id: int | None = Field(
        default=None,
        foreign_key="resultado_busqueda.id",
        index=True,
    )
    info_hash: str | None = Field(default=None, max_length=128)
    titulo: str = Field(max_length=500)
    indexador: str | None = Field(default=None, max_length=128)
    qbittorrent_hash: str | None = Field(default=None, max_length=128)
    estado: str = Field(default="seleccionada", max_length=20, index=True)
    progreso: float = Field(default=0.0, ge=0.0, le=1.0)
    tamano_bytes: int | None = Field(default=None, ge=0)
    ultimo_error: str | None = Field(default=None, sa_type=Text)
    estado_verificacion: str = Field(
        default="pendiente",
        max_length=20,
        index=True,
    )
    verificada_en: datetime | None = None
    error_verificacion: str | None = Field(default=None, sa_type=Text)
    verificacion_locked_by: str | None = Field(
        default=None, max_length=128
    )
    verificacion_locked_until: datetime | None = None
    verificacion_heartbeat: datetime | None = None
    verificacion_disponible_desde: datetime | None = None
    verificacion_intentos_temporales: int = Field(
        default=0, ge=0
    )

    inicio_estado: str = Field(
        default="no_requerido", max_length=20, index=True
    )
    inicio_locked_by: str | None = Field(
        default=None, max_length=128
    )
    inicio_locked_until: datetime | None = None
    inicio_disponible_desde: datetime | None = None
    inicio_intentos: int = Field(default=0, ge=0)

    # Preparación de la futura organización; el worker de producción
    # NO consume esta cola mientras no exista un ejecutor seguro.
    organizacion_estado: str = Field(
        default="no_requerida", max_length=20, index=True
    )
    organizacion_locked_by: str | None = Field(
        default=None, max_length=128
    )
    organizacion_locked_until: datetime | None = None
    organizacion_disponible_desde: datetime | None = None
    organizacion_intentos: int = Field(default=0, ge=0)
    organizacion_ultimo_error: str | None = Field(default=None, sa_type=Text)

    creado_en: datetime = Field(default_factory=utc_now)
    actualizado_en: datetime = Field(default_factory=utc_now)
