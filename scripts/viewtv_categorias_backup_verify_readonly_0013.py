"""Verificador SQLite de copia online previa a categorías. Solo lectura."""
import sqlite3
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Se exige ruta de copia.")
file = Path(sys.argv[1])
if not file.is_file() or file.is_symlink() or file.stat().st_size < 8192:
    raise SystemExit("Copia SQLite ausente.")
db = sqlite3.connect(f"file:{file}?mode=ro", uri=True)
try:
    db.execute("PRAGMA query_only=ON")
    if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
        raise RuntimeError("Integridad SQLite no válida.")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Claves foráneas rotas.")
    if db.execute("SELECT version_num FROM alembic_version").fetchone() != ("0013_cola_organizacion",):
        raise RuntimeError("Esquema diferente a 0013.")
    downloaded = db.execute("SELECT COUNT(*) FROM descarga").fetchone()[0]
    media = db.execute("SELECT COUNT(*) FROM medio").fetchone()[0]
    if downloaded < 4 or media < 4:
        raise RuntimeError("Copia incompleta.")
    print("COPIA_SQLITE_INTEGRA=SI")
    print("COPIA_SQLITE_FK=OK")
    print("COPIA_SQLITE_REVISION=0013_cola_organizacion")
    print("COPIA_DESCARGAS="+str(downloaded))
    print("COPIA_CATALOGO="+str(media))
finally:
    db.close()
