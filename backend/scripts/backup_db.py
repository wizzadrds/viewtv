"""Crea y valida copias coherentes de SQLite usando la Online Backup API."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import get_settings

LOGGER = logging.getLogger("viewtv.backup")
BACKUP_PREFIX = "viewtv-"
BACKUP_SUFFIX = ".db"


def sqlite_file_from_url(database_url: str) -> Path:
    """Devuelve la ruta de una base SQLite en disco; rechaza otros motores."""
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        raise ValueError("El backup automático solo admite SQLite en un archivo.")
    if url.database == ":memory:":
        raise ValueError("No se puede respaldar una base SQLite en memoria.")
    return Path(url.database).expanduser().resolve()


def prune_old_backups(
    backup_dir: Path,
    retention_days: int,
    *,
    now: datetime | None = None,
) -> list[Path]:
    """Elimina únicamente backups VIEWTV con fecha de modificación fuera de retención."""
    if retention_days < 1:
        raise ValueError("BACKUP_RETENTION_DAYS debe ser al menos 1.")
    current_time = now or datetime.now().astimezone()
    cutoff = current_time.timestamp() - timedelta(days=retention_days).total_seconds()
    removed: list[Path] = []
    for candidate in backup_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"):
        if candidate.is_file() and candidate.stat().st_mtime < cutoff:
            candidate.unlink()
            removed.append(candidate)
    return removed


def create_backup(
    database_url: str,
    backup_dir: Path,
    retention_days: int = 30,
    *,
    now: datetime | None = None,
) -> Path:
    """Crea una copia SQLite consistente, valida su integridad y aplica retención."""
    source_path = sqlite_file_from_url(database_url)
    if not source_path.is_file():
        raise FileNotFoundError(f"No existe la base de datos configurada: {source_path}")
    if retention_days < 1:
        raise ValueError("BACKUP_RETENTION_DAYS debe ser al menos 1.")

    backup_dir.mkdir(parents=True, exist_ok=True)
    current_time = now or datetime.now().astimezone()
    stamp = current_time.strftime("%Y%m%d-%H%M%S")
    final_path = backup_dir / f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}"
    temporary_path = backup_dir / f".{final_path.name}.tmp"
    if final_path.exists():
        raise FileExistsError(f"Ya existe un backup con ese nombre: {final_path}")

    try:
        with sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True, timeout=30) as source:
            with sqlite3.connect(temporary_path, timeout=30) as destination:
                source.backup(destination, pages=256, sleep=0.1)
                result = destination.execute("PRAGMA integrity_check").fetchone()
                if result is None or result[0] != "ok":
                    raise sqlite3.DatabaseError(f"Falló integrity_check: {result}")
        os.replace(temporary_path, final_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    removed = prune_old_backups(backup_dir, retention_days, now=current_time)
    LOGGER.info(
        "Backup creado: %s (%d bytes); backups antiguos eliminados: %d",
        final_path,
        final_path.stat().st_size,
        len(removed),
    )
    return final_path


def main() -> None:
    logging.basicConfig(
        level=os.getenv("VIEWTV_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()
    backup_dir = Path(os.getenv("BACKUP_DIR", "/backups"))
    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
    try:
        created = create_backup(
            settings.database_url,
            backup_dir,
            retention_days=retention_days,
        )
    except Exception:
        LOGGER.exception("No se pudo completar el backup de VIEWTV.")
        raise SystemExit(1) from None
    print(f"Backup verificado: {created}")


if __name__ == "__main__":
    main()
