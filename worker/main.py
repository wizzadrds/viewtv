"""Proceso independiente de planificación de trabajos de VIEWTV.

La ejecución real de la cola durable se incorporará en la siguiente iteración.
Este esqueleto permite validar que API y worker arrancan como procesos separados.
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("viewtv.worker")


def report_worker_alive() -> None:
    logger.info("Worker activo; procesador de cola pendiente de implementación")


def main() -> None:
    settings = get_settings()
    scheduler = BlockingScheduler(timezone=settings.timezone)
    scheduler.add_job(
        report_worker_alive,
        trigger="interval",
        seconds=30,
        id="worker-heartbeat",
        max_instances=1,
        coalesce=True,
    )
    logger.info("Iniciando worker VIEWTV con zona horaria %s", settings.timezone)
    scheduler.start()


if __name__ == "__main__":
    main()
