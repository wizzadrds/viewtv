"""Ensayo de la migración 0014 ↔ 0015 sobre copia efímera real, sin red."""
import subprocess

DB_NAME = "api-resultados-predeploy-20261122-225105.db"
COMMAND = """
set -eu
cp /backup/""" + DB_NAME + """ /tmp/viewtv-clone.db
cd /opt/viewtv/backend
alembic current | grep -q 0014_identidad_tmdb_solicitud
python - <<'PY'
import sqlite3
db = sqlite3.connect('/tmp/viewtv-clone.db')
for table in ('perfil', 'medio', 'solicitud', 'descarga'):
    open('/tmp/count-' + table, 'w').write(str(
        db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
    ))
assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert db.execute('PRAGMA foreign_key_check').fetchall() == []
PY
alembic upgrade head >/dev/null
alembic current | grep -q 0015_gestion_espacio_vistas
python - <<'PY'
import sqlite3
db=sqlite3.connect('/tmp/viewtv-clone.db')
for table in ('perfil', 'medio', 'solicitud', 'descarga'):
    count = str(db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0])
    assert count == open('/tmp/count-' + table).read()
for table in ('pelicula_vista','solicitud_retirada'):
    assert db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] == 0
assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert db.execute('PRAGMA foreign_key_check').fetchall() == []
print('CLON_MIGRADO_0015=PASS')
PY
alembic downgrade 0014_identidad_tmdb_solicitud >/dev/null
alembic current | grep -q 0014_identidad_tmdb_solicitud
python - <<'PY'
import sqlite3
db=sqlite3.connect('/tmp/viewtv-clone.db')
for table in ('perfil', 'medio', 'solicitud', 'descarga'):
    count = str(db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0])
    assert count == open('/tmp/count-' + table).read()
assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert db.execute('PRAGMA foreign_key_check').fetchall() == []
print('CLON_REVERSIBLE_0014=PASS')
PY
alembic upgrade head >/dev/null
alembic current | grep -q 0015_gestion_espacio_vistas
echo CLON_MIGRACION_0014_0015_0014_0015=PASS
"""
result = subprocess.run(
    [
        "docker", "run", "--rm", "--network", "none", "--user", "0:0",
        "-v", "/home/viewtv/viewtv-backups:/backup:ro",
        "-e", "DATABASE_URL=sqlite:////tmp/viewtv-clone.db",
        "--entrypoint", "sh", "viewtv:gestion-espacio-api-0015",
        "-ec", COMMAND,
    ],
    capture_output=True, text=True, timeout=120, check=False,
)
if result.returncode != 0:
    raise SystemExit(f"ENSAYO_MIGRACION=FALLO (código {result.returncode})")
print(result.stdout.strip())
