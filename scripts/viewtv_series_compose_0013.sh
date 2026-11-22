#!/usr/bin/env bash
# Despliegue conservador: SOLO API y frontend, sin reinstalar Jellyfin/worker.
# La tarea periódica de Windows debe pausarse en deploy/rollback.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
previous="$root/deploy/compose.catalogo-escalable-0013.yaml"
new="$root/deploy/compose.series-episodios-0013.yaml"
mode="${1:-check}"
case "$mode" in check|previous|deploy|rollback|redeploy-api) ;; *) exit 2 ;; esac

test "$(git -C "$root" branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$new"
test -f "$previous"
test -f "$legacy/.env"
test -f /home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-203946.db
test -f /home/viewtv/viewtv-backups/metadatos-series-predeploy-20261122-203946.db
test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:release-0013-worker-candidate
test "$(docker inspect --format '{{.Config.Image}}' viewtv-catalogador-1)" = viewtv:catalogo-escalable-api-0013
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
last="${original[${#original[@]}-1]}"
if [[ "$mode" == rollback || "$mode" == redeploy-api ]]; then
  test "$last" = "$new"
else
  test "$last" = "$previous"
fi

compose=(-p viewtv --project-directory "$legacy")
saw_previous=false
for path in "${original[@]}"; do
  if [[ "$mode" == rollback && "$path" == "$new" ]]; then
    continue
  fi
  case "$path" in
    "$legacy/compose.yaml"|"$legacy/compose.production.yaml"|"$legacy/compose.release-0012.yaml"|/home/viewtv/viewtv-backups/compose-verification-enabled.yaml|"$root"/deploy/*.yaml)
      test -f "$path"
      compose+=(-f "$path")
      if [[ "$path" == "$previous" ]]; then saw_previous=true; fi
      ;;
    *) echo COMPOSE_NO_AUTORIZADO >&2; exit 3 ;;
  esac
done
test "$saw_previous" = true
if [[ "$mode" == check || "$mode" == deploy ]]; then
  compose+=(-f "$new")
  target=new
elif [[ "$mode" == redeploy-api ]]; then
  target=new
else
  target=previous
fi

docker compose "${compose[@]}" config --quiet
docker compose "${compose[@]}" config --format json |
  python3 "$root/scripts/viewtv_series_compose_verify_0013.py" "$target"

if [[ "$mode" == deploy ]]; then
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:catalogo-escalable-api-0013
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:catalogo-amplio-0013
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:series-episodios-api-0013
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate frontend
  echo SERIES_EPISODIOS_DESPLEGADOS=SI
elif [[ "$mode" == redeploy-api ]]; then
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:series-episodios-api-0013
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:series-episodios-0013
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  echo SERIES_API_RECREADA=SI
elif [[ "$mode" == rollback ]]; then
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:series-episodios-api-0013
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:series-episodios-0013
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate frontend
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  echo SERIES_EPISODIOS_REVERTIDOS=SI
fi
