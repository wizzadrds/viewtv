"""Proceso independiente de procesamiento de la cola durable de VIEWTV."""

import logging
import os
import socket
import time

from sqlmodel import Session
from worker.download_processor import process_one_download
from worker.processor import process_one_request

from app.database import engine
from app.queue import get_queue_counts

POLL_INTERVAL_SECONDS = 10
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
    while True:
        try:
            download_processed = process_one_download(WORKER_ID)
            request_processed = process_one_request(WORKER_ID)

            if not download_processed and not request_processed:
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
