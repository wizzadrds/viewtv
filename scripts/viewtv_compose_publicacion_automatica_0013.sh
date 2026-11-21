#!/usr/bin/env bash
# Solo API; persistencia de publisher depende de la tarea Windows limitada.
# Modo GENERAL exige opt-in de API y política after_id=3 en Windows.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
candidate="$root/deploy/compose.release-0013-disabled-candidate.yaml"
previous="$root/deploy/compose.playback-sin-subtitulos-0013.yaml"
auto="$root/deploy/compose.publicacion-automatica-0013.yaml"
backup=/home/viewtv/viewtv-backups/publicador-auto-general-pre-20261122-003621.tar.gz
mode="${1:-check}"
case "$mode" in check|summary|deploy|rollback) ;; *) exit 2;; esac
cd "$root"
test "$(git branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$backup"
test -f "$candidate"
test -f "$previous"
test -f "$auto"
test "$(docker inspect --format '{{.State.Running}}' viewtv-worker-1)" = true
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
test "${#original[@]}" -ge 5
compose=(-p viewtv --project-directory "$legacy")
for path in "${original[@]}"; do
  if [[ "$path" == "$candidate" || "$path" == "$previous" || "$path" == "$auto" ||
        "$path" == "$root/deploy/compose.publicacion-una-id-0013.yaml" ]]; then
    continue
  fi
  case "$path" in
    "$legacy/compose.yaml"|"$legacy/compose.production.yaml"|"$legacy/compose.release-0012.yaml"|/home/viewtv/viewtv-backups/compose-verification-enabled.yaml|"$root"/deploy/*.yaml)
      test -f "$path"
      compose+=(-f "$path")
      ;;
    *) echo 'OVERRIDE_NO_AUTORIZADO' >&2; exit 3;;
  esac
done
compose+=(-f "$candidate" -f "$previous")
if [[ "$mode" != rollback ]]; then
  compose+=(-f "$auto")
fi
docker compose "${compose[@]}" config --quiet
if [[ "$mode" == check ]]; then
  echo COMPOSE_PUBLICACION_AUTOMATICA_0013_OK
elif [[ "$mode" == summary ]]; then
  docker compose "${compose[@]}" config --format json |
    python3 "$root/scripts/viewtv_release_0013_summary_safe.py"
else
  if [[ "$mode" == deploy ]]; then
    test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:playback-sin-subtitulos-api-0013
    test -f /home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-004055.db
  else
    test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:auto-publicador-api-0013
  fi
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  echo "API_PUBLICACION_AUTOMATICA_0013_$mode"
fi
