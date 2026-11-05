#!/usr/bin/env bash
# VIEWTV — backup diario desde Ubuntu/WSL hacia el SSD de Windows.
set -Eeuo pipefail

cd /home/viewtv/projects/viewtv

BACKUP_HOST_DIR="/mnt/c/VIEWTV/backups"
STAGING_DIR="$BACKUP_HOST_DIR/.viewtv-staging"

if [[ ! -d /mnt/c/VIEWTV ]]; then
    echo "ERROR: no está disponible /mnt/c/VIEWTV." >&2
    exit 1
fi
mkdir -p "$BACKUP_HOST_DIR" "$STAGING_DIR"

# Asegura que la API esté levantada y lista.
docker compose up -d api
for attempt in $(seq 1 60); do
    if curl --fail --silent http://127.0.0.1:8000/health >/dev/null 2>&1; then
        break
    fi
    if [[ "$attempt" -eq 60 ]]; then
        echo "ERROR: la API no respondió correctamente en 5 minutos." >&2
        exit 1
    fi
    sleep 5
done

# El backup se crea en el almacenamiento efímero del contenedor, NO en un
# bind mount de Windows. Después se exporta explícitamente por stdout/tar.
backup_output="$(
    docker compose exec -T api sh -c \
        'cd /opt/viewtv/backend && BACKUP_DIR=/tmp/viewtv-backups python scripts/backup_db.py' 2>&1
)" || {
    printf '%s\\n' "$backup_output" >&2
    echo "ERROR: falló la creación/validación SQLite dentro del contenedor." >&2
    exit 1
}
printf '%s\\n' "$backup_output"

backup_path="$(printf '%s\\n' "$backup_output" | sed -n 's/^Backup verificado: //p' | tail -n 1)"
case "$backup_path" in
    /tmp/viewtv-backups/viewtv-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].db) ;;
    *)
        echo "ERROR: no se pudo identificar el archivo de backup generado." >&2
        exit 1
        ;;
esac

backup_name="${backup_path##*/}"
staged_file="$STAGING_DIR/$backup_name"
final_file="$BACKUP_HOST_DIR/$backup_name"

if [[ -e "$final_file" ]]; then
    echo "ERROR: ya existe el destino $final_file; no se sobrescribirá." >&2
    exit 1
fi

# Transferencia explícita: evita depender del bind mount /backups de Docker Desktop.
docker compose exec -T api tar -C /tmp/viewtv-backups -cf - "$backup_name" \
    | tar -C "$STAGING_DIR" -xf -

if [[ ! -s "$staged_file" ]]; then
    echo "ERROR: la transferencia al SSD no produjo un archivo válido." >&2
    exit 1
fi

# Validar el archivo ya transferido al SSD con el SQLite de WSL.
python3 - "$staged_file" <<'PY'
import sqlite3
import sys
from pathlib import Path

path = Path(sys.argv[1]).resolve()
with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()
    if integrity is None or integrity[0] != "ok":
        raise SystemExit(f"ERROR: integrity_check falló en {path}: {integrity}")
    profiles = connection.execute("SELECT count(*) FROM perfil").fetchone()[0]
    migration = connection.execute(
        "SELECT version_num FROM alembic_version"
    ).fetchone()[0]
    print(
        f"Backup en SSD validado: {path.name}; "
        f"integridad={integrity[0]}; perfiles={profiles}; migración={migration}"
    )
PY

# Publicar el archivo validado en la carpeta visible desde Windows.
mv -- "$staged_file" "$final_file"
test -s "$final_file"

# La retención se aplica en el SSD y solo después de publicar una copia nueva.
retention_days="$(docker compose exec -T api sh -c 'printf "%s" "${BACKUP_RETENTION_DAYS:-30}"')"
if [[ ! "$retention_days" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: BACKUP_RETENTION_DAYS no es un entero positivo." >&2
    exit 1
fi
find "$BACKUP_HOST_DIR" -maxdepth 1 -type f -name 'viewtv-*.db' \
    -mtime +"$retention_days" -print -delete

rmdir "$STAGING_DIR" 2>/dev/null || true
echo "Backup VIEWTV completado y verificado en SSD: $final_file"
