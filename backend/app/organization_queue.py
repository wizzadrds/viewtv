"""Cola durable de organización. NO copia ni mueve archivos.

Una futura implementación del ejecutor deberá reconciliar ficheros staged
antes de invocar confirm_organization. No se llama desde worker/main.py.
"""

from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import and_, case, or_, update
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


def _attempt(expected_attempt: int | None) -> None:
    if expected_attempt is not None and (
        isinstance(expected_attempt, bool)
        or not isinstance(expected_attempt, int)
        or not 1 <= expected_attempt <= MAX_ATTEMPTS
    ):
        raise ValueError("Número de intento de organización inválido.")


def claim_next_organization(
    session: Session,
    worker_id: str,
    *,
    now: datetime | None = None,
    allowed_download_id: int | None = None,
) -> Descarga | None:
    """Reclamación exclusiva, opcionalmente restringida a una sola descarga."""
    _worker(worker_id)
    if allowed_download_id is not None:
        _id(allowed_download_id)
        if allowed_download_id > 2**63 - 1:
            raise ValueError("ID de descarga fuera de rango SQLite.")
    current = _now(now)

    _begin_write(session)
    try:
        conditions = (
            *((Descarga.id == allowed_download_id,) if allowed_download_id is not None else ()),
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


def _claimed_conditions(
    download_id: int,
    worker_id: str,
    current: datetime,
    *,
    expected_attempt: int | None = None,
) -> tuple:
    _attempt(expected_attempt)
    conditions = (
        Descarga.id == download_id,
        Descarga.estado == "completada",
        Descarga.progreso == 1,
        Descarga.estado_verificacion == "verificada",
        Descarga.organizacion_estado == "pendiente",
        Descarga.organizacion_locked_by == worker_id,
        Descarga.organizacion_locked_until > current,
    )
    if expected_attempt is not None:
        conditions += (Descarga.organizacion_intentos == expected_attempt,)
    return conditions


def renew_organization_lease(
    session: Session,
    download_id: int,
    worker_id: str,
    *,
    lease_seconds: int = LEASE_SECONDS,
    now: datetime | None = None,
    expected_attempt: int | None = None,
) -> bool:
    """Extender solo un lease propio todavía válido; no reanimar caducados."""
    _id(download_id)
    _worker(worker_id)
    _attempt(expected_attempt)
    if (
        isinstance(lease_seconds, bool)
        or not isinstance(lease_seconds, int)
        or not 1 <= lease_seconds <= 900
    ):
        raise ValueError("Duración del lease inválida.")

    current = _now(now)
    new_expiry = current + timedelta(seconds=lease_seconds)
    _begin_write(session)
    try:
        result = session.exec(
            update(Descarga)
            .where(
                *_claimed_conditions(
                    download_id, worker_id, current, expected_attempt=expected_attempt
                )
            )
            .values(
                organizacion_locked_until=case(
                    (
                        Descarga.organizacion_locked_until > new_expiry,
                        Descarga.organizacion_locked_until,
                    ),
                    else_=new_expiry,
                ),
                actualizado_en=current,
            )
        )
        session.commit()
        return result.rowcount == 1
    except Exception:
        session.rollback()
        raise


def confirm_organization(
    session: Session,
    download_id: int,
    worker_id: str,
    *,
    now: datetime | None = None,
    expected_attempt: int | None = None,
) -> bool:
    """Solo el dueño de un lease vivo puede registrar una publicación comprobada."""
    _id(download_id)
    _worker(worker_id)
    _attempt(expected_attempt)
    current = _now(now)
    _begin_write(session)
    try:
        result = session.exec(
            update(Descarga)
            .where(
                *_claimed_conditions(
                    download_id, worker_id, current, expected_attempt=expected_attempt
                )
            )
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
    expected_attempt: int | None = None,
) -> bool:
    """Detener reintentos de forma conservadora ante un conflicto real."""
    _id(download_id)
    _worker(worker_id)
    _reason(reason)
    _attempt(expected_attempt)
    current = _now(now)
    _begin_write(session)
    try:
        result = session.exec(
            update(Descarga)
            .where(
                *_claimed_conditions(
                    download_id, worker_id, current, expected_attempt=expected_attempt
                )
            )
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
    expected_attempt: int | None = None,
) -> bool:
    """Aplaza con reintentos limitados; no duplica operaciones externas."""
    _id(download_id)
    _worker(worker_id)
    _reason(reason)
    _attempt(expected_attempt)
    current = _now(now)
    _begin_write(session)
    try:
        download = session.exec(
            select(Descarga).where(
                *_claimed_conditions(
                    download_id, worker_id, current, expected_attempt=expected_attempt
                )
            )
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
            .where(
                *_claimed_conditions(
                    download_id, worker_id, current, expected_attempt=expected_attempt
                )
            )
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
