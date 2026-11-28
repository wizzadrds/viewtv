"""Copia SQLite online (origen solo lectura) para despliegue limitado de API."""
import os
import re
import sqlite3
from pathlib import Path

name = os.environ.get("VIEWTV_BACKUP_NAME", "")
if not re.fullmatch(r"api-resultados-predeploy-[0-9]{8}-[0-9]{6}\.db", name):
    raise SystemExit("Nombre de copia inválido")
if os.getenv("VIEWTV_SQLITE_COPY_ONLY") != "1":
    raise SystemExit("No se autorizó modo de copia")
source = Path("/data/viewtv.db")
destination = Path("/backup") / name
if not source.is_file() or destination.exists():
    raise SystemExit("Origen ausente o destino existente")
fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
os.close(fd)
try:
    with (
        sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src,
        sqlite3.connect(str(destination)) as dst,
    ):
        src.backup(dst)
        assert dst.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert dst.execute("PRAGMA foreign_key_check").fetchall() == []
    print("SQLITE_BACKUP=OK", flush=True)
    print("SQLITE_INTEGRITY=OK", flush=True)
    print("SQLITE_FK=OK", flush=True)
except Exception:
    destination.unlink(missing_ok=True)
    raise
