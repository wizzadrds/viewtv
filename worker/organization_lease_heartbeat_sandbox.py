"""Heartbeat concurrente para organización 0013, SOLO SQLite ficticia /tmp.

No participa en worker/main.py ni confirma publicaciones. No concede permiso
de escribir en Windows: el broker deberá tener su propia autoridad.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Self

from app.organization_publication_gate_sandbox import _sandbox_db
from app.organization_queue import MAX_ATTEMPTS, renew_organization_lease
from sqlalchemy.engine import Engine
from sqlmodel import Session


class SandboxLeaseLost(RuntimeError):
    """Lease perdido o indeterminado: detener el trabajo, nunca confirmar."""


class IndependentOrganizationHeartbeat:
    """Renueva en otro hilo/conexión mientras el hilo de copia está bloqueado.

    Solo el propietario y número de intento correctos pueden renovar.
    Cualquier fallo de base o de hilo se trata conservadoramente como pérdida.
    """

    def __init__(
        self,
        engine: Engine,
        download_id: int,
        worker_id: str,
        attempt: int,
        *,
        interval_seconds: float = 0.1,
        lease_seconds: int = 180,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if engine.url.get_backend_name() != "sqlite":
            raise ValueError("Solo SQLite de sandbox.")
        path = engine.url.database
        if not path or not Path(path).is_absolute():
            raise ValueError("Solo rutas absolutas de SQLite sandbox.")
        _sandbox_db(Path(path))
        if (
            isinstance(download_id, bool)
            or not isinstance(download_id, int)
            or download_id < 1
            or not isinstance(worker_id, str)
            or not worker_id.strip()
            or len(worker_id) > 128
            or isinstance(attempt, bool)
            or not isinstance(attempt, int)
            or not 1 <= attempt <= MAX_ATTEMPTS
            or isinstance(interval_seconds, bool)
            or not isinstance(interval_seconds, (int, float))
            or not 0.01 <= interval_seconds <= 30
            or isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, int)
            or not 1 <= lease_seconds <= 900
            or (clock is not None and not callable(clock))
        ):
            raise ValueError("Identidad o frecuencia inválida.")
        self._engine = engine
        self._path = Path(path)
        self._download_id = download_id
        self._worker_id = worker_id
        self._attempt = attempt
        self._interval = interval_seconds
        self._lease_seconds = lease_seconds
        self._clock = clock
        self._stop = Event()
        self._lost = Event()
        self._thread: Thread | None = None
        self._pulse_lock = Lock()
        self._renewals = 0

    @property
    def renewals(self) -> int:
        with self._pulse_lock:
            return self._renewals

    @property
    def lost(self) -> bool:
        return self._lost.is_set()

    def _pulse(self) -> None:
        # Serialize explicit checks and heartbeat; no concurrent transactions.
        with self._pulse_lock:
            _sandbox_db(self._path)
            with Session(self._engine) as session:
                kwargs = {"expected_attempt": self._attempt,
                          "lease_seconds": self._lease_seconds}
                if self._clock is not None:
                    kwargs["now"] = self._clock()
                ok = renew_organization_lease(
                    session, self._download_id, self._worker_id, **kwargs
                )
            if not ok:
                raise SandboxLeaseLost("Lease de sandbox perdido.")
            self._renewals += 1

    def _background(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._pulse()
            except Exception:  # noqa: BLE001 - fail closed on ANY background error
                # A failure could be a transient DB lock. Fail closed anyway:
                # never silently claim renewal or continue publication.
                self._lost.set()
                return

    def start(self) -> "IndependentOrganizationHeartbeat":
        if self._thread is not None or self._stop.is_set():
            raise RuntimeError("El heartbeat no puede iniciarse dos veces.")
        try:
            self._pulse()
        except Exception as exc:
            self._lost.set()
            raise SandboxLeaseLost("No se pudo comprobar el lease inicial.") from exc
        self._thread = Thread(
            target=self._background, name="viewtv-lease-sandbox",
            daemon=True,
        )
        self._thread.start()
        return self

    def require_active(self) -> None:
        if self._thread is None or self._stop.is_set() or self._lost.is_set():
            raise SandboxLeaseLost("No existe un heartbeat vivo.")
        if not self._thread.is_alive():
            self._lost.set()
            raise SandboxLeaseLost("El hilo de renovación terminó.")
        try:
            self._pulse()
        except Exception as exc:
            self._lost.set()
            raise SandboxLeaseLost("Lease no verificable; no publicar.") from exc

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                self._lost.set()
                raise SandboxLeaseLost("No se pudo detener la renovación.")

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.stop()
