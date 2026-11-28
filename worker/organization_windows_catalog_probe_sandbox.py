"""Docker -> publicación NTFS Windows -> Jellyfin simulado -> catálogo SQLite ficticio.

SONDA EXCLUSIVA DE LABORATORIO. No consulta credenciales, Jellyfin real,
qBittorrent ni SQLite productiva. La autorización Windows se comprueba
antes y después mediante el publicador/reconciliador PowerShell del test.
"""

import argparse
import json
from pathlib import Path

import httpx
from app.config import Settings
from app.jellyfin import JellyfinClient, synchronize_catalog
from app.models import Medio
from sqlmodel import Session, SQLModel, create_engine, select

from worker.organization_cross_runtime_probe import (
    STAGE,
    SUBTITLE,
    TITLE,
    VIDEO,
    validate_scratch_root,
)
from worker.organization_planner import UnsafeOrganizationPlan


def test_catalog_after_windows_publication(root: Path, *, phase: str) -> dict:
    """No hay acciones externas: se trata solo de HTTP mock e in-memory SQLite."""
    if phase not in {"before", "after"}:
        raise ValueError("Fase de prueba desconocida.")
    root = validate_scratch_root(root)
    staging = root / STAGE
    published = root / TITLE
    if phase == "before":
        if not staging.is_dir() or published.exists() or staging.is_symlink():
            raise UnsafeOrganizationPlan("El sandbox no está antes de publicar.")
        return {
            "estado": "pendiente_sin_escaneo",
            "solicitudes_escaneo": 0,
            "catalogo": 0,
        }

    if staging.exists() or not published.is_dir() or published.is_symlink():
        raise UnsafeOrganizationPlan("La carpeta Windows no está publicada.")
    actual_names = {child.name for child in published.iterdir()}
    if actual_names != {VIDEO, SUBTITLE}:
        raise UnsafeOrganizationPlan(
            "Publicación incompleta o con archivos adicionales."
        )
    for filename in (VIDEO, SUBTITLE):
        file = published / filename
        if (
            file.is_symlink()
            or not file.is_file()
            or not 0 < file.stat().st_size <= 32 * 1024 * 1024
        ):
            raise UnsafeOrganizationPlan("Contenido ficticio no validable.")

    state = {"scan_requested": 0, "scan_complete": False, "events": []}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host != "jellyfin-ficticio.invalid":
            raise AssertionError("La prueba no admite host de red externo.")
        if request.method == "POST" and request.url.path == "/Library/Refresh":
            state["events"].append("POST_SCAN")
            state["scan_requested"] += 1
            return httpx.Response(204, request=request)
        if request.method == "GET" and request.url.path == "/Items":
            state["events"].append("GET_CATALOG")
            available = state["scan_complete"] and state["scan_requested"] == 1
            items = (
                [
                    {
                        "Id": "pelicula-ficticia-windows",
                        "Type": "Movie",
                        "Name": TITLE,
                        "ProductionYear": 2026,
                    }
                ]
                if available
                else []
            )
            return httpx.Response(
                200,
                json={"Items": items, "TotalRecordCount": len(items)},
                request=request,
            )
        raise AssertionError("Ruta de Jellyfin inesperada.")

    settings = Settings(
        _env_file=None,
        jellyfin_base_url="http://jellyfin-ficticio.invalid:8096",
        jellyfin_api_key="clave-no-real-de-prueba",
    )
    client = JellyfinClient(settings=settings, transport=httpx.MockTransport(handler))
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            if synchronize_catalog(session, client=client) != 0:
                raise AssertionError(
                    "El catálogo no debe contener la obra antes del escaneo."
                )
            client.request_library_scan()
            if synchronize_catalog(session, client=client) != 0:
                raise AssertionError("Aceptar el escaneo no equivale a terminarlo.")
            state["scan_complete"] = True
            if synchronize_catalog(session, client=client) != 1:
                raise AssertionError("Jellyfin simulado no indexó la obra publicada.")
            records = session.exec(select(Medio)).all()
            if (
                len(records) != 1
                or records[0].titulo != TITLE
                or not records[0].disponible_en_jellyfin
            ):
                raise AssertionError("El catálogo SQLite de prueba es incongruente.")
        if state["events"] != [
            "GET_CATALOG",
            "POST_SCAN",
            "GET_CATALOG",
            "GET_CATALOG",
        ]:
            raise AssertionError("Orden inesperado de operaciones simuladas.")
        return {
            "estado": "publicacion_windows_catalogo_simulado_ok",
            "solicitudes_escaneo": state["scan_requested"],
            "catalogo_antes": 0,
            "catalogo_antes_finalizar": 0,
            "catalogo_despues": 1,
        }
    finally:
        engine.dispose()


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--sandbox", type=Path, required=True)
    cli.add_argument("--phase", choices=["before", "after"], required=True)
    args = cli.parse_args()
    print(
        json.dumps(
            test_catalog_after_windows_publication(args.sandbox, phase=args.phase),
            ensure_ascii=False,
        )
    )
