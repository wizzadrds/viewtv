"""Verifica copia online de SQLite antes de sincronizar portada ID4, solo lectura.

No expone nombres, rutas, IDs Jellyfin, torrents ni secretos.
"""
import sqlite3
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Se requiere ruta exacta de la copia.")
file = Path(sys.argv[1])
if not file.is_file() or file.is_symlink() or file.stat().st_size < 4096:
    raise SystemExit("Copia ausente o inválida.")
db = sqlite3.connect(f"file:{file}?mode=ro", uri=True)
try:
    db.execute("PRAGMA query_only=ON")
    if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
        raise RuntimeError("SQLite integrity_check no es ok")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("SQLite foreign_key_check tiene errores")
    if db.execute("SELECT version_num FROM alembic_version").fetchone() != ("0013_cola_organizacion",):
        raise RuntimeError("Revision de esquema inesperada")
    records = db.execute(
        "SELECT id, estado, progreso, estado_verificacion, organizacion_estado, "
        "organizacion_locked_by, organizacion_locked_until "
        "FROM descarga ORDER BY id"
    ).fetchall()
    if len(records) != 4 or [x[0] for x in records] != [1, 2, 3, 4]:
        raise RuntimeError("Registro de descargas diferente")
    if any(x[4] != "no_requerida" or x[5] is not None or x[6] is not None for x in records[:2]):
        raise RuntimeError("Descargas historicas no excluidas")
    if any(
        x[1] != "completada" or x[2] != 1 or x[3] != "verificada"
        or x[4] != "organizada" or x[5] is not None or x[6] is not None
        for x in records[2:]
    ):
        raise RuntimeError("Descargas #3/#4 no organizadas o con lease activo")
    print("SQLITE_COPIA_INTEGRA=SI")
    print("FK_VALIDAS=SI")
    print("ALEMBIC=0013_cola_organizacion")
    print("ID1_ID2_EXCLUIDAS=SI")
    print("ID3_ID4_ORGANIZADAS=SI")
    print("REGISTROS_MEDIO="+str(db.execute("SELECT COUNT(*) FROM medio").fetchone()[0]))
finally:
    db.close()
