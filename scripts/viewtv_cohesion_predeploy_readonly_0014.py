"""Preflight agregado de SQLite, solo lectura y sin títulos ni hashes."""
import sqlite3

with sqlite3.connect("file:/data/viewtv.db?mode=ro", uri=True) as db:
    version = db.execute("SELECT version_num FROM alembic_version").fetchone()
    assert version is not None
    print("REVISION_SQLITE=" + version[0])
    pending = db.execute(
        "SELECT COUNT(*) FROM solicitud WHERE estado IN ('pendiente','procesando')"
    ).fetchone()[0]
    selected = db.execute(
        "SELECT COUNT(*) FROM descarga WHERE estado IN "
        "('seleccionada','enviada','descargando','pausada')"
    ).fetchone()[0]
    print("SOLICITUDES_PENDIENTES_O_PROCESANDO=" + str(pending))
    print("DESCARGAS_ACTIVAS=" + str(selected))
    print("INTEGRIDAD=" + db.execute("PRAGMA integrity_check").fetchone()[0])
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    print("CLAVES_FORANEAS=OK")
