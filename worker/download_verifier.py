"""Coordinación de verificaciones pendientes de descargas."""

import logging
from pathlib import Path

from app.database import engine
from app.models import Descarga
from app.qbittorrent import QBittorrentClient, QBittorrentError
from sqlmodel import Session, select

from worker.completed_files import verify_completed_files
from worker.file_validator import InvalidTorrentFiles
from worker.verification_heartbeat import VerificationHeartbeat

logger = logging.getLogger("viewtv.download_verifier")

DOWNLOAD_ROOT = Path("/media/descargas_temporales")


def new_verification_worker_id() -> str:
    """Genera una identidad distinta para cada ejecución."""
    from uuid import uuid4

    return f"verification-{uuid4().hex}"


def process_one_verification(
    worker_id: str,
    client: QBittorrentClient | None = None,
    media_root: Path = DOWNLOAD_ROOT,
) -> bool:
    """Verifica un trabajo con lease y heartbeat independientes."""
    from app.queue import (
        claim_next_verification,
        defer_claimed_verification,
        finish_claimed_verification,
    )

    qbittorrent = client if client is not None else QBittorrentClient()

    with Session(engine) as session:
        descarga = claim_next_verification(session, worker_id)

        if descarga is None:
            return False

        download_id = descarga.id
        torrent_hash = descarga.qbittorrent_hash

    if download_id is None or not torrent_hash:
        return True

    resultado = "correcta"
    error = None

    with VerificationHeartbeat(
        engine,
        download_id,
        worker_id,
    ) as heartbeat:
        try:
            verify_completed_files(
                qbittorrent,
                torrent_hash,
                media_root,
            )
        except QBittorrentError:
            resultado = "aplazar"
            logger.warning(
                "Error de comunicación al verificar descarga %s",
                download_id,
            )
        except (InvalidTorrentFiles, OSError) as exc:
            resultado = "fallida"
            error = str(exc)
            logger.warning(
                "Verificación fallida de descarga %s: %s",
                download_id,
                exc,
            )
        except Exception:
            resultado = "aplazar"
            logger.exception(
                "Error inesperado verificando descarga %s",
                download_id,
            )

    # El hilo ya está detenido antes de escribir en SQLite.
    if heartbeat.lease_lost:
        logger.warning(
            "No se registra el resultado: lease perdido en descarga %s",
            download_id,
        )
        return True

    with Session(engine) as session:
        if resultado == "aplazar":
            changed = defer_claimed_verification(
                session,
                download_id,
                worker_id,
                retry_base_seconds=60,
            )
        else:
            changed = finish_claimed_verification(
                session,
                download_id,
                torrent_hash,
                worker_id,
                verified=resultado == "correcta",
                error=error,
            )

    if not changed:
        logger.warning(
            "No se pudo registrar la verificación %s: "
            "lease caducado o reclamación perdida",
            download_id,
        )

    return True


def verify_pending_downloads_once(
    client: QBittorrentClient | None = None,
    media_root: Path = DOWNLOAD_ROOT,
) -> int:
    """Compatibilidad: verifica mediante reclamaciones protegidas.

    Procesa como máximo un trabajo por llamada.
    Devuelve 1 si se registra una verificación definitiva,
    o 0 si no hay trabajo o se aplaza.
    """
    qbittorrent = client if client is not None else QBittorrentClient()

    with Session(engine) as session:
        pendientes_antes = set(
            session.exec(
                select(Descarga.id).where(
                    Descarga.estado == "completada",
                    Descarga.progreso == 1,
                    Descarga.estado_verificacion == "pendiente",
                )
            ).all()
        )

    if not process_one_verification(
        new_verification_worker_id(),
        client=qbittorrent,
        media_root=media_root,
    ):
        return 0

    with Session(engine) as session:
        finalizadas = session.exec(
            select(Descarga.id).where(
                Descarga.id.in_(pendientes_antes),
                Descarga.estado_verificacion.in_(
                    ("verificada", "fallida")
                ),
            )
        ).all()

    return min(len(finalizadas), 1)
