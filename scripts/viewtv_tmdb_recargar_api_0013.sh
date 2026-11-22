#!/usr/bin/env bash
# Recarga solo API para leer TMDB_API_KEY del .env privado de producción.
# Se ejecuta únicamente en la worktree autorizada y con tarea Windows pausada.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
mode="${1:-check}"
case "$mode" in check|apply) ;; *) exit 2 ;; esac

test "$(git -C "$root" branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$legacy/.env"
test -f "$root/deploy/compose.categorias-netflix-0013.yaml"
test -f /home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-014729.db
test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:categorias-0013-api-conservative
test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:categorias-0013-candidate
test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:release-0013-worker-candidate
test "$(docker exec viewtv-worker-1 printenv VIEWTV_WINDOWS_PUBLICATION_MODE)" = disabled
test "$(docker exec viewtv-worker-1 printenv VIEWTV_ENABLE_ORGANIZATION)" = false

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
IFS=',' read -ra original <<<"$files"
test "${#original[@]}" -ge 25
test "${original[${#original[@]}-1]}" = "$root/deploy/compose.categorias-netflix-0013.yaml"
compose=(-p viewtv --project-directory "$legacy")
for path in "${original[@]}"; do
  case "$path" in
    "$legacy/compose.yaml"|"$legacy/compose.production.yaml"|"$legacy/compose.release-0012.yaml"|/home/viewtv/viewtv-backups/compose-verification-enabled.yaml|"$root"/deploy/*.yaml)
      test -f "$path"
      compose+=(-f "$path")
      ;;
    *) echo COMPOSE_NO_AUTORIZADO >&2; exit 3 ;;
  esac
done

docker compose "${compose[@]}" config --quiet
docker compose "${compose[@]}" config --format json |
    python3 "$root/scripts/viewtv_tmdb_compose_verificar_0013.py"
if [[ "$mode" == apply ]]; then
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  echo API_TMDB_RECARGADA=SI
fi
