#!/usr/bin/env bash
# VIEWTV — ejecución del backup desde Ubuntu/WSL.
set -Eeuo pipefail

cd /home/viewtv/projects/viewtv

# Asegura que la API esté levantada. Docker Compose puede tardar si Docker
# Desktop acaba de iniciar; el bucle espera a que /health responda.
docker compose up -d api

for attempt in $(seq 1 60); do
    if curl --fail --silent http://127.0.0.1:8000/health >/dev/null 2>&1; then
        docker compose exec -T api sh -c 'cd /opt/viewtv/backend && python scripts/backup_db.py'
        exit 0
    fi
    sleep 5
done

echo "ERROR: la API no respondió correctamente en 5 minutos." >&2
exit 1
