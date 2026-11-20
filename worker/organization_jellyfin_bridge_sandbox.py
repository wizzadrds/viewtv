"""Publicación de prueba -> escaneo Jellyfin, SOLO EN SANDBOX /tmp.

NO importar desde worker/main.py. Un escaneo HTTP aceptado NO implica
que Jellyfin haya descubierto el medio: el catálogo se sincroniza después.
No hay autorización para escribir en las bibliotecas del usuario.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol

from app.jellyfin import JellyfinError
from app.models import Descarga
from sqlalchemy.engine import Engine
from sqlmodel import Session, select
from worker.organization_copy_sandbox import _check_sandbox
from worker.organization_planner import UnsafeOrganizationPlan
from worker.organization_runner_sandbox import (
    SandboxOutcome,
    run_one_sandbox_organization,
)


class ScanRequester(Protocol):
    def request_library_scan(self) -> None: ...


BridgeOutcome = (
    SandboxOutcome | Literal["escaneo_solicitado", "publicada_escaneo_pendiente"]
)


def _verified_sandbox_engine(engine: Engine, sandbox_root: Path) -> Path:
    root = _check_sandbox(sandbox_root)
    if engine.url.get_backend_name() != "sqlite" or engine.url.database != str(
        root / "test-organization.db"
    ):
        raise UnsafeOrganizationPlan("La base no pertenece al sandbox de integración.")
    return root


def request_scan_for_published_sandbox_download(
    engine: Engine,
    sandbox_root: Path,
    download_id: int,
    jellyfin: ScanRequester,
) -> Literal["escaneo_solicitado", "publicada_escaneo_pendiente"]:
    """Reintentable sin copiar: solo tras confirmar 'organizada' en SQLite."""
    _verified_sandbox_engine(engine, sandbox_root)
    if (
        isinstance(download_id, bool)
        or not isinstance(download_id, int)
        or download_id <= 0
    ):
        raise ValueError("Identificador de descarga no válido.")
    with Session(engine) as session:
        row = session.get(Descarga, download_id)
        if row is None or row.organizacion_estado != "organizada":
            raise UnsafeOrganizationPlan("La publicación aún no está confirmada.")

    try:
        jellyfin.request_library_scan()
    except JellyfinError:
        # La publicación confirmada no se deshace ni se copia de nuevo.
        return "publicada_escaneo_pendiente"
    return "escaneo_solicitado"


def run_one_sandbox_organization_with_jellyfin(
    engine: Engine,
    sandbox_root: Path,
    worker_id: str,
    source_provider: Callable[[Descarga], list[Path]],
    *,
    expected_download_id: int,
    jellyfin: ScanRequester,
) -> BridgeOutcome:
    """Ensaya una publicación y pide escaneo SOLO si confirmó la ID esperada."""
    _verified_sandbox_engine(engine, sandbox_root)
    if (
        isinstance(expected_download_id, bool)
        or not isinstance(expected_download_id, int)
        or expected_download_id <= 0
    ):
        raise ValueError("Identificador esperado no válido.")
    with Session(engine) as session:
        eligible = session.exec(
            select(Descarga.id).where(
                Descarga.estado == "completada",
                Descarga.progreso == 1,
                Descarga.estado_verificacion == "verificada",
                Descarga.organizacion_estado == "pendiente",
            )
        ).all()
    if eligible and eligible != [expected_download_id]:
        raise UnsafeOrganizationPlan("Hay otra descarga pendiente en el sandbox.")

    outcome = run_one_sandbox_organization(
        engine,
        sandbox_root,
        worker_id,
        source_provider,
    )
    if outcome != "organizada":
        return outcome
    return request_scan_for_published_sandbox_download(
        engine,
        sandbox_root,
        expected_download_id,
        jellyfin,
    )
