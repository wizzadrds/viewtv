"""Diagnóstico local SIN sesión, solo totales, sin títulos, rutas ni borrados."""
import sqlite3
from pathlib import Path

from app.almacenamiento_archivos import (
    _cache_own_dir,
    tamanio_logico,
    volumen,
)
from app.config import get_settings

settings = get_settings()
disk = volumen(settings.cache_dir)
assert disk and disk["total_bytes"] > 0
print("DISCO_LIBRE_GIB=" + str(round(disk["libre_bytes"] / 1024 ** 3, 1)))
for code, path in (
    ("BIBLIOTECA_PELICULAS", Path("/media/Peliculas")),
    ("DESCARGAS_TEMPORALES", Path("/media/descargas_temporales")),
    ("CACHE_TOTAL", settings.cache_dir),
):
    result = tamanio_logico(path)
    print(code + "_GIB=" + str(round(result["bytes"] / 1024 ** 3, 2)))
    print(code + "_ARCHIVOS=" + str(result["archivos"]))
    print(code + "_COMPLETO=" + ("SI" if result["completo"] else "NO"))
print("CACHE_GESTIONADA=" + ("SI" if _cache_own_dir(settings.cache_dir) else "NO"))
print("CUOTA_CACHE_CONFIGURADA_GIB=" + str(settings.cache_quota_gb))
db = sqlite3.connect("file:/data/viewtv.db?mode=ro", uri=True)
db.execute("PRAGMA query_only=ON")
assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
print("SQLITE_VERSION=" + db.execute("SELECT version_num FROM alembic_version").fetchone()[0])
print("VISTAS_MANUALES=" + str(db.execute("SELECT COUNT(*) FROM pelicula_vista").fetchone()[0]))
print("RETIRADAS_PENDIENTES=" + str(db.execute(
    "SELECT COUNT(*) FROM solicitud_retirada WHERE estado='pendiente_revision'"
).fetchone()[0]))
print("OPERACIONES_DE_BORRADO=0")
