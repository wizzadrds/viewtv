"""Ejecuta la migración 0013->0014->0013 en un CLON EFÍMERO sin red."""
import subprocess

BACKUP = "/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-222154.db"
NAME = BACKUP.rsplit("/", 1)[-1]
DOCKER_CMD = r"""
set -eu
cp /backup/""" + NAME + r""" /tmp/viewtv-clone.db
cd /opt/viewtv/backend
alembic current | grep -q 0013_cola_organizacion
alembic upgrade head >/dev/null
alembic current | grep -q 0014_identidad_tmdb_solicitud
python - <<'PY'
import sqlite3
con = sqlite3.connect('/tmp/viewtv-clone.db')
assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert con.execute('PRAGMA foreign_key_check').fetchall() == []
columns = [x[1] for x in con.execute('PRAGMA table_info(solicitud)')]
assert 'tmdb_id' in columns
assert con.execute('SELECT COUNT(*) FROM solicitud WHERE tmdb_id IS NOT NULL').fetchone()[0] == 0
print('CLON_SQLITE_0014_INTEGRIDAD=OK')
PY
alembic downgrade 0013_cola_organizacion >/dev/null
alembic current | grep -q 0013_cola_organizacion
python - <<'PY'
import sqlite3
con = sqlite3.connect('/tmp/viewtv-clone.db')
assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert con.execute('PRAGMA foreign_key_check').fetchall() == []
assert 'tmdb_id' not in [x[1] for x in con.execute('PRAGMA table_info(solicitud)')]
print('CLON_REVERSIÓN_0013_INTEGRIDAD=OK')
PY
alembic upgrade head >/dev/null
alembic current | grep -q 0014_identidad_tmdb_solicitud
echo 'CLON_MIGRACION_0013_0014_REVERSIBLE=SI'
"""
proc = subprocess.run(
    [
        "docker", "run", "--rm", "--network", "none", "--user", "0:0",
        "-v", "/home/viewtv/viewtv-backups:/backup:ro",
        "-e", "DATABASE_URL=sqlite:////tmp/viewtv-clone.db",
        "--entrypoint", "sh",
        "viewtv:cohesion-caratula-api-0014", "-ec", DOCKER_CMD,
    ],
    text=True, capture_output=True, timeout=120, check=False,
)
if proc.returncode:
    # No imprimir el SQL ni URL privada de ningún entorno.
    raise SystemExit(f"CLON_MIGRACION=ERROR (codigo {proc.returncode})")
print(proc.stdout.strip())
