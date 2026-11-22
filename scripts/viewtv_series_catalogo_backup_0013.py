"""Copia online de metadatos TMDB sin tocar SQLite principal ni películas.

Origen montado read-only; nombre destino controlado por regex.
Sin acceso a credenciales de usuario ni claves de TMDB.
"""
import os
import re
import sqlite3
from pathlib import Path

name = os.getenv("VIEWTV_BACKUP_NAME", "")
if re.fullmatch(r"metadatos-series-predeploy-\d{8}-\d{6}\.db", name) is None:
    raise SystemExit("Nombre de copia de catálogo inválido.")
if os.getenv("VIEWTV_SQLITE_COPY_ONLY") != "1":
    raise SystemExit("Modo de copia no autorizado.")

source = Path("/catalogo/metadatos.db")
destination = Path("/backup") / name
if not source.is_file() or destination.exists():
    raise SystemExit("Origen ausente o copia destino ya existe.")
fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
os.close(fd)

try:
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src:
        src.execute("PRAGMA query_only=ON")
        if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Metadatos no íntegros.")
        count = src.execute("SELECT COUNT(*) FROM ficha").fetchone()[0]
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Copia no íntegra.")
            if dst.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Claves foráneas incorrectas.")
            if dst.execute("SELECT COUNT(*) FROM ficha").fetchone()[0] != count:
                raise RuntimeError("La copia no conserva el catálogo.")
            if dst.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise RuntimeError("Versión SQLite inesperada.")
    print("BACKUP_CATALOGO_SERIES=INTEGRO")
    print("FICHAS_RESPALDADAS="+str(count))
except Exception:
    destination.unlink(missing_ok=True)
    raise
