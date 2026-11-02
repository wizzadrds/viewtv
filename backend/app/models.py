from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, Column, UniqueConstraint
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


class Solicitud(SQLModel, table=True):
    """Cola durable. El worker reclama tareas mediante un lease temporal."""

    __tablename__ = "solicitud"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente', 'procesando', 'completada', "
            "'fallida', 'cancelada', 'vigilando')",
            name="ck_solicitud_estado",
        ),
        CheckConstraint("intentos >= 0 AND max_intentos > 0", name="ck_solicitud_intentos"),
        CheckConstraint("prioridad BETWEEN 0 AND 100", name="ck_solicitud_prioridad"),
    )

    id: int | None = Field(default=None, primary_key=True)
    perfil_id: int = Field(foreign_key="perfil.id", index=True)
    jellyfin_item_id: str = Field(max_length=128, index=True)
    titulo: str = Field(max_length=500)
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
