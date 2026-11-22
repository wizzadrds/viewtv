"""Copia online consistente del volumen exclusivamente de fichas TMDB.

Ejecutar desde contenedor efímero, volumen fuente montado read-only.
Nunca imprime claves ni títulos. No lee/escribe viewtv.db ni /media.
"""
import sqlite3
from pathlib import Path

source = Path("/catalogo/metadatos.db")
target = Path("/backup/metadatos-pre-ampliacion-20261122-200700.db")
if not source.is_file() or target.exists():
    raise SystemExit("CATALOGO_BACKUP_ORIGEN_O_DESTINO_NO_VALIDO")
with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src:
    src.execute("PRAGMA query_only=ON")
    if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise SystemExit("CATALOGO_ORIGEN_INCONSISTENTE")
    old_count = src.execute("SELECT COUNT(*) FROM ficha").fetchone()[0]
    with sqlite3.connect(target) as dst:
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise SystemExit("CATALOGO_COPIA_INCONSISTENTE")
        count = dst.execute("SELECT COUNT(*) FROM ficha").fetchone()[0]
        if count != old_count or count < 100:
            raise SystemExit("CATALOGO_BACKUP_RECUENTO_INCORRECTO")
print("COPIA_METADATOS_SQLITE_INTEGRA=SI")
print("COPIA_METADATOS_FICHAS="+str(count))
