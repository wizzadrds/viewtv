"""Operaciones transaccionales de la cola durable de VIEWTV.

Cada operación de escritura empieza con BEGIN IMMEDIATE en SQLite. Esto serializa
los reclamadores y evita que dos workers obtengan la misma solicitud.
Las funciones requieren una Session sin una transacción previa activa.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete, func, or_, text, update
from sqlmodel import Session, select

from app.models import Descarga, ResultadoBusqueda, Solicitud

LEASE_SECONDS_DEFAULT = 120
RETRY_BASE_SECONDS_DEFAULT = 30
RETRY_MAX_SECONDS_DEFAULT = 30 * 60
ERROR_MAX_LENGTH = 4000


def _now(value: datetime | None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        raise ValueError("Las fechas de la cola deben incluir zona horaria")
    return current.astimezone(UTC)


def _begin_write(session: Session) -> None:
    """Abre una transacción SQLite inmediata sin descartar cambios del llamador."""
    if session.in_transaction():
        if session.new or session.dirty or session.deleted:
            raise RuntimeError("Confirma o revierte los cambios pendientes antes de usar la cola")
        # Una lectura ORM puede dejar una transacción lógica abierta. Se cierra
        # únicamente si no contiene cambios pendientes del llamador.
        session.rollback()
    session.exec(text("BEGIN IMMEDIATE"))


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
            ultimo_error=func.coalesce(
                Solicitud.ultimo_error,
                "Lease caducado; trabajo recuperado",
            ),
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

def finish_search_request(
    session: Session,
    request_id: int,
    worker_id: str,
    results: list[ResultadoBusqueda],
    *,
    now: datetime | None = None,
) -> bool:
    """Guarda resultados y libera el lease de una búsqueda vigente."""
    current_time = _now(now)

    if any(result.solicitud_id != request_id for result in results):
        raise ValueError("Todos los resultados deben pertenecer a la solicitud")

    _begin_write(session)
    try:
        owned_request = session.exec(
            select(Solicitud.id).where(
                Solicitud.id == request_id,
                Solicitud.estado == "procesando",
                Solicitud.locked_by == worker_id,
                Solicitud.locked_until > current_time,
            )
        ).first()

        if owned_request is None:
            session.rollback()
            return False

        session.exec(
            delete(ResultadoBusqueda).where(
                ResultadoBusqueda.solicitud_id == request_id
            )
        )

        session.add_all(results)

        updated = session.exec(
            update(Solicitud)
            .where(
                Solicitud.id == request_id,
                Solicitud.estado == "procesando",
                Solicitud.locked_by == worker_id,
                Solicitud.locked_until > current_time,
            )
            .values(
                estado="esperando_seleccion" if results else "sin_resultados",
                actualizado_en=current_time,
                **_clear_lease_values(),
            )
        )

        if updated.rowcount != 1:
            session.rollback()
            return False

        session.commit()
        return True
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



def get_queue_counts(session: Session) -> dict[str, int]:
    """Devuelve el número de solicitudes por estado sin modificar la cola."""
    rows = session.exec(
        select(Solicitud.estado, func.count(Solicitud.id)).group_by(Solicitud.estado)
    ).all()
    counts = {
        "pendiente": 0,
        "procesando": 0,
        "completada": 0,
        "fallida": 0,
        "cancelada": 0,
        "vigilando": 0,
	"esperando_seleccion": 0,
	"sin_resultados": 0,
    }
    counts.update({estado: total for estado, total in rows})
    return counts

def claim_next_download(
    session: Session,
    worker_id: str,
    *,
    lease_seconds: int = LEASE_SECONDS_DEFAULT,
    now: datetime | None = None,
) -> Descarga | None:
    """Reclama una descarga seleccionada sin consumir intentos de envío."""
    if not worker_id or len(worker_id) > 128:
        raise ValueError("worker_id debe tener entre 1 y 128 caracteres")
    if lease_seconds <= 0:
        raise ValueError("lease_seconds debe ser mayor que cero")

    current_time = _now(now)
    _begin_write(session)
    try:
        download_id = session.exec(
            select(Descarga.id)
            .where(
                Descarga.estado == "seleccionada",
                Descarga.disponible_desde <= current_time,
                or_(
                    (
                        Descarga.locked_by.is_(None)
                        & Descarga.locked_until.is_(None)
                    ),
                    Descarga.locked_until <= current_time,
                ),
            )
            .order_by(
                Descarga.disponible_desde.asc(),
                Descarga.creado_en.asc(),
                Descarga.id.asc(),
            )
            .limit(1)
        ).first()

        if download_id is None:
            session.commit()
            return None

        result = session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.estado == "seleccionada",
                or_(
                    (
                        Descarga.locked_by.is_(None)
                        & Descarga.locked_until.is_(None)
                    ),
                    Descarga.locked_until <= current_time,
                ),
            )
            .values(
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
        return session.get(Descarga, download_id)
    except Exception:
        session.rollback()
        raise


def renew_download_lease(
    session: Session,
    download_id: int,
    worker_id: str,
    *,
    lease_seconds: int = LEASE_SECONDS_DEFAULT,
    now: datetime | None = None,
) -> bool:
    """Renueva el lease de una descarga seleccionada."""
    if lease_seconds <= 0:
        raise ValueError("lease_seconds debe ser mayor que cero")

    current_time = _now(now)
    _begin_write(session)
    try:
        result = session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.estado == "seleccionada",
                Descarga.locked_by == worker_id,
                Descarga.locked_until > current_time,
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


def record_download_attempt(
    session: Session,
    download_id: int,
    worker_id: str,
    *,
    now: datetime | None = None,
) -> bool:
    """Consume un intento justo antes de enviar el torrent."""
    current_time = _now(now)
    _begin_write(session)
    try:
        result = session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.estado == "seleccionada",
                Descarga.locked_by == worker_id,
                Descarga.locked_until > current_time,
                Descarga.intentos_envio < Descarga.max_intentos_envio,
            )
            .values(
                intentos_envio=Descarga.intentos_envio + 1,
                heartbeat=current_time,
                actualizado_en=current_time,
            )
        )
        session.commit()
        return result.rowcount == 1
    except Exception:
        session.rollback()
        raise


def mark_download_submitted(
    session: Session,
    download_id: int,
    worker_id: str,
    qbittorrent_hash: str,
    *,
    now: datetime | None = None,
) -> bool:
    """Confirma que qBittorrent ya contiene el torrent y libera el lease."""
    if not qbittorrent_hash or len(qbittorrent_hash) > 128:
        raise ValueError("qbittorrent_hash no es válido")

    current_time = _now(now)
    _begin_write(session)
    try:
        result = session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.estado == "seleccionada",
                Descarga.locked_by == worker_id,
                Descarga.locked_until > current_time,
            )
            .values(
                estado="enviada",
                qbittorrent_hash=qbittorrent_hash,
                ultimo_error=None,
                actualizado_en=current_time,
                **_clear_lease_values(),
            )
        )
        session.commit()
        return result.rowcount == 1
    except Exception:
        session.rollback()
        raise


def fail_download(
    session: Session,
    download_id: int,
    worker_id: str,
    error: str,
    *,
    retry_base_seconds: int = RETRY_BASE_SECONDS_DEFAULT,
    retry_max_seconds: int = RETRY_MAX_SECONDS_DEFAULT,
    permanent: bool = False,
    now: datetime | None = None,
) -> bool:
    """Reintenta el envío o reabre la selección al agotar los intentos."""
    if retry_base_seconds <= 0 or retry_max_seconds < retry_base_seconds:
        raise ValueError("Los límites de reintento no son válidos")

    current_time = _now(now)
    _begin_write(session)
    try:
        download = session.exec(
            select(Descarga).where(
                Descarga.id == download_id,
                Descarga.estado == "seleccionada",
                Descarga.locked_by == worker_id,
                Descarga.locked_until > current_time,
            )
        ).first()

        if download is None:
            session.rollback()
            return False

        terminal = permanent or (
            download.intentos_envio >= download.max_intentos_envio
        )
        error_message = (error or "Error no especificado")[:ERROR_MAX_LENGTH]

        delay = min(
            retry_base_seconds * (2 ** max(download.intentos_envio - 1, 0)),
            retry_max_seconds,
        )

        result = session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.estado == "seleccionada",
                Descarga.locked_by == worker_id,
                Descarga.locked_until > current_time,
            )
            .values(
                estado="fallida" if terminal else "seleccionada",
                disponible_desde=current_time + timedelta(seconds=delay),
                ultimo_error=error_message,
                actualizado_en=current_time,
                **_clear_lease_values(),
            )
        )

        if result.rowcount != 1:
            session.rollback()
            return False

        if terminal:
            session.exec(
                update(Solicitud)
                .where(
                    Solicitud.id == download.solicitud_id,
                    Solicitud.estado == "completada",
                )
                .values(
                    estado="esperando_seleccion",
                    ultimo_error=error_message,
                    actualizado_en=current_time,
                    **_clear_lease_values(),
                )
            )

        session.commit()
        return True
    except Exception:
        session.rollback()
        raise



def update_download_progress(
    session: Session,
    download_id: int,
    qbittorrent_hash: str,
    estado: str,
    progreso: float,
    tamano_bytes: int | None = None,
    *,
    now: datetime | None = None,
) -> bool:
    """Actualiza una descarga identificada sin alterar estados terminales."""
    import math

    if estado not in {"enviada", "descargando", "pausada", "completada"}:
        raise ValueError("Estado de descarga no válido")

    if (
        isinstance(progreso, bool)
        or not isinstance(progreso, (int, float))
        or not math.isfinite(progreso)
        or not 0 <= progreso <= 1
    ):
        raise ValueError("Progreso de descarga no válido")

    if tamano_bytes is not None and (
        isinstance(tamano_bytes, bool)
        or not isinstance(tamano_bytes, int)
        or tamano_bytes < 0
    ):
        raise ValueError("Tamaño de descarga no válido")

    if estado == "completada" and progreso != 1:
        raise ValueError("Una descarga completada requiere progreso 1")

    if not qbittorrent_hash:
        raise ValueError("Falta el hash del torrent")

    current_time = _now(now)
    _begin_write(session)

    try:
        descarga = session.exec(
            select(Descarga).where(
                Descarga.id == download_id,
                Descarga.qbittorrent_hash == qbittorrent_hash,
                Descarga.estado.in_(
                    ["enviada", "descargando", "pausada"]
                ),
            )
        ).first()

        if descarga is None:
            session.commit()
            return False

        if progreso < descarga.progreso:
            session.commit()
            return False

        # Una lectura atrasada no debe devolver una descarga activa
        # al estado inicial de envio.
        if descarga.estado in {"descargando", "pausada"} and estado == "enviada":
            session.commit()
            return False

        nuevo_tamano = (
            tamano_bytes
            if tamano_bytes is not None
            else descarga.tamano_bytes
        )

        if (
            descarga.estado == estado
            and descarga.progreso == progreso
            and descarga.tamano_bytes == nuevo_tamano
        ):
            session.commit()
            return False

        session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.qbittorrent_hash == qbittorrent_hash,
                Descarga.estado.in_(
                    ["enviada", "descargando", "pausada"]
                ),
            )
            .values(
                estado=estado,
                progreso=progreso,
                tamano_bytes=nuevo_tamano,
                actualizado_en=current_time,
            )
        )

        session.commit()
        return True

    except Exception:
        session.rollback()
        raise



def claim_next_verification(
    session: Session,
    worker_id: str,
    *,
    lease_seconds: int = LEASE_SECONDS_DEFAULT,
    now: datetime | None = None,
) -> Descarga | None:
    """Reclama exclusivamente una verificación pendiente o recuperable."""
    if not worker_id or len(worker_id) > 128:
        raise ValueError("worker_id debe tener entre 1 y 128 caracteres")
    if lease_seconds <= 0:
        raise ValueError("lease_seconds debe ser mayor que cero")

    current_time = _now(now)
    _begin_write(session)

    try:
        condiciones = (
            Descarga.estado == "completada",
            Descarga.progreso == 1,
            Descarga.estado_verificacion == "pendiente",
            Descarga.qbittorrent_hash.is_not(None),
            or_(
                Descarga.verificacion_disponible_desde.is_(None),
                Descarga.verificacion_disponible_desde <= current_time,
            ),
            or_(
                (
                    Descarga.verificacion_locked_by.is_(None)
                    & Descarga.verificacion_locked_until.is_(None)
                ),
                Descarga.verificacion_locked_until <= current_time,
            ),
        )

        download_id = session.exec(
            select(Descarga.id)
            .where(*condiciones)
            .order_by(
                Descarga.verificacion_disponible_desde.asc(),
                Descarga.creado_en.asc(),
                Descarga.id.asc(),
            )
            .limit(1)
        ).first()

        if download_id is None:
            session.commit()
            return None

        result = session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                *condiciones,
            )
            .values(
                verificacion_locked_by=worker_id,
                verificacion_locked_until=(
                    current_time + timedelta(seconds=lease_seconds)
                ),
                verificacion_heartbeat=current_time,
                actualizado_en=current_time,
            )
        )

        if result.rowcount != 1:
            session.rollback()
            return None

        session.commit()
        return session.get(Descarga, download_id)

    except Exception:
        session.rollback()
        raise



def renew_verification_lease(
    session: Session,
    download_id: int,
    worker_id: str,
    *,
    lease_seconds: int = LEASE_SECONDS_DEFAULT,
    now: datetime | None = None,
) -> bool:
    """Renueva únicamente una reclamación de verificación vigente."""
    if (
        isinstance(download_id, bool)
        or not isinstance(download_id, int)
        or download_id <= 0
    ):
        raise ValueError("Identificador de descarga no válido")

    if (
        not isinstance(worker_id, str)
        or not worker_id
        or len(worker_id) > 128
    ):
        raise ValueError("worker_id debe tener entre 1 y 128 caracteres")

    if (
        isinstance(lease_seconds, bool)
        or not isinstance(lease_seconds, int)
        or lease_seconds <= 0
    ):
        raise ValueError("lease_seconds debe ser positivo")

    current_time = _now(now)
    _begin_write(session)

    try:
        result = session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.estado == "completada",
                Descarga.progreso == 1,
                Descarga.estado_verificacion == "pendiente",
                Descarga.verificacion_locked_by == worker_id,
                Descarga.verificacion_locked_until > current_time,
            )
            .values(
                verificacion_locked_until=(
                    current_time + timedelta(seconds=lease_seconds)
                ),
                verificacion_heartbeat=current_time,
                actualizado_en=current_time,
            )
        )

        session.commit()
        return result.rowcount == 1

    except Exception:
        session.rollback()
        raise




def finish_claimed_verification(
    session: Session,
    download_id: int,
    qbittorrent_hash: str,
    worker_id: str,
    *,
    verified: bool,
    error: str | None = None,
    now: datetime | None = None,
) -> bool:
    """Finaliza una verificación solo con un lease vigente y propio."""
    if (
        isinstance(download_id, bool)
        or not isinstance(download_id, int)
        or download_id <= 0
    ):
        raise ValueError("Identificador de descarga no válido")

    if not isinstance(qbittorrent_hash, str) or not qbittorrent_hash.strip():
        raise ValueError("Hash de qBittorrent no válido")

    if (
        not isinstance(worker_id, str)
        or not worker_id
        or len(worker_id) > 128
    ):
        raise ValueError("worker_id no válido")

    if not isinstance(verified, bool):
        raise ValueError("Resultado de verificación no válido")

    if verified:
        if error is not None:
            raise ValueError("Una verificación correcta no admite error")
        nuevo_estado = "verificada"
        nuevo_error = None
    else:
        if not isinstance(error, str) or not error.strip():
            raise ValueError("Una verificación fallida requiere un error")
        nuevo_estado = "fallida"
        nuevo_error = error.strip()[:ERROR_MAX_LENGTH]

    current_time = _now(now)
    _begin_write(session)

    try:
        result = session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.qbittorrent_hash == qbittorrent_hash,
                Descarga.estado == "completada",
                Descarga.progreso == 1,
                Descarga.estado_verificacion == "pendiente",
                Descarga.verificacion_locked_by == worker_id,
                Descarga.verificacion_locked_until > current_time,
            )
            .values(
                estado_verificacion=nuevo_estado,
                verificada_en=current_time if verified else None,
                error_verificacion=nuevo_error,
                verificacion_locked_by=None,
                verificacion_locked_until=None,
                verificacion_heartbeat=None,
                verificacion_disponible_desde=None,
                actualizado_en=current_time,
            )
        )
        session.commit()
        return result.rowcount == 1

    except Exception:
        session.rollback()
        raise



def record_download_verification(
    session: Session,
    download_id: int,
    qbittorrent_hash: str,
    *,
    verified: bool,
    error: str | None = None,
    now: datetime | None = None,
) -> bool:
    """Registra una verificación sin alterar el estado de descarga."""
    if (
        isinstance(download_id, bool)
        or not isinstance(download_id, int)
        or download_id <= 0
    ):
        raise ValueError("Identificador de descarga no válido")

    if not isinstance(qbittorrent_hash, str) or not qbittorrent_hash.strip():
        raise ValueError("Hash de qBittorrent no válido")

    if not isinstance(verified, bool):
        raise ValueError("Resultado de verificación no válido")

    if verified:
        if error is not None:
            raise ValueError("Una verificación correcta no admite error")
        nuevo_estado = "verificada"
        nuevo_error = None
    else:
        if not isinstance(error, str) or not error.strip():
            raise ValueError("Una verificación fallida requiere un error")
        nuevo_estado = "fallida"
        nuevo_error = error.strip()[:ERROR_MAX_LENGTH]

    current_time = _now(now)
    _begin_write(session)

    try:
        descarga = session.exec(
            select(Descarga).where(
                Descarga.id == download_id,
                Descarga.qbittorrent_hash == qbittorrent_hash,
                Descarga.estado == "completada",
                Descarga.progreso == 1,
            )
        ).first()

        if descarga is None:
            session.commit()
            return False

        # Una verificación correcta es terminal para este registro.
        if descarga.estado_verificacion == "verificada":
            session.commit()
            return False

        if (
            descarga.estado_verificacion == nuevo_estado
            and descarga.error_verificacion == nuevo_error
        ):
            session.commit()
            return False

        session.exec(
            update(Descarga)
            .where(
                Descarga.id == download_id,
                Descarga.qbittorrent_hash == qbittorrent_hash,
                Descarga.estado == "completada",
                Descarga.progreso == 1,
                Descarga.estado_verificacion != "verificada",
            )
            .values(
                estado_verificacion=nuevo_estado,
                verificada_en=current_time if verified else None,
                error_verificacion=nuevo_error,
                actualizado_en=current_time,
            )
        )

        session.commit()
        return True

    except Exception:
        session.rollback()
        raise
