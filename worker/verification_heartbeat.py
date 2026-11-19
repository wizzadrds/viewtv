"""Renovación periódica de leases de verificación."""

import logging
from threading import Event, Thread

from sqlmodel import Session

from app.queue import renew_verification_lease

logger = logging.getLogger("viewtv.verification_heartbeat")

LEASE_SECONDS = 120
RENEW_INTERVAL_SECONDS = 30


class VerificationHeartbeat:
    """Mantiene un lease mientras se verifican archivos."""

    def __init__(
        self,
        engine,
        download_id: int,
        worker_id: str,
        *,
        lease_seconds: int = LEASE_SECONDS,
        interval_seconds: float = RENEW_INTERVAL_SECONDS,
    ):
        if lease_seconds <= 0 or interval_seconds <= 0:
            raise ValueError("Intervalos de heartbeat no válidos")
        if interval_seconds >= lease_seconds:
            raise ValueError(
                "La renovación debe ser anterior al vencimiento"
            )

        self.engine = engine
        self.download_id = download_id
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.interval_seconds = interval_seconds
        self._stop = Event()
        self._lost = Event()
        self._thread = None

    @property
    def lease_lost(self) -> bool:
        return self._lost.is_set()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                with Session(self.engine) as session:
                    renewed = renew_verification_lease(
                        session,
                        self.download_id,
                        self.worker_id,
                        lease_seconds=self.lease_seconds,
                    )
            except Exception:
                logger.exception(
                    "No se pudo renovar el lease de verificación %s",
                    self.download_id,
                )
                self._lost.set()
                break

            if not renewed:
                logger.warning(
                    "Lease de verificación perdido: descarga %s",
                    self.download_id,
                )
                self._lost.set()
                break

    def __enter__(self):
        self._thread = Thread(
            target=self._run,
            name=f"verification-heartbeat-{self.download_id}",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        return False
