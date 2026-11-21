"""Identificar solo metadatos de IDs nuevas para el ensayo 0013.

No muestra títulos, rutas, hashes, resultados, PIN ni credenciales.
Abrir exclusivamente la base montada en modo SOLO LECTURA.
"""
import sqlite3
from pathlib import Path

DATABASE = Path("/data/viewtv.db")
AFTER_ID = 2
VALID_STATES = {
    "pendiente", "seleccionada", "descargando", "completada", "fallida",
    "cancelada", "error", "pausada", "verificando", "verificada", "descartada",
}
VALID_VERIFICATION = {
    "pendiente", "verificando", "verificada", "fallida",
    "requiere_revision", "no_requerida",
}
VALID_ORGANIZATION = {
    "pendiente", "organizada", "requiere_revision", "no_requerida",
}


def main() -> None:
    if not DATABASE.is_file() or DATABASE.is_symlink():
        raise SystemExit("No existe la base de datos de producción.")
    db = sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        revision = db.execute("SELECT version_num FROM alembic_version").fetchone()
        if revision != ("0013_cola_organizacion",):
            raise SystemExit("No se está utilizando 0013.")
        rows = db.execute(
            "SELECT id, estado, progreso, estado_verificacion, "
            "organizacion_estado FROM descarga WHERE id > ? ORDER BY id",
            (AFTER_ID,),
        ).fetchall()
        print(f"DESCARGAS_NUEVAS={len(rows)}")
        for download_id, state, progress, verification, organization in rows:
            if (
                not isinstance(download_id, int)
                or download_id <= AFTER_ID
                or state not in VALID_STATES
                or verification not in VALID_VERIFICATION
                or organization not in VALID_ORGANIZATION
                or not isinstance(progress, (int, float))
            ):
                print(f"ID={download_id} ESTADO=requiere_revision_manual")
                continue
            print(
                f"ID={download_id} DESCARGA={state} "
                f"PROGRESO={progress:.1%} "
                f"VERIFICACION={verification} "
                f"PUBLICACION={organization}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
