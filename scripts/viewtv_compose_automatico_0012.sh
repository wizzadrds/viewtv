#!/usr/bin/env bash
# Despliegue reversible: solo nuevas selecciones de VIEWTV tras el opt-in.
set -euo pipefail
cd /home/viewtv/projects/viewtv
d=/home/viewtv/projects/viewtv-broker-0013-20261119/deploy
floor_file=/home/viewtv/viewtv-backups/viewtv-auto-floor-0012.txt
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
)
updated=("${base[@]}" -f "$d/compose.automatico-0012.yaml")

read_floor() {
  if [[ -f "$floor_file" ]]; then
    cat "$floor_file"
  else
    docker exec viewtv-api-1 python -c 'from sqlmodel import Session,select,func; from app.database import engine; from app.models import Descarga; s=Session(engine); print(s.exec(select(func.max(Descarga.id))).one() or 0); s.close()'
  fi
}

case "${1:-}" in
  preflight|deploy-worker|deploy-frontend|rollback-worker|rollback-frontend) ;;
  *) echo "Uso: preflight | deploy-worker | deploy-frontend | rollback-worker | rollback-frontend" >&2; exit 2 ;;
esac

if [[ "${1}" == rollback-* ]]; then
  service="${1#rollback-}"
  docker compose "${base[@]}" up -d --no-deps --no-build --force-recreate "$service"
  exit
fi

floor="$(read_floor)"
if [[ ! "$floor" =~ ^(0|[1-9][0-9]{0,17})$ ]] || (( floor >= 9223372036854775807 )); then
  echo "ABORTADO: corte de ID no válido" >&2
  exit 1
fi
export VIEWTV_AUTO_DOWNLOAD_AFTER_ID="$floor"

docker compose "${updated[@]}" config --format json | python3 -c '
import json,sys
config=json.load(sys.stdin)["services"]
w=config["worker"]
e=w["environment"]
assert config["frontend"]["image"]=="viewtv-frontend:automatico-0012"
assert w["image"]=="viewtv:auto-worker-0012"
assert e["VIEWTV_ENABLE_AUTO_DOWNLOAD"]=="true"
assert str(e["VIEWTV_AUTO_DOWNLOAD_AFTER_ID"])==sys.argv[1]
assert e["VIEWTV_ENABLE_TORRENT_SUBMIT"]=="false"
assert e["VIEWTV_ENABLE_DOWNLOAD_START"]=="false"
assert e["VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID"]==""
print("AUTO_PREFLIGHT_OK=1; FLOOR_ID="+sys.argv[1])
' "$floor"

if [[ "${1}" == "preflight" ]]; then
  docker compose "${updated[@]}" config --images
  exit
fi

if [[ "${1}" == "deploy-worker" && ! -f "$floor_file" ]]; then
  # Corte grabado ANTES de activar el worker, no se sobrescribe nunca.
  umask 077
  printf '%s\n' "$floor" > "$floor_file"
  chmod 600 "$floor_file"
fi

service="${1#deploy-}"
docker compose "${updated[@]}" up -d --no-deps --no-build --force-recreate "$service"
