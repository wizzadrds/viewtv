"""Proceso independiente de procesamiento de la cola durable de VIEWTV."""

import logging
import os
import socket
import time

from app.database import engine
from app.queue import get_queue_counts
from sqlmodel import Session
from worker.catalog_sync import CatalogSyncScheduler
from worker.download_monitor import monitor_downloads_once
from worker.download_processor import process_one_download
from worker.download_starter import process_one_start
from worker.download_verifier import (
    new_verification_worker_id,
    process_one_verification,
)
from worker.processor import process_one_request

POLL_INTERVAL_SECONDS = 10
VERIFICATION_ENABLED = (
    os.environ.get("VIEWTV_ENABLE_DOWNLOAD_VERIFICATION", "false").strip().lower()
    == "true"
)
START_ENABLED = (
    os.environ.get("VIEWTV_ENABLE_DOWNLOAD_START", "false").strip().lower() == "true"
)
# Seleccionar un resultado NO autoriza añadir un torrent real a qBittorrent.
# La preparación y el inicio son dos permisos independientes y explícitos.
SUBMISSION_ENABLED = (
    os.environ.get("VIEWTV_ENABLE_TORRENT_SUBMIT", "false").strip().lower() == "true"
)
VERIFICATION_WORKER_ID = new_verification_worker_id()
WORKER_ID = f"{socket.gethostname()[:80]}-{os.getpid()}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("viewtv.worker")


def report_worker_status() -> None:
    """Informa del estado de la cola sin modificarla."""
    with Session(engine) as session:
        counts = get_queue_counts(session)

    logger.info("Worker %s activo; estado de la cola: %s", WORKER_ID, counts)


def main():
    catalog_sync = CatalogSyncScheduler()
    while True:
        try:
            download_processed = False
            if SUBMISSION_ENABLED:
                download_processed = process_one_download(WORKER_ID)
            request_processed = process_one_request(WORKER_ID)

            start_processed = False
            if START_ENABLED:
                try:
                    start_processed = process_one_start(WORKER_ID)
                except Exception:
                    logger.exception("Error procesando inicio de torrent.")

            try:
                updated = monitor_downloads_once()
                if updated:
                    logger.info(
                        "Supervisor: %s descargas actualizadas",
                        updated,
                    )
            except Exception:
                logger.exception("Error consultando el progreso de descargas.")

            # Catálogo fresco incluso con la interfaz cerrada. Jellyfin
            # y SQLite se sincronizan en una transacción; si fallan, el
            # ciclo de descargas continúa y se reintenta después.
            try:
                synced = catalog_sync.run_if_due()
                if synced is not None:
                    logger.info("Catálogo Jellyfin actualizado: %s medios", synced)
            except Exception:
                logger.exception("Sincronización periódica de Jellyfin fallida.")

            verification_processed = False
            if VERIFICATION_ENABLED:
                try:
                    verification_processed = process_one_verification(
                        VERIFICATION_WORKER_ID
                    )
                except Exception:
                    logger.exception("Error procesando verificación de descarga.")

            if not any(
                (
                    download_processed,
                    request_processed,
                    start_processed,
                    verification_processed,
                )
            ):
                report_worker_status()

            time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("Worker detenido.")
            break
        except Exception:
            logger.exception("Error inesperado en el ciclo del worker.")
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
