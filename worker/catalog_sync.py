"""Sincronización periódica del catálogo Jellyfin desde el worker VIEWTV.

No mueve medios, no lanza torrents y no depende de una sesión web.
Cada worker ejecuta el refresco cada 30 min, con retraso inicial de 60 s.
Ante un fallo conserva el catálogo por rollback y reintenta a los 5 min.
"""

import time
from collections.abc import Callable

from app.database import engine
from app.jellyfin import synchronize_catalog
from sqlmodel import Session

CATALOG_INTERVAL_SECONDS = 30 * 60
CATALOG_INITIAL_DELAY_SECONDS = 60
CATALOG_RETRY_SECONDS = 5 * 60


def _sync_in_database() -> int:
    with Session(engine) as session:
        return synchronize_catalog(session)


class CatalogSyncScheduler:
    """Planifica sin bloquear el resto del worker cuando todavía no toca."""

    def __init__(
        self,
        *,
        sync: Callable[[], int] = _sync_in_database,
        clock: Callable[[], float] = time.monotonic,
        interval_seconds: int = CATALOG_INTERVAL_SECONDS,
        initial_delay_seconds: int = CATALOG_INITIAL_DELAY_SECONDS,
        retry_seconds: int = CATALOG_RETRY_SECONDS,
    ) -> None:
        if interval_seconds <= 0 or initial_delay_seconds < 0 or retry_seconds <= 0:
            raise ValueError("Intervalos de sincronización no válidos")
        self._sync = sync
        self._clock = clock
        self._interval = interval_seconds
        self._retry = retry_seconds
        self._due = clock() + initial_delay_seconds

    def run_if_due(self) -> int | None:
        """None: aún no toca. Entero: número de medios procesados."""
        now = self._clock()
        if now < self._due:
            return None
        # Protege también frente a llamadas reentrantes del mismo scheduler.
        self._due = now + self._retry
        try:
            count = self._sync()
        except Exception:
            self._due = self._clock() + self._retry
            raise
        self._due = self._clock() + self._interval
        return count
