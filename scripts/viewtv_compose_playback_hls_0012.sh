#!/usr/bin/env bash
# Despliegue aislado de HLS (API y PWA). El worker sigue verificando y descargando.
set -euo pipefail
cd /home/viewtv/projects/viewtv
d=/home/viewtv/projects/viewtv-broker-0013-20261119/deploy
floor_file=/home/viewtv/viewtv-backups/viewtv-auto-floor-0012.txt
[[ -f "$floor_file" ]] || { echo "Falta el corte de seguridad" >&2; exit 1; }
export VIEWTV_AUTO_DOWNLOAD_AFTER_ID="$(cat "$floor_file")"
[[ "$VIEWTV_AUTO_DOWNLOAD_AFTER_ID" =~ ^(0|[1-9][0-9]{0,17})$ ]] || {
  echo "Corte automático inválido" >&2; exit 1;
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
  -f "$d/compose.actualizar-resultados-0012.yaml"
  -f "$d/compose.descartados-opcionales-0012.yaml"
  -f "$d/compose.verificacion-compatible-0012.yaml"
)
current=("${base[@]}" -f "$d/compose.playback-hls-0012.yaml")
preflight() {
 docker compose "${current[@]}" config --format json | python3 -c '
import json,sys
s=json.load(sys.stdin)["services"]
e=s["worker"]["environment"]
assert s["api"]["image"]=="viewtv:playback-hls-api-0012"
assert s["frontend"]["image"]=="viewtv-frontend:playback-hls-0012"
assert s["worker"]["image"]=="viewtv:verificacion-compatible-worker-0012"
assert e["VIEWTV_ENABLE_DOWNLOAD_VERIFICATION"]=="true"
assert e["VIEWTV_ENABLE_AUTO_DOWNLOAD"]=="true"
assert str(e["VIEWTV_AUTO_DOWNLOAD_AFTER_ID"])==sys.argv[1]
assert e["VIEWTV_ENABLE_TORRENT_SUBMIT"]=="false"
assert e["VIEWTV_ENABLE_DOWNLOAD_START"]=="false"
assert e["VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID"]==""
print("PLAYBACK_HLS_PREFLIGHT_OK=1")
' "$VIEWTV_AUTO_DOWNLOAD_AFTER_ID"
}
case "${1:-}" in
 preflight)
  preflight;;
 deploy-api|deploy-frontend)
  preflight
  docker compose "${current[@]}" up -d --no-deps --no-build --force-recreate "${1#deploy-}";;
 rollback-api|rollback-frontend)
  docker compose "${base[@]}" up -d --no-deps --no-build --force-recreate "${1#rollback-}";;
 *)
  echo "Uso: preflight | deploy-api | deploy-frontend | rollback-api | rollback-frontend" >&2
  exit 2;;
esac
