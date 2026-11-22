#!/usr/bin/env bash
# La televisión navega la misma instancia. Solo recrea frontend, nunca worker/API.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
old="$root/deploy/compose.series-episodios-0013.yaml"
new="$root/deploy/compose.tv-auto-update-0013.yaml"
mode="${1:-check}"
case "$mode" in check|previous|deploy|rollback) ;; *) exit 2 ;; esac
test "$(git -C "$root" branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$old"
test -f "$new"
test -f "$legacy/.env"
test -f /home/viewtv/viewtv-backups/television-actualizaciones-pre-20261122-211000.tar.gz
test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:series-episodios-api-0013
test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:release-0013-worker-candidate
test "$(docker inspect --format '{{.Config.Image}}' viewtv-catalogador-1)" = viewtv:catalogo-escalable-api-0013

export VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1
export VIEWTV_ENABLE_AUTO_DOWNLOAD=true
export VIEWTV_ENABLE_DOWNLOAD_START=false
export VIEWTV_ENABLE_DOWNLOAD_VERIFICATION=true
export VIEWTV_ENABLE_ORGANIZATION=false
export VIEWTV_ENABLE_TORRENT_SUBMIT=false
export VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=''
export VIEWTV_WINDOWS_PUBLICATION_DOWNLOAD_ID=''

files="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' viewtv-frontend-1)"
test -n "$files"
IFS=',' read -ra original <<<"$files"
test "${#original[@]}" -ge 25
if [[ "$mode" == rollback ]]; then
  test "${original[${#original[@]}-1]}" = "$new"
else
  test "${original[${#original[@]}-1]}" = "$old"
fi
compose=(-p viewtv --project-directory "$legacy")
saw_old=false
for path in "${original[@]}"; do
  if [[ "$mode" == rollback && "$path" == "$new" ]]; then
    continue
  fi
  case "$path" in
    "$legacy/compose.yaml"|"$legacy/compose.production.yaml"|"$legacy/compose.release-0012.yaml"|/home/viewtv/viewtv-backups/compose-verification-enabled.yaml|"$root"/deploy/*.yaml)
      test -f "$path"
      compose+=(-f "$path")
      if [[ "$path" == "$old" ]]; then saw_old=true; fi
      ;;
    *) echo COMPOSE_NO_AUTORIZADO >&2; exit 3 ;;
  esac
done
test "$saw_old" = true
if [[ "$mode" == check || "$mode" == deploy ]]; then
  compose+=(-f "$new")
  target=new
else
  target=previous
fi
docker compose "${compose[@]}" config --quiet
docker compose "${compose[@]}" config --format json |
  python3 "$root/scripts/viewtv_tv_compose_verify_0013.py" "$target"

if [[ "$mode" == deploy ]]; then
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:series-episodios-0013
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate frontend
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:tv-auto-update-0013
  echo FRONTEND_TV_DESPLEGADO=SI
elif [[ "$mode" == rollback ]]; then
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:tv-auto-update-0013
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate frontend
  echo FRONTEND_TV_REVERTIDO=SI
fi
