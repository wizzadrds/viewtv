#!/usr/bin/env bash
# API y frontend: verificar tamaño REAL antes de elegir. Reversión aislada.
# El worker y todas las flags de envío/inicio permanecen desactivados.
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
  -f "$d/compose.validacion-tamano-0012.yaml"
)
current=("${base[@]}" -f "$d/compose.preseleccion-real-0012.yaml")
case "${1:-}" in
  preflight)
    docker compose "${current[@]}" config --images
    docker compose "${current[@]}" config --services
    ;;
  deploy-api|deploy-frontend)
    svc="${1#deploy-}"
    docker compose "${current[@]}" up -d --no-deps --no-build --force-recreate "$svc"
    ;;
  rollback-api|rollback-frontend)
    svc="${1#rollback-}"
    docker compose "${base[@]}" up -d --no-deps --no-build --force-recreate "$svc"
    ;;
  *)
    echo "Uso: preflight | deploy-api | deploy-frontend | rollback-api | rollback-frontend" >&2
    exit 2
    ;;
esac
