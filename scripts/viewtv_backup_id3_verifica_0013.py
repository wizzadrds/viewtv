"""Verificador read-only de la copia SQLite real previa a publicar ID #3.

No imprime información de películas, rutas, usuarios ni tokens.
Rechaza actividad histórica y leases de publicación que ya existan.
"""
import sqlite3
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Se requiere ruta del respaldo.")
file = Path(sys.argv[1])
if not file.is_file() or file.is_symlink() or file.stat().st_size < 4096:
    raise SystemExit("Copia ausente, simbólica o inválida.")
with sqlite3.connect(f"file:{file}?mode=ro", uri=True) as connection:
    connection.execute("PRAGMA query_only=ON")
    if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
        raise RuntimeError("La copia no pasó integridad.")
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("La copia tiene claves foráneas inválidas.")
    if connection.execute("SELECT version_num FROM alembic_version").fetchone() != ("0013_cola_organizacion",):
        raise RuntimeError("El esquema no es 0013.")
    rows = connection.execute(
        "SELECT id, estado, progreso, estado_verificacion, organizacion_estado, "
        "organizacion_locked_by, organizacion_locked_until, organizacion_intentos "
        "FROM descarga ORDER BY id"
    ).fetchall()
    if len(rows) != 3 or [x[0] for x in rows] != [1, 2, 3]:
        raise RuntimeError("El conjunto de descargas cambió: revisar antes de publicar.")
    if any(
        x[4] != "no_requerida" or x[5] is not None or x[6] is not None
        for x in rows[:2]
    ):
        raise RuntimeError("Una descarga histórica tiene organización activa.")
    item = rows[2]
    if (
        item[1] != "completada" or item[2] != 1
        or item[3] != "verificada" or item[4] != "pendiente"
        or item[5] is not None or item[6] is not None or item[7] != 0
    ):
        raise RuntimeError("La descarga 3 ya no está pendiente sin lease.")
print("SQLITE_0013_INTEGRIDAD_OK=SI")
print("SQLITE_CLAVES_FORANEAS_OK=SI")
print("DESCARGAS_HISTORICAS_EXCLUIDAS=2")
print("DESCARGA_3_PENDIENTE_Y_SIN_LEASE=SI")
