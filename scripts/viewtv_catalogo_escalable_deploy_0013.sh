#!/usr/bin/env bash
# Reconfigura solo API y catalogador. No toca frontend, worker, Jellyfin ni media.
# Debe pausarse la tarea de Windows antes de ejecutar deploy/rollback.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
old="$root/deploy/compose.categorias-netflix-0013.yaml"
new="$root/deploy/compose.catalogo-escalable-0013.yaml"
mode="${1:-check}"
case "$mode" in check|deploy|rollback) ;; *) exit 2 ;; esac
test "$(git -C "$root" branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$old"
test -f "$new"
test -f "$legacy/.env"
test -f /home/viewtv/viewtv-backups/metadatos-pre-ampliacion-20261122-200700.db
test -f /home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-201500.db
test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:release-0013-worker-candidate
test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:catalogo-amplio-0013
test "$(docker exec viewtv-worker-1 printenv VIEWTV_WINDOWS_PUBLICATION_MODE)" = disabled
test "$(docker exec viewtv-worker-1 printenv VIEWTV_ENABLE_ORGANIZATION)" = false
test "$(docker exec viewtv-worker-1 printenv VIEWTV_ENABLE_DOWNLOAD_START)" = false

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
expected_last="$old"
if [[ "$mode" == rollback ]]; then expected_last="$new"; fi
test "${original[${#original[@]}-1]}" = "$expected_last"
compose=(-p viewtv --project-directory "$legacy")
seen_old=false
for path in "${original[@]}"; do
  if [[ "$path" == "$new" && "$mode" == rollback ]]; then
    continue
  fi
  case "$path" in
    "$legacy/compose.yaml"|"$legacy/compose.production.yaml"|"$legacy/compose.release-0012.yaml"|/home/viewtv/viewtv-backups/compose-verification-enabled.yaml|"$root"/deploy/*.yaml)
      test -f "$path"
      compose+=(-f "$path")
      if [[ "$path" == "$old" ]]; then seen_old=true; fi
      ;;
    *) echo COMPOSE_NO_AUTORIZADO >&2; exit 3 ;;
  esac
done
test "$seen_old" = true
if [[ "$mode" != rollback ]]; then
  compose+=(-f "$new")
  target=new
else
  target=previous
fi
docker compose "${compose[@]}" config --quiet
docker compose "${compose[@]}" config --format json |
  python3 "$root/scripts/viewtv_catalogo_escalable_verify_0013.py" "$target"

if [[ "$mode" == deploy ]]; then
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:catalogo-amplio-api-0013
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-catalogador-1)" = viewtv:catalogo-amplio-api-0013
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:catalogo-escalable-api-0013
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate catalogador
  echo CATALOGO_ESCALABLE_DESPLEGADO=SI
elif [[ "$mode" == rollback ]]; then
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:catalogo-escalable-api-0013
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-catalogador-1)" = viewtv:catalogo-escalable-api-0013
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate catalogador
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  echo CATALOGO_ESCALABLE_ROLLBACK=SI
fi
