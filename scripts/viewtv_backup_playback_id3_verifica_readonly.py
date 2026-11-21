"""Preflight en copia SQLite previa a cambio API/HLS; no escribe ni expone secretos."""
import sqlite3
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Ruta de copia requerida.")
p=Path(sys.argv[1])
if not p.is_file() or p.is_symlink() or p.stat().st_size < 4096:
    raise SystemExit("Copia ausente o inválida.")
conn=sqlite3.connect(f"file:{p}?mode=ro",uri=True)
try:
    conn.execute("PRAGMA query_only=ON")
    if conn.execute("PRAGMA integrity_check").fetchone()!=("ok",):
        raise RuntimeError("SQLite no íntegra")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Claves foráneas no válidas")
    if conn.execute("SELECT version_num FROM alembic_version").fetchone()!=("0013_cola_organizacion",):
        raise RuntimeError("Revision inesperada")
    rows=conn.execute(
        "SELECT id, estado, progreso, estado_verificacion, organizacion_estado, "
        "organizacion_locked_by, organizacion_locked_until FROM descarga ORDER BY id"
    ).fetchall()
    if len(rows)!=3 or [r[0] for r in rows]!=[1,2,3]:
        raise RuntimeError("IDs de descargas cambiaron")
    if any(r[4]!="no_requerida" or r[5] is not None or r[6] is not None for r in rows[:2]):
        raise RuntimeError("Histórico en cola")
    d=rows[2]
    if (d[1]!="completada" or d[2]!=1 or d[3]!="verificada"
        or d[4]!="organizada" or d[5] is not None or d[6] is not None):
        raise RuntimeError("Descarga ID3 distinta de organizada")
    print("SQLITE_INTEGRIDAD_Y_FK=OK")
    print("SQLITE_ALEMBIC=0013_cola_organizacion")
    print("DESCARGAS_HISTORICAS_EXCLUIDAS=2")
    print("DESCARGA_3_ORGANIZADA=SI")
    print("CATALOGO_REGISTROS="+str(conn.execute("SELECT COUNT(*) FROM medio").fetchone()[0]))
finally:
    conn.close()
