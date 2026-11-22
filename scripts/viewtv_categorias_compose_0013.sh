#!/usr/bin/env bash
# Despliegue controlado, solo API/frontend; no recrea worker/Jellyfin.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
new="$root/deploy/compose.categorias-netflix-0013.yaml"
hls="$root/deploy/compose.hls-video-ref-0012.yaml"
mode="${1:-check}"
case "$mode" in check|previous|deploy|rollback) ;; *) exit 2;; esac
test "$(git -C "$root" branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$new"
test -f "$hls"
test "$(docker inspect --format '{{.State.Running}}' viewtv-worker-1)" = true
test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:release-0013-worker-candidate
test "$(docker exec viewtv-worker-1 printenv VIEWTV_WINDOWS_PUBLICATION_MODE)" = disabled
test "$(docker exec viewtv-worker-1 printenv VIEWTV_ENABLE_ORGANIZATION)" = false
test "$(docker exec viewtv-worker-1 printenv VIEWTV_ENABLE_DOWNLOAD_START)" = false

# Los valores del último release son obligatorios. No leer/mostrar .env.
export VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1
export VIEWTV_ENABLE_AUTO_DOWNLOAD=true
export VIEWTV_ENABLE_DOWNLOAD_START=false
export VIEWTV_ENABLE_DOWNLOAD_VERIFICATION=true
export VIEWTV_ENABLE_ORGANIZATION=false
export VIEWTV_ENABLE_TORRENT_SUBMIT=false
export VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=''
export VIEWTV_WINDOWS_PUBLICATION_DOWNLOAD_ID=''

original="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' viewtv-api-1)"
test -n "$original"
IFS=',' read -ra all <<<"$original"
test "${#all[@]}" -ge 25
last="${all[${#all[@]}-1]}"
if [[ "$mode" == deploy || "$mode" == check || "$mode" == previous ]]; then
  test "$last" = "$root/deploy/compose.publicacion-automatica-0013.yaml"
else
  test "$last" = "$new"
fi
compose=(-p viewtv --project-directory "$legacy")
for item in "${all[@]}"; do
  if [[ "$item" == "$new" ]]; then continue; fi
  case "$item" in
    "$legacy/compose.yaml"|"$legacy/compose.production.yaml"|"$legacy/compose.release-0012.yaml"|/home/viewtv/viewtv-backups/compose-verification-enabled.yaml|"$root"/deploy/*.yaml)
      test -f "$item"
      compose+=(-f "$item")
      ;;
    *) echo 'COMPOSE_NO_AUTORIZADO' >&2; exit 3;;
  esac
done
# El frontend antiguo tiene un override adicional solo para su imagen.
compose+=(-f "$hls")
if [[ "$mode" == check || "$mode" == deploy ]]; then
  compose+=(-f "$new")
  verified=new
else
  verified=previous
fi
docker compose "${compose[@]}" config --quiet
docker compose "${compose[@]}" config --format json |
  python3 "$root/scripts/viewtv_categorias_compose_verify_0013.py" "$verified"

if [[ "$mode" == deploy ]]; then
  test -f /home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-014729.db
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:auto-publicador-api-0013
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:hls-video-ref-0012
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:categorias-0013-api-conservative
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate frontend
  echo DESPLIEGUE_CATEGORIAS_API_FRONTEND_OK
elif [[ "$mode" == rollback ]]; then
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:categorias-0013-api-conservative
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:categorias-0013-candidate
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate frontend
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  echo ROLLBACK_CATEGORIAS_API_FRONTEND_OK
fi
