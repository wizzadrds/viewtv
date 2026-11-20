#!/usr/bin/env bash
# Operar desde la rama autorizada; no edita el repositorio principal.
set -euo pipefail
cd /home/viewtv/projects/viewtv
d=/home/viewtv/projects/viewtv-broker-0013-20261119/deploy
base=(
  -f compose.yaml
  -f compose.production.yaml
  -f /home/viewtv/viewtv-backups/compose-verification-enabled.yaml
  -f compose.release-0012.yaml
  -f "$d/compose.catalog-auto-0012.yaml"
  -f "$d/compose.descargas-auto-0012.yaml"
  -f "$d/compose.solicitudes-0012.yaml"
  -f "$d/compose.seleccion-sin-envio-0012.yaml"
  -f "$d/compose.ensayo-torrent-unico-0012.yaml"
  -f "$d/compose.inicio-torrent-unico-0012.yaml"
  -f "$d/compose.resultados-fecha-0012.yaml"
)
actual=("${base[@]}" -f "$d/compose.relevancia-limpieza-0012.yaml")
case "${1:-}" in
  preflight)
    docker compose "${actual[@]}" config --images
    docker compose "${actual[@]}" config --services
    ;;
  deploy-api|deploy-worker|deploy-frontend)
    servicio="${1#deploy-}"
    docker compose "${actual[@]}" up -d --no-deps --no-build --force-recreate "$servicio"
    ;;
  rollback-api|rollback-worker|rollback-frontend)
    servicio="${1#rollback-}"
    docker compose "${base[@]}" up -d --no-deps --no-build --force-recreate "$servicio"
    ;;
  *)
    echo "Uso: preflight | deploy-{api,worker,frontend} | rollback-{api,worker,frontend}" >&2
    exit 2
    ;;
esac
