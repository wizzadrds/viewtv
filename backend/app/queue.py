"""Operaciones transaccionales de la cola durable de VIEWTV.

Cada operación de escritura empieza con BEGIN IMMEDIATE en SQLite. Esto serializa
los reclamadores y evita que dos workers obtengan la misma solicitud.
Las funciones requieren una Session sin una transacción previa activa.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, update
from sqlmodel import Session, select

from app.models import Solicitud

LEASE_SECONDS_DEFAULT = 120
RETRY_BASE_SECONDS_DEFAULT = 30
RETRY_MAX_SECONDS_DEFAULT = 30 * 60
ERROR_MAX_LENGTH = 4000


def _now(value: datetime | None) -> datetime:
    return value or datetime.now(UTC)


def _begin_write(session: Session) -> None:
    """Abre una transacción de escritura SQLite con bloqueo reservado inmediato."""
    if session.in_transaction():
        raise RuntimeError("Las operaciones de cola requieren una Session sin transacción activa")
    session.exec("BEGIN IMMEDIATE")


def _clear_lease_values() -> dict:
    return {
        "locked_by": None,
        "locked_until": None,
        "heartbeat": None,
    }


def _recover_expired_leases(session: Session, now: datetime) -> None:
    """Devuelve a la cola los trabajos abandonados o los marca como fallidos."""
    session.exec(
        update(Solicitud)
        .where(
            Solicitud.estado == "procesando",
            Solicitud.locked_until.is_not(None),
            Solicitud.locked_until <= now,
        )
        .values(
            estado=case(
                (Solicitud.intentos >= Solicitud.max_intentos, "fallida"),
                else_="pendiente",
            ),
            disponible_desde=now,
            actualizado_en=now,
            ultimo_error=func.coalesce(Solicitud.ultimo_error, "Lease caducado; trabajo recuperado"),
            **_clear_lease_values(),
        )
    )


def claim_next_request(
    session: Session,
    worker_id: str,
    *,
    lease_seconds: int = LEASE_SECONDS_DEFAULT,
    now: datetime | None = None,
) -> Solicitud | None:
    """Reclama la siguiente solicitud disponible y devuelve su lease."""
    if not worker_id or len(worker_id) > 128:
        raise ValueError("worker_id debe tener entre 1 y 128 caracteres")
    if lease_seconds <= 0:
        raise ValueError("lease_seconds debe ser mayor que cero")

    current_time = _now(now)
    _begin_write(session)
    try:
        _recover_expired_leases(session, current_time)
        request_id = session.exec(
            select(Solicitud.id)
            .where(
                Solicitud.estado == "pendiente",
                Solicitud.disponible_desde <= current_time,
            )
            .order_by(
                Solicitud.prioridad.desc(),
                Solicitud.creado_en.asc(),
                Solicitud.id.asc(),
            )
            .limit(1)
        ).first()

        if request_id is None:
            session.commit()
            return None

        result = session.exec(
            update(Solicitud)
            .where(Solicitud.id == request_id, Solicitud.estado == "pendiente")
            .values(
                estado="procesando",
                intentos=Solicitud.intentos + 1,
                locked_by=worker_id,
                locked_until=current_time + timedelta(seconds=lease_seconds),
                heartbeat=current_time,
                actualizado_en=current_time,
            )
        )
        if result.rowcount != 1:
            session.rollback()
            return None

        session.commit()
        return session.get(Solicitud, request_id)
    except Exception:
        session.rollback()
        raise


def renew_lease(
    session: Session,
    request_id: int,
    worker_id: str,
    *,
    lease_seconds: int = LEASE_SECONDS_DEFAULT,
    now: datetime | None = None,
) -> bool:
    """Renueva un lease vigente únicamente si pertenece al worker indicado."""
    if lease_seconds <= 0:
        raise ValueError("lease_seconds debe ser mayor que cero")
    current_time = _now(now)
    _begin_write(session)
    try:
        result = session.exec(
            update(Solicitud)
            .where(
                Solicitud.id == request_id,
                Solicitud.estado == "procesando",
                Solicitud.locked_by == worker_id,
                Solicitud.locked_until > current_time,
            )
            .values(
                locked_until=current_time + timedelta(seconds=lease_seconds),
                heartbeat=current_time,
                actualizado_en=current_time,
            )
        )
        session.commit()
        return result.rowcount == 1
    except Exception:
        session.rollback()
        raise


def complete_request(
    session: Session,
    request_id: int,
    worker_id: str,
    *,
    now: datetime | None = None,
) -> bool:
    """Marca una solicitud como completada si el worker aún posee el lease."""
    current_time = _now(now)
    _begin_write(session)
    try:
        result = session.exec(
            update(Solicitud)
            .where(
                Solicitud.id == request_id,
                Solicitud.estado == "procesando",
                Solicitud.locked_by == worker_id,
                Solicitud.locked_until > current_time,
            )
            .values(
                estado="completada",
                actualizado_en=current_time,
                **_clear_lease_values(),
            )
        )
        session.commit()
        return result.rowcount == 1
    except Exception:
        session.rollback()
        raise


def fail_request(
    session: Session,
    request_id: int,
    worker_id: str,
    error: str,
    *,
    retry_base_seconds: int = RETRY_BASE_SECONDS_DEFAULT,
    retry_max_seconds: int = RETRY_MAX_SECONDS_DEFAULT,
    now: datetime | None = None,
) -> bool:
    """Registra un fallo y programa reintento exponencial o fallo definitivo."""
    if retry_base_seconds <= 0 or retry_max_seconds < retry_base_seconds:
        raise ValueError("Los límites de reintento no son válidos")

    current_time = _now(now)
    _begin_write(session)
    try:
        request = session.exec(
            select(Solicitud).where(
                Solicitud.id == request_id,
                Solicitud.estado == "procesando",
                Solicitud.locked_by == worker_id,
                Solicitud.locked_until > current_time,
            )
        ).first()
        if request is None:
            session.rollback()
            return False

        terminal = request.intentos >= request.max_intentos
        delay = min(
            retry_base_seconds * (2 ** max(request.intentos - 1, 0)),
            retry_max_seconds,
        )
        result = session.exec(
            update(Solicitud)
            .where(
                Solicitud.id == request_id,
                Solicitud.estado == "procesando",
                Solicitud.locked_by == worker_id,
                Solicitud.locked_until > current_time,
            )
            .values(
                estado="fallida" if terminal else "pendiente",
                disponible_desde=current_time + timedelta(seconds=delay),
                actualizado_en=current_time,
                ultimo_error=(error or "Error no especificado")[:ERROR_MAX_LENGTH],
                **_clear_lease_values(),
            )
        )
        session.commit()
        return result.rowcount == 1
    except Exception:
        session.rollback()
        raise
