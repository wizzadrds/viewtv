"""Proceso independiente de supervisión de la cola durable de VIEWTV.

Este worker observa la cola y registra su estado. No reclama solicitudes hasta
que exista un procesador multimedia configurado, para no consumir intentos ni
marcar como completadas tareas que todavía no puede ejecutar.
"""

import logging
import socket

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlmodel import Session

from app.config import get_settings
from app.database import engine
from app.queue import get_queue_counts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("viewtv.worker")
WORKER_ID = socket.gethostname()


def report_worker_status() -> None:
    """Comprueba conectividad con SQLite e informa de la cola sin alterarla."""
    with Session(engine) as session:
        counts = get_queue_counts(session)

    pending = counts["pendiente"]
    processing = counts["procesando"]
    logger.info(
        "Worker %s activo; cola: %s pendientes, %s procesando",
        WORKER_ID,
        pending,
        processing,
    )
    if pending:
        logger.warning(
            "Hay %s solicitudes pendientes; el procesador multimedia aún no está configurado",
            pending,
        )


def main() -> None:
    settings = get_settings()
    scheduler = BlockingScheduler(timezone=settings.timezone)
    scheduler.add_job(
        report_worker_status,
        trigger="interval",
        seconds=30,
        id="worker-queue-status",
        max_instances=1,
        coalesce=True,
    )
    logger.info("Iniciando worker VIEWTV con zona horaria %s", settings.timezone)
    scheduler.start()


if __name__ == "__main__":
    main()
