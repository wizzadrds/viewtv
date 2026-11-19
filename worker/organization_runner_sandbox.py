"""Integración de cola + planificador + copia SOLO EN SANDBOX DE PRUEBAS.

No se importa desde worker/main.py y no permite trabajar con /media real.
Un éxito de copia seguido de pérdida de lease se considera ambiguo:
jamás se reintenta sobrescribiendo, el destino existente exige revisión.
"""

import errno
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from app.models import Descarga, Solicitud
from app.organization_queue import (
    claim_next_organization,
    confirm_organization,
    defer_organization,
    mark_organization_review,
    renew_organization_lease,
)
from app.qbittorrent import QBittorrentError
from sqlalchemy.engine import Engine
from sqlmodel import Session
from worker.file_validator import InvalidTorrentFiles
from worker.organization_copy_sandbox import (
    _check_sandbox,
    publish_test_plan,
)
from worker.organization_planner import (
    UnsafeOrganizationPlan,
    plan_verified_media,
)

SandboxOutcome = Literal[
    "sin_trabajos", "organizada", "requiere_revision", "lease_perdido", "aplazada"
]


class LostOrganizationLease(RuntimeError):
    """El lease caducó o pasó a otro worker: no confirmar la copia."""


def run_one_sandbox_organization(
    engine: Engine,
    sandbox_root: Path,
    worker_id: str,
    source_provider: Callable[[Descarga], list[Path]],
) -> SandboxOutcome:
    """Procesa una única reclamación con ficheros ficticios bajo /tmp.

    source_provider es una función inyectada por PRUEBAS. No obtiene archivos
    reales de qBittorrent y no constituye autorización para organizarlos.
    """
    root = _check_sandbox(sandbox_root)  # Antes de realizar cualquier claim.
    if not callable(source_provider):
        raise TypeError("Se requiere proveedor de fuentes de prueba.")

    with Session(engine) as session:
        claimed = claim_next_organization(session, worker_id)
        if claimed is None:
            return "sin_trabajos"
        download_id = claimed.id
        if download_id is None:
            raise AssertionError("Una descarga reclamada debe tener ID.")

    def heartbeat() -> None:
        with Session(engine) as session:
            renewed = renew_organization_lease(
                session, download_id, worker_id,
            )
        if not renewed:
            raise LostOrganizationLease("Reserva perdida; operación no confirmada.")

    try:
        heartbeat()
        with Session(engine) as session:
            download = session.get(Descarga, download_id)
            if download is None:
                raise LostOrganizationLease("Descarga reclamada inexistente.")
            request = session.get(Solicitud, download.solicitud_id)
            if request is None:
                raise UnsafeOrganizationPlan("La solicitud ya no existe.")
            sources = source_provider(download)
            plan = plan_verified_media(
                download,
                request,
                sources,
                root / "media" / "descargas_temporales",
                root / "media",
            )

        heartbeat()
        publish_test_plan(
            plan, root, progress_callback=heartbeat,
        )
        # Verificar de nuevo el lease DESPUÉS de publicar. Si falla,
        # otro intento detectará el destino y lo enviará a revisión.
        heartbeat()
        with Session(engine) as session:
            confirmed = confirm_organization(
                session, download_id, worker_id,
            )
        if not confirmed:
            return "lease_perdido"
        return "organizada"
    except LostOrganizationLease:
        return "lease_perdido"
    except QBittorrentError:
        # La consulta al gestor ocurre antes de crear staging: el error
        # de comunicación no constituye una orden ambigua de escritura.
        with Session(engine) as session:
            deferred = defer_organization(
                session, download_id, worker_id, "comunicacion",
            )
        return "aplazada" if deferred else "lease_perdido"
    except (UnsafeOrganizationPlan, InvalidTorrentFiles, OSError) as exc:
        reason = (
            "espacio_insuficiente"
            if isinstance(exc, OSError) and exc.errno == errno.ENOSPC
            else "archivo_invalido"
        )
        with Session(engine) as session:
            marked = mark_organization_review(
                session, download_id, worker_id, reason,
            )
        return "requiere_revision" if marked else "lease_perdido"
