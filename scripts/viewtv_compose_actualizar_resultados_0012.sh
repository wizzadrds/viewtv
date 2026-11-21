#!/usr/bin/env bash
# Corrección de enlaces 404 y rebúsqueda. Solo API/frontend.
# Mantiene la cola automática acotada y no toca qBittorrent.
set -euo pipefail
cd /home/viewtv/projects/viewtv
d=/home/viewtv/projects/viewtv-broker-0013-20261119/deploy
floor_file=/home/viewtv/viewtv-backups/viewtv-auto-floor-0012.txt
[[ -f "$floor_file" ]] || { echo "Falta el corte de seguridad" >&2; exit 1; }
export VIEWTV_AUTO_DOWNLOAD_AFTER_ID="$(cat "$floor_file")"
[[ "$VIEWTV_AUTO_DOWNLOAD_AFTER_ID" =~ ^(0|[1-9][0-9]{0,17})$ ]] || {
  echo "Corte inválido" >&2; exit 1;
}
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
  -f "$d/compose.descartados-claros-0012.yaml"
)
current=("${base[@]}" -f "$d/compose.actualizar-resultados-0012.yaml")
preflight() {
  docker compose "${current[@]}" config --format json | python3 -c '
import sys,json
svc=json.load(sys.stdin)["services"]
env=svc["worker"]["environment"]
assert svc["api"]["image"]=="viewtv:actualizar-resultados-api-0012"
assert svc["frontend"]["image"]=="viewtv-frontend:actualizar-resultados-0012"
assert svc["worker"]["image"]=="viewtv:auto-worker-0012"
assert env["VIEWTV_ENABLE_AUTO_DOWNLOAD"]=="true"
assert str(env["VIEWTV_AUTO_DOWNLOAD_AFTER_ID"])==sys.argv[1]
assert env["VIEWTV_ENABLE_TORRENT_SUBMIT"]=="false"
assert env["VIEWTV_ENABLE_DOWNLOAD_START"]=="false"
assert env["VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID"]==""
print("PREFLIGHT_404_REBUSQUEDA_OK=1")
' "$VIEWTV_AUTO_DOWNLOAD_AFTER_ID"
}
case "${1:-}" in
  preflight)
    preflight
    docker compose "${current[@]}" config --images
    ;;
  deploy-api|deploy-frontend)
    preflight
    docker compose "${current[@]}" up -d --no-deps --no-build --force-recreate "${1#deploy-}"
    ;;
  rollback-api|rollback-frontend)
    docker compose "${base[@]}" up -d --no-deps --no-build --force-recreate "${1#rollback-}"
    ;;
  *)
    echo "Uso: preflight | deploy-api | deploy-frontend | rollback-api | rollback-frontend" >&2
    exit 2
    ;;
esac
