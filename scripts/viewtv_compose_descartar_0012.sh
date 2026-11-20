#!/usr/bin/env bash
# API y PWA 0012 para descartar selecciones incorrectas con confirmación.
# Conserva worker qbit-async, sin activar envíos/inicios ni migrar SQLite.
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
  -f "$d/compose.relevancia-limpieza-0012.yaml"
  -f "$d/compose.qbit-windows-url-0012.yaml"
  -f "$d/compose.qbit-async-0012.yaml"
)
updated=("${base[@]}" -f "$d/compose.descartar-incorrecta-0012.yaml")
case "${1:-}" in
  preflight)
    docker compose "${updated[@]}" config --images
    docker compose "${updated[@]}" config --services
    ;;
  deploy-api|deploy-frontend)
    service="${1#deploy-}"
    docker compose "${updated[@]}" up -d --no-deps --no-build --force-recreate "$service"
    ;;
  rollback-api|rollback-frontend)
    service="${1#rollback-}"
    docker compose "${base[@]}" up -d --no-deps --no-build --force-recreate "$service"
    ;;
  *)
    printf '%s\n' "Uso: preflight | deploy-{api,frontend} | rollback-{api,frontend}" >&2
    exit 2
    ;;
esac
