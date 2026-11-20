#!/usr/bin/env bash
# Comprobar configuración 0012 y actualizar solo worker sin dar permiso a torrents.
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
  -f "$d/compose.descartar-incorrecta-0012.yaml"
)
actual=("${base[@]}" -f "$d/compose.validacion-tamano-0012.yaml")
case "${1:-}" in
  preflight)
    docker compose "${actual[@]}" config --images
    docker compose "${actual[@]}" config --services
    ;;
  deploy-worker)
    docker compose "${actual[@]}" up -d --no-deps --no-build --force-recreate worker
    ;;
  rollback-worker)
    docker compose "${base[@]}" up -d --no-deps --no-build --force-recreate worker
    ;;
  *)
    echo "Uso: preflight | deploy-worker | rollback-worker" >&2
    exit 2
    ;;
esac
