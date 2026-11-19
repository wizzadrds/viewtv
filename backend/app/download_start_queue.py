"""Coordinación durable de órdenes de inicio de torrents."""

from datetime import timedelta

from sqlalchemy import and_, or_, update
from sqlmodel import Session, select

from app.models import Descarga
from app.queue import _begin_write, _now

LEASE_SECONDS = 90
RETRY_SECONDS = 60
MAX_RETRY_SECONDS = 1800


def claim_next_start(session: Session, worker_id: str, *, now=None):
    """Reclama un inicio pendiente mediante una escritura exclusiva."""
    if not worker_id or len(worker_id) > 128:
        raise ValueError("Identidad de worker no válida.")

    current = _now(now)
    _begin_write(session)
    try:
        download_id = session.exec(
            select(Descarga.id)
            .where(
                Descarga.estado == "enviada",
                Descarga.inicio_estado == "pendiente",
                Descarga.qbittorrent_hash.is_not(None),
                or_(
                    Descarga.inicio_disponible_desde.is_(None),
                    Descarga.inicio_disponible_desde <= current,
                ),
                or_(
                    and_(
                        Descarga.inicio_locked_by.is_(None),
                        Descarga.inicio_locked_until.is_(None),
                    ),
                    Descarga.inicio_locked_until <= current,
                ),
            )
            .order_by(Descarga.id.asc())
            .limit(1)
        ).first()

        if download_id is None:
            session.commit()
            return None

        updated = session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.estado == "enviada",
                Descarga.inicio_estado == "pendiente",
                Descarga.qbittorrent_hash.is_not(None),
                or_(
                    Descarga.inicio_disponible_desde.is_(None),
                    Descarga.inicio_disponible_desde <= current,
                ),
                or_(
                    and_(
                        Descarga.inicio_locked_by.is_(None),
                        Descarga.inicio_locked_until.is_(None),
                    ),
                    Descarga.inicio_locked_until <= current,
                ),
            )
            .values(
                inicio_locked_by=worker_id,
                inicio_locked_until=current + timedelta(
                    seconds=LEASE_SECONDS
                ),
                inicio_intentos=Descarga.inicio_intentos + 1,
                actualizado_en=current,
            )
        )
        if updated.rowcount != 1:
            session.rollback()
            return None

        session.commit()
        return session.get(Descarga, download_id)
    except Exception:
        session.rollback()
        raise


def confirm_start_command(
    session: Session,
    download_id: int,
    worker_id: str,
    *,
    now=None,
) -> bool:
    """Registra aceptación de la orden; no acredita transferencia."""
    current = _now(now)
    _begin_write(session)
    try:
        updated = session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.inicio_estado == "pendiente",
                Descarga.inicio_locked_by == worker_id,
                Descarga.inicio_locked_until > current,
            )
            .values(
                inicio_estado="iniciada",
                inicio_locked_by=None,
                inicio_locked_until=None,
                inicio_disponible_desde=None,
                actualizado_en=current,
            )
        )
        session.commit()
        return updated.rowcount == 1
    except Exception:
        session.rollback()
        raise



def mark_start_needs_review(
    session: Session,
    download_id: int,
    worker_id: str,
    *,
    now=None,
) -> bool:
    """Finaliza la conciliación ambigua sin reanudar el torrent."""
    current = _now(now)
    _begin_write(session)
    try:
        updated = session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.estado == "enviada",
                Descarga.inicio_estado == "pendiente",
                Descarga.inicio_locked_by == worker_id,
                Descarga.inicio_locked_until > current,
            )
            .values(
                inicio_estado="requiere_revision",
                inicio_locked_by=None,
                inicio_locked_until=None,
                inicio_disponible_desde=None,
                actualizado_en=current,
            )
        )
        session.commit()
        return updated.rowcount == 1
    except Exception:
        session.rollback()
        raise

def defer_start_command(
    session: Session,
    download_id: int,
    worker_id: str,
    *,
    now=None,
) -> bool:
    """Aplaza un inicio reclamado sin reenviar el torrent."""
    current = _now(now)
    _begin_write(session)
    try:
        download = session.exec(
            select(Descarga).where(
                Descarga.id == download_id,
                Descarga.inicio_estado == "pendiente",
                Descarga.inicio_locked_by == worker_id,
                Descarga.inicio_locked_until > current,
            )
        ).first()

        if download is None:
            session.rollback()
            return False

        delay = min(
            RETRY_SECONDS
            * (2 ** min(max(download.inicio_intentos - 1, 0), 10)),
            MAX_RETRY_SECONDS,
        )

        updated = session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.inicio_estado == "pendiente",
                Descarga.inicio_locked_by == worker_id,
                Descarga.inicio_locked_until > current,
            )
            .values(
                inicio_locked_by=None,
                inicio_locked_until=None,
                inicio_disponible_desde=current + timedelta(
                    seconds=delay
                ),
                actualizado_en=current,
            )
        )
        session.commit()
        return updated.rowcount == 1
    except Exception:
        session.rollback()
        raise
