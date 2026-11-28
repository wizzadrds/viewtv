"""Modo automático: solo descargas seleccionadas DESPUÉS de la activación.

Se procesa como máximo una transferencia VIEWTV activa. Las descargas
históricas, descartadas, fallidas o pausadas manualmente nunca se
reanudan sin más. Todas las operaciones reales conservan ID y staging.
"""
import re

from app.models import Descarga
from sqlmodel import Session, select


def parse_auto_floor(value: str) -> int | None:
    """IDs superiores al valor de activación; 0 sirve para una DB vacía."""
    raw = value.strip()
    if re.fullmatch(r"0|[1-9][0-9]{0,17}", raw) is None:
        return None
    floor = int(raw)
    return floor if floor < 2**63 - 1 else None


def next_auto_download_id(session: Session, *, after_id: int) -> int | None:
    """Prioriza trabajos en curso y luego un nuevo seleccionado.

    Una pausa manual ocupa el turno y NO se reanuda aquí, para evitar
    arrancar otras descargas saltando por encima de la intervención.
    """
    if not isinstance(after_id, int) or isinstance(after_id, bool) or after_id < 0:
        raise ValueError("Umbral de activación no válido")

    eligible = (
        Descarga.id > after_id,
        Descarga.resultado_busqueda_id.is_not(None),
        Descarga.info_hash.is_not(None),
    )
    active = session.exec(
        select(Descarga.id)
        .where(
            *eligible,
            Descarga.estado.in_(("enviada", "descargando", "pausada")),
        )
        .order_by(Descarga.id.asc())
        .limit(1)
    ).first()
    if active is not None:
        return active

    return session.exec(
        select(Descarga.id)
        .where(*eligible, Descarga.estado == "seleccionada")
        .order_by(Descarga.id.asc())
        .limit(1)
    ).first()
