"""Inspección segura de una COPIA SQLite al ensayar Alembic 0012 ↔ 0013.

No revela perfiles, títulos, descargas, medios, secretos ni claves.
Abre la base especificada EN MODO READ-ONLY sin crearla.
"""

import sqlite3
import sys
from pathlib import Path

VALID_REVISIONS = {"0012_inicio_torrent", "0013_cola_organizacion"}
ORGANIZATION_COLUMNS = {
    "organizacion_estado",
    "organizacion_locked_by",
    "organizacion_locked_until",
    "organizacion_disponible_desde",
    "organizacion_intentos",
    "organizacion_ultimo_error",
}


def verify_snapshot(database: Path, expected_revision: str) -> dict[str, object]:
    if expected_revision not in VALID_REVISIONS:
        raise ValueError("Revisión de SQLite no autorizada.")
    if not database.is_absolute() or not database.is_file():
        raise ValueError("La copia SQLite debe existir.")
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        fk_errors = db.execute("PRAGMA foreign_key_check").fetchall()
        revision = db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        columns = {item[1] for item in db.execute("PRAGMA table_info(descarga)")}
        counts = {}
        for table in ("perfil", "medio", "solicitud", "descarga", "resultado_busqueda"):
            counts[table] = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if expected_revision == "0013_cola_organizacion":
            states = db.execute(
                "SELECT COUNT(*) FROM descarga WHERE organizacion_estado != 'no_requerida'"
            ).fetchone()[0]
        else:
            states = 0

    if integrity != "ok" or fk_errors:
        raise ValueError("La integridad de la copia SQLite es incorrecta.")
    if revision != expected_revision:
        raise ValueError("La revisión real no coincide con la esperada.")
    has_organization = ORGANIZATION_COLUMNS.issubset(columns)
    if has_organization != (expected_revision == "0013_cola_organizacion"):
        raise ValueError("Columnas 0013 incongruentes con la revisión.")
    if states:
        raise ValueError("Las descargas históricas no deben entrar en el organizador.")

    return {
        "integridad": "ok",
        "foreign_keys_errores": 0,
        "revision": revision,
        "organizacion_columnas": has_organization,
        "descargas_pendientes_organizacion": states,
        "totales": counts,
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: probe.py /data/viewtv.db REVISION")
    result = verify_snapshot(Path(sys.argv[1]), sys.argv[2])
    print(f"SQLITE_REVISION={result['revision']}")
    print(f"INTEGRIDAD={result['integridad']}")
    print(f"ORGANIZACION_COLUMNAS={result['organizacion_columnas']}")
    print(f"ORGANIZACION_PENDIENTES={result['descargas_pendientes_organizacion']}")
    print(f"CONTEOS={result['totales']}")
