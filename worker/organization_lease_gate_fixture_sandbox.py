"""Datos de prueba para el puente Windows -> WSL; nunca SQLite de producción.

Crea una base ficticia bajo una raíz aleatoria /tmp/viewtv-lease-gate-<GUID>.
Solo permite alterar o quitar SU PROPIA base bajo esa raíz marcada.
"""

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.models import Descarga, Perfil, Solicitud
from app.organization_publication_gate_sandbox import _sandbox_db
from app.organization_queue import claim_next_organization
from sqlmodel import Session, SQLModel, create_engine

_MARKER = "VIEWTV_LEASE_GATE_SANDBOX_V1\n"
_WORKER = "worker-ficticio-windows"
_HASH = "a" * 40


def _create() -> dict:
    root = Path("/tmp") / ("viewtv-lease-gate-" + uuid4().hex)
    root.mkdir(mode=0o700, exist_ok=False)
    (root / ".viewtv-lease-gate-sandbox-only").write_text(
        _MARKER, encoding="utf-8"
    )
    db = root / "organization.sqlite3"
    engine = create_engine(f"sqlite:///{db}")
    try:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            profile = Perfil(nombre="Perfil ficticio", pin_hash="hash-no-real")
            session.add(profile)
            session.flush()
            request = Solicitud(
                perfil_id=profile.id,
                titulo="Video de prueba",
                tipo_medio="pelicula",
                estado="completada",
            )
            session.add(request)
            session.flush()
            row = Descarga(
                solicitud_id=request.id,
                titulo="Video de prueba",
                estado="completada",
                progreso=1,
                estado_verificacion="verificada",
                verificada_en=datetime.now(UTC),
                qbittorrent_hash=_HASH,
                organizacion_estado="pendiente",
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            did = row.id
        with Session(engine) as session:
            claimed = claim_next_organization(session, _WORKER)
            if claimed is None or claimed.id != did:
                raise RuntimeError("No se pudo reclamar un trabajo ficticio.")
    finally:
        engine.dispose()
    return {
        "database": str(db),
        "download_id": did,
        "worker_id": _WORKER,
        "attempt": 1,
        "torrent_hash": _HASH,
    }


def _modify(db: Path, action: str) -> dict:
    _sandbox_db(db)
    if action == "expire":
        sql = "UPDATE descarga SET organizacion_locked_until = ?"
        value = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    elif action == "revoke":
        sql = "UPDATE descarga SET estado_verificacion = ?"
        value = "fallida"
    elif action == "reassign":
        sql = "UPDATE descarga SET organizacion_locked_by = ?"
        value = "otro-worker"
    else:
        raise ValueError("Acción inválida.")
    with closing(sqlite3.connect(db)) as connection, connection:
        result = connection.execute(sql, (value,))
        if result.rowcount != 1:
            raise ValueError("La base de prueba no tiene una sola descarga.")
    return {"ok": True}


def _cleanup(db: Path) -> dict:
    _sandbox_db(db)
    root = db.parent
    marker = root / ".viewtv-lease-gate-sandbox-only"
    # Nunca borrar ni recorrer una raíz no reconocida.
    if {p.name for p in root.iterdir()} != {
        "organization.sqlite3", ".viewtv-lease-gate-sandbox-only"
    }:
        raise ValueError("Hay entradas inesperadas; no se eliminará nada.")
    db.unlink()
    marker.unlink()
    root.rmdir()
    return {"ok": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "expire", "revoke", "reassign", "cleanup"])
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    if args.action == "create":
        result = _create()
    else:
        if args.database is None:
            parser.error("Se requiere --database.")
        result = _cleanup(args.database) if args.action == "cleanup" else _modify(
            args.database, args.action
        )
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
