#!/usr/bin/env bash
# Despliegue reversible SOLO de la PWA; no reinicia worker, API ni torrents.
set -euo pipefail
cd /home/viewtv/projects/viewtv
d=/home/viewtv/projects/viewtv-broker-0013-20261119/deploy
floor_file=/home/viewtv/viewtv-backups/viewtv-auto-floor-0012.txt
if [[ ! -f "$floor_file" ]]; then
  echo "Falta el corte de seguridad de la cola automatica" >&2; exit 1
fi
export VIEWTV_AUTO_DOWNLOAD_AFTER_ID="$(cat "$floor_file")"
if [[ ! "$VIEWTV_AUTO_DOWNLOAD_AFTER_ID" =~ ^(0|[1-9][0-9]{0,17})$ ]]; then
  echo "Corte de seguridad invalido" >&2; exit 1
fi
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
  -f "$d/compose.tamano-canonico-0012.yaml"
  -f "$d/compose.automatico-0012.yaml"
)
current=("${base[@]}" -f "$d/compose.descartados-claros-0012.yaml")
case "${1:-}" in
  preflight)
    docker compose "${current[@]}" config --images
    ;;
  deploy)
    docker compose "${current[@]}" up -d --no-deps --no-build --force-recreate frontend
    ;;
  rollback)
    docker compose "${base[@]}" up -d --no-deps --no-build --force-recreate frontend
    ;;
  *)
    echo "Uso: preflight | deploy | rollback" >&2
    exit 2
    ;;
esac
