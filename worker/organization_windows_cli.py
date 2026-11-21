"""Canal de control para un publicador Windows separado del worker.

Solo se ejecuta bajo autorización del host dentro de la API 0013.
No copia ni mueve archivos. El ejecutor Windows conserva toda la autoridad
sobre C:\\VIEWTV\\media, diario y operaciones NTFS.
"""

import argparse
import json
import os
import sys

from sqlmodel import Session
from worker.organization_windows_authority import (
    BROKER_ID,
    build_windows_publication_intent,
    claim_for_windows,
    publication_policy,
    verify_windows_publication_sources,
)

from app.database import engine
from app.jellyfin import JellyfinClient, synchronize_catalog
from app.models import Descarga, Solicitud
from app.organization_queue import (
    confirm_organization,
    mark_organization_review,
    renew_organization_lease,
)
from app.qbittorrent import QBittorrentClient


def _schema_0013() -> None:
    with engine.connect() as connection:
        version = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()
    if version != "0013_cola_organizacion":
        raise ValueError("La base de datos no tiene el esquema 0013.")


def _in_policy(download_id: int, policy) -> None:
    if download_id <= policy.after_id or (
        policy.allowed_id is not None and download_id != policy.allowed_id
    ):
        raise ValueError("La descarga no está autorizada para esta fase.")


def _prepare(download_id: int, attempt: int) -> dict:
    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        if download is None or download.organizacion_intentos != attempt:
            raise ValueError("Trabajo de publicación no vigente.")
        request = session.get(Solicitud, download.solicitud_id)
        if request is None:
            raise ValueError("Solicitud original no disponible.")
        # Desvincular los valores antes de consultar red y archivos:
        # se usan objetos leídos, sin mantener una transacción SQLite.
        return build_windows_publication_intent(
            download, request, QBittorrentClient()
        )


def run(command: str, download_id: int | None = None, attempt: int | None = None) -> dict:
    policy = publication_policy(os.environ)
    if policy.mode == "disabled":
        return {"estado": "deshabilitado"}
    _schema_0013()
    if command == "status":
        return {"estado": "listo", "modo": policy.mode, "after_id": policy.after_id,
                "allowed_download_id": policy.allowed_id}
    if command == "sync":
        # Solo en modo futuro aprobado: la sincronización completa es
        # transaccional, reutiliza la misma función que la API autenticada.
        if policy.mode != "general":
            raise ValueError("Sincronización periódica no autorizada.")
        jellyfin = JellyfinClient()
        first_page = jellyfin.get_items(0, 100)
        items = first_page.get("Items")
        if not isinstance(items, list) or len(items) < 2:
            raise ValueError("Jellyfin no confirmó la biblioteca mínima.")
        with Session(engine) as session:
            processed = synchronize_catalog(session, jellyfin)
        return {"estado": "catalogo_sincronizado", "elementos_procesados": processed}
    if command == "claim":
        with Session(engine) as session:
            claimed = claim_for_windows(session, policy)
            if claimed is None:
                return {"estado": "sin_trabajos"}
            return {
                "estado": "reclamada",
                "download_id": claimed.id,
                "attempt": claimed.organizacion_intentos,
            }

    if download_id is None or attempt is None:
        raise ValueError("Se requiere descarga e intento.")
    _in_policy(download_id, policy)
    if command == "prepare":
        return {"estado": "preparada", "intent": _prepare(download_id, attempt)}
    if command == "verify-source":
        with Session(engine) as session:
            download = session.get(Descarga, download_id)
            if download is None or download.organizacion_intentos != attempt:
                raise ValueError("Trabajo no vigente.")
            files = verify_windows_publication_sources(download, QBittorrentClient())
            return {"estado": "fuente_verificada", "torrent_hash": download.qbittorrent_hash,
                    "files": files}
    if command == "renew":
        with Session(engine) as session:
            renewed = renew_organization_lease(
                session, download_id, BROKER_ID, expected_attempt=attempt,
            )
        return {"estado": "renovada" if renewed else "lease_perdido"}
    if command == "confirm":
        # El broker llama a confirm después de verificar publicación y diario.
        # Revalidar lease y propiedad del torrent, aun con destino ya existente.
        with Session(engine) as session:
            download = session.get(Descarga, download_id)
            if download is None or download.organizacion_intentos != attempt:
                raise ValueError("Trabajo no vigente.")
            verify_windows_publication_sources(download, QBittorrentClient())
            confirmed = confirm_organization(
                session, download_id, BROKER_ID, expected_attempt=attempt,
            )
        return {"estado": "organizada" if confirmed else "lease_perdido"}
    if command == "review":
        with Session(engine) as session:
            marked = mark_organization_review(
                session, download_id, BROKER_ID, "archivo_invalido",
                expected_attempt=attempt,
            )
        return {"estado": "requiere_revision" if marked else "lease_perdido"}
    if command == "scan":
        with Session(engine) as session:
            download = session.get(Descarga, download_id)
            if download is None or download.organizacion_estado != "organizada":
                raise ValueError("No está confirmada la publicación.")
        # Respuesta aceptada != escaneo terminado ni catálogo comprobado.
        JellyfinClient().request_library_scan()
        return {"estado": "escaneo_solicitado"}
    raise ValueError("Operación de broker desconocida.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Control de publicación Windows 0013.")
    parser.add_argument(
        "command",
        choices=("status", "claim", "prepare", "verify-source", "renew", "confirm",
                 "review", "scan", "sync"),
    )
    parser.add_argument("--download-id", type=int)
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args(argv)
    try:
        if args.download_id is not None and args.download_id <= 0:
            raise ValueError("ID de descarga inválida.")
        if args.attempt is not None and not 1 <= args.attempt <= 3:
            raise ValueError("Intento inválido.")
        result = run(args.command, args.download_id, args.attempt)
    except Exception:
        # No revelar rutas privadas, tokens de qBit o credenciales en stdout.
        print(json.dumps({"estado": "rechazada", "motivo": "validacion_o_servicio"}))
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
