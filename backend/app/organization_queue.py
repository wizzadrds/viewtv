"""Cola durable de organización. NO copia ni mueve archivos.

Una futura implementación del ejecutor deberá reconciliar ficheros staged
antes de invocar confirm_organization. No se llama desde worker/main.py.
"""

from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import and_, or_, update
from sqlmodel import Session, select

from app.models import Descarga
from app.queue import _begin_write, _now

LEASE_SECONDS = 180
MAX_ATTEMPTS = 3
BASE_DELAY_SECONDS = 60
MAX_DELAY_SECONDS = 1800

FailureCode = Literal[
    "comunicacion",
    "archivo_invalido",
    "espacio_insuficiente",
    "origen_cambio",
    "otro",
]
FAILURE_CODES = frozenset(
    {"comunicacion", "archivo_invalido", "espacio_insuficiente", "origen_cambio", "otro"}
)


def _worker(worker_id: str) -> None:
    if not isinstance(worker_id, str) or not worker_id.strip() or len(worker_id) > 128:
        raise ValueError("Identidad de worker inválida.")


def _id(download_id: int) -> None:
    if isinstance(download_id, bool) or not isinstance(download_id, int) or download_id <= 0:
        raise ValueError("ID de descarga inválido.")


def _reason(code: FailureCode) -> None:
    if not isinstance(code, str) or code not in FAILURE_CODES:
        raise ValueError("Código de error no reconocido.")


def claim_next_organization(
    session: Session,
    worker_id: str,
    *,
    now: datetime | None = None,
) -> Descarga | None:
    """Reclamación exclusiva; un lease agotado tras 3 intentos va a revisión."""
    _worker(worker_id)
    current = _now(now)

    _begin_write(session)
    try:
        conditions = (
            Descarga.estado == "completada",
            Descarga.progreso == 1,
            Descarga.estado_verificacion == "verificada",
            Descarga.organizacion_estado == "pendiente",
            or_(
                Descarga.organizacion_disponible_desde.is_(None),
                Descarga.organizacion_disponible_desde <= current,
            ),
            or_(
                and_(
                    Descarga.organizacion_locked_by.is_(None),
                    Descarga.organizacion_locked_until.is_(None),
                ),
                Descarga.organizacion_locked_until <= current,
            ),
        )

        candidate = session.exec(
            select(Descarga).where(*conditions).order_by(Descarga.id.asc()).limit(1)
        ).first()
        if candidate is None:
            session.commit()
            return None

        if candidate.organizacion_intentos >= MAX_ATTEMPTS:
            session.exec(
                update(Descarga)
                .where(Descarga.id == candidate.id, *conditions)
                .values(
                    organizacion_estado="requiere_revision",
                    organizacion_locked_by=None,
                    organizacion_locked_until=None,
                    organizacion_disponible_desde=None,
                    organizacion_ultimo_error="lease_agotado",
                    actualizado_en=current,
                )
            )
            session.commit()
            return None

        result = session.exec(
            update(Descarga)
            .where(Descarga.id == candidate.id, *conditions)
            .values(
                organizacion_locked_by=worker_id,
                organizacion_locked_until=current + timedelta(seconds=LEASE_SECONDS),
                organizacion_intentos=Descarga.organizacion_intentos + 1,
                actualizado_en=current,
            )
        )
        if result.rowcount != 1:
            session.rollback()
            return None
        session.commit()
        return session.get(Descarga, candidate.id)
    except Exception:
        session.rollback()
        raise


def _claimed_conditions(download_id: int, worker_id: str, current: datetime) -> tuple:
    return (
        Descarga.id == download_id,
        Descarga.estado == "completada",
        Descarga.progreso == 1,
        Descarga.estado_verificacion == "verificada",
        Descarga.organizacion_estado == "pendiente",
        Descarga.organizacion_locked_by == worker_id,
        Descarga.organizacion_locked_until > current,
    )


def confirm_organization(
    session: Session, download_id: int, worker_id: str, *, now: datetime | None = None
) -> bool:
    """Solo el dueño de un lease vivo puede registrar una publicación comprobada."""
    _id(download_id)
    _worker(worker_id)
    current = _now(now)
    _begin_write(session)
    try:
        result = session.exec(
            update(Descarga)
            .where(*_claimed_conditions(download_id, worker_id, current))
            .values(
                organizacion_estado="organizada",
                organizacion_locked_by=None,
                organizacion_locked_until=None,
                organizacion_disponible_desde=None,
                organizacion_ultimo_error=None,
                actualizado_en=current,
            )
        )
        session.commit()
        return result.rowcount == 1
    except Exception:
        session.rollback()
        raise


def mark_organization_review(
    session: Session,
    download_id: int,
    worker_id: str,
    reason: FailureCode,
    *,
    now: datetime | None = None,
) -> bool:
    """Detener reintentos de forma conservadora ante un conflicto real."""
    _id(download_id)
    _worker(worker_id)
    _reason(reason)
    current = _now(now)
    _begin_write(session)
    try:
        result = session.exec(
            update(Descarga)
            .where(*_claimed_conditions(download_id, worker_id, current))
            .values(
                organizacion_estado="requiere_revision",
                organizacion_locked_by=None,
                organizacion_locked_until=None,
                organizacion_disponible_desde=None,
                organizacion_ultimo_error=reason,
                actualizado_en=current,
            )
        )
        session.commit()
        return result.rowcount == 1
    except Exception:
        session.rollback()
        raise


def defer_organization(
    session: Session,
    download_id: int,
    worker_id: str,
    reason: FailureCode,
    *,
    now: datetime | None = None,
) -> bool:
    """Aplaza con reintentos limitados; no duplica operaciones externas."""
    _id(download_id)
    _worker(worker_id)
    _reason(reason)
    current = _now(now)
    _begin_write(session)
    try:
        download = session.exec(
            select(Descarga).where(*_claimed_conditions(download_id, worker_id, current))
        ).first()
        if download is None:
            session.commit()
            return False

        needs_review = download.organizacion_intentos >= MAX_ATTEMPTS
        delay = min(
            BASE_DELAY_SECONDS * 2 ** max(download.organizacion_intentos - 1, 0),
            MAX_DELAY_SECONDS,
        )
        result = session.exec(
            update(Descarga)
            .where(*_claimed_conditions(download_id, worker_id, current))
            .values(
                organizacion_estado="requiere_revision" if needs_review else "pendiente",
                organizacion_locked_by=None,
                organizacion_locked_until=None,
                organizacion_disponible_desde=(
                    None if needs_review else current + timedelta(seconds=delay)
                ),
                organizacion_ultimo_error=reason,
                actualizado_en=current,
            )
        )
        session.commit()
        return result.rowcount == 1
    except Exception:
        session.rollback()
        raise
