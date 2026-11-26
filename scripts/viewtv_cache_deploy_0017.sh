#!/usr/bin/env bash
# Instalación del volumen aislado y de dos imágenes. Sin borrar volúmenes.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
new="$root/deploy/compose.cache-propia-0017.yaml"
rollback="$root/deploy/compose.cache-propia-rollback-0017.yaml"
prev="$root/deploy/compose.publicador-compatible-api-0016.yaml"
mode="${1:-check}"
case "$mode" in check|deploy|check-rollback|rollback) ;; *) exit 2;; esac
test "$(git -C "$root" branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$legacy/.env"
backup=/home/viewtv/viewtv-backups/gestion-cache-propia-pre-20261126-195942.tar.gz
test "$(sha256sum "$backup" | cut -d' ' -f1)" = 40d6b82f5790b000dc462cea4c3cf2cd39096c3b57dd5473d96cdeda1b0da129
tar -tzf "$backup" >/dev/null

export VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1
export VIEWTV_ENABLE_AUTO_DOWNLOAD=true
export VIEWTV_ENABLE_DOWNLOAD_START=false
export VIEWTV_ENABLE_DOWNLOAD_VERIFICATION=true
export VIEWTV_ENABLE_ORGANIZATION=false
export VIEWTV_ENABLE_TORRENT_SUBMIT=false
export VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=''
export VIEWTV_WINDOWS_PUBLICATION_DOWNLOAD_ID=''

files="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' viewtv-api-1)"
test -n "$files"
IFS=',' read -ra previous <<<"$files"
test "${#previous[@]}" -ge 27
last="${previous[${#previous[@]}-1]}"
if [[ "$mode" == check || "$mode" == deploy ]]; then
  test "$last" = "$prev"
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:publicador-compatible-api-0016
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:gestion-espacio-0015
  target="$new"
  expected=new
else
  test "$last" = "$new"
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:cache-propia-api-0017
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:cache-propia-0017
  target="$rollback"
  expected=rollback
fi
test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:gestion-espacio-worker-0015
compose=(-p viewtv --project-directory "$legacy")
has_prev=false
for file in "${previous[@]}"; do
  case "$file" in
    "$legacy/compose.yaml"|"$legacy/compose.production.yaml"|"$legacy/compose.release-0012.yaml"|/home/viewtv/viewtv-backups/compose-verification-enabled.yaml|"$root"/deploy/*.yaml)
      test -f "$file"
      compose+=(-f "$file")
      if [[ "$file" == "$prev" ]]; then has_prev=true; fi
      ;;
    *) echo COMPOSE_NO_AUTORIZADO >&2; exit 3;;
  esac
done
test "$has_prev" = true
compose+=(-f "$target")
docker compose "${compose[@]}" config --quiet
docker compose "${compose[@]}" config --format json |
  python3 "$root/scripts/viewtv_cache_compose_verify_0017.py" "$expected"
if [[ "$mode" == check || "$mode" == check-rollback ]]; then
  echo CACHE_PROPIA_PREFLIGHT=PASS
  exit 0
fi

# Sólo API y frontend. No recrear worker, Jellyfin, catálogo ni qBittorrent.
docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate frontend
if [[ "$mode" == deploy ]]; then
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:cache-propia-api-0017
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:cache-propia-0017
  docker exec viewtv-api-1 python -m worker.organization_windows_cli status |
    python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["estado"]=="listo" and r["modo"]=="general"'
  docker exec viewtv-api-1 python -c 'from pathlib import Path; from app.cache_privada import estado_cache; d=estado_cache(Path("/cache-gestionada"),80*1024**3); assert d["estado"]=="vacia_sin_inicializar" and d["bytes"]==0'
  echo CACHE_PROPIA_0017_DESPLEGADA=SI
else
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:publicador-compatible-api-0016
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:gestion-espacio-0015
  echo CACHE_PROPIA_0017_LOGICA_REVERTIDA_SIN_BORRAR_DATOS=SI
fi
