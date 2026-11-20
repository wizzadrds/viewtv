"""Respaldo SQLite consistente y verificable de API 0012.
Se ejecuta en contenedor efímero con /data en solo lectura y /recovery aislado.
No consulta .env ni modifica la base de datos origen.
"""

import hashlib
import os
import sqlite3
from pathlib import Path

SOURCE = Path("/data/viewtv.db")
DEST = Path("/recovery/viewtv-api-0012-before-recreate.db")


def main():
    if not SOURCE.is_file() or SOURCE.is_symlink():
        raise RuntimeError("Origen SQLite no reconocido")
    if not DEST.parent.is_dir() or DEST.parent.is_symlink() or DEST.exists():
        raise RuntimeError("Destino inexistente o ya ocupado")
    fd = os.open(DEST, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    source = sqlite3.connect("file:/data/viewtv.db?mode=ro", uri=True, timeout=30)
    target = sqlite3.connect(str(DEST), timeout=30)
    try:
        source.backup(target, pages=64, sleep=0.05)
        target.commit()
    finally:
        target.close()
        source.close()
    os.chmod(DEST, 0o600)
    copy = sqlite3.connect(f"file:{DEST}?mode=ro", uri=True)
    try:
        integrity = copy.execute("PRAGMA integrity_check").fetchone()[0]
        revisions = copy.execute("SELECT version_num FROM alembic_version").fetchall()
        foreign_keys = copy.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        copy.close()
    if integrity != "ok" or revisions != [("0012_inicio_torrent",)] or foreign_keys:
        raise RuntimeError(
            f"Respaldo invalido: integrity={integrity!r}, "
            f"revisions={len(revisions)}, fk_errors={len(foreign_keys)}"
        )
    h = hashlib.sha256()
    with DEST.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    print(
        f"COPIA_SQLITE_VERIFICADA=SI REVISION=0012_inicio_torrent "
        f"BYTES={DEST.stat().st_size} SHA256={h.hexdigest()} "
        "ERRORES_CLAVES_FORANEAS=0"
    )


if __name__ == "__main__":
    main()
