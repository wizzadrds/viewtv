#!/usr/bin/env bash
# Despliegue reversible de tamaños/hashes canonicos del archivo .torrent.
# Mantiene los permisos de alta e inicio totalmente desactivados.
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
  -f "$d/compose.preseleccion-real-0012.yaml"
)
current=("${base[@]}" -f "$d/compose.tamano-canonico-0012.yaml")
case "${1:-}" in
  preflight)
    docker compose "${current[@]}" config --images
    docker compose "${current[@]}" config --services
    ;;
  deploy-api|deploy-frontend|deploy-worker)
    svc="${1#deploy-}"
    docker compose "${current[@]}" up -d --no-deps --no-build --force-recreate "$svc"
    ;;
  rollback-api|rollback-frontend|rollback-worker)
    svc="${1#rollback-}"
    docker compose "${base[@]}" up -d --no-deps --no-build --force-recreate "$svc"
    ;;
  *)
    echo "Uso: preflight | deploy-{api,frontend,worker} | rollback-{api,frontend,worker}" >&2
    exit 2
    ;;
esac
