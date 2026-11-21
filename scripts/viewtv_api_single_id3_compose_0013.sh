#!/usr/bin/env bash
# Prueba exclusivamente ID #3, sin cambiar worker ni publicar desde Docker.
# Reconstruye orden Compose real; NUNCA imprime config (contiene secretos).
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
candidate="$root/deploy/compose.release-0013-disabled-candidate.yaml"
single="$root/deploy/compose.publicacion-una-id-0013.yaml"
backup=/home/viewtv/viewtv-backups/publicacion-id3-pre-20261121-235826.tar.gz
mode="${1:-check}"
case "$mode" in check|summary|enable|disable) ;; *) exit 2;; esac
cd "$root"
test "$(git branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$backup"
test -f "$candidate"
test -f "$single"
export VIEWTV_WINDOWS_PUBLICATION_DOWNLOAD_ID=3
export VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1
export VIEWTV_ENABLE_AUTO_DOWNLOAD=true
export VIEWTV_ENABLE_DOWNLOAD_START=false
export VIEWTV_ENABLE_DOWNLOAD_VERIFICATION=true
export VIEWTV_ENABLE_ORGANIZATION=false
export VIEWTV_ENABLE_TORRENT_SUBMIT=false
export VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=''
# La propia API debe estar todavía en el esquema compartido 0013.
test "$(docker inspect --format '{{.State.Health.Status}}' viewtv-api-1)" = healthy
test "$(docker inspect --format '{{.State.Running}}' viewtv-worker-1)" = true
test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:release-0013-api-candidate
test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:release-0013-worker-candidate
label="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' viewtv-api-1)"
test -n "$label"
IFS=',' read -ra files <<<"$label"
test "${#files[@]}" -ge 5
compose=(-p viewtv --project-directory "$legacy")
for file in "${files[@]}"; do
  if [[ "$file" == "$candidate" || "$file" == "$single" ]]; then continue; fi
  case "$file" in
    "$legacy/compose.yaml"|"$legacy/compose.production.yaml"|"$legacy/compose.release-0012.yaml"|/home/viewtv/viewtv-backups/compose-verification-enabled.yaml|"$root"/deploy/*.yaml)
      test -f "$file"
      compose+=(-f "$file")
      ;;
    *) echo 'OVERRIDE_NO_AUTORIZADO' >&2; exit 3;;
  esac
done
compose+=(-f "$candidate")
if [[ "$mode" == check || "$mode" == summary || "$mode" == enable ]]; then
  compose+=(-f "$single")
fi
docker compose "${compose[@]}" config --quiet
if [[ "$mode" == summary ]]; then
  docker compose "${compose[@]}" config --format json |
    python3 "$root/scripts/viewtv_release_0013_summary_safe.py"
elif [[ "$mode" == check ]]; then
  echo COMPOSE_ID3_CONFIG_OK
else
  # Dos overrides expresos: API en SINGLE id3 o vuelta a DISABLED.
  # Nunca recrear el worker y nunca activar GENERAL.
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  echo "API_0013_PUBLICACION_ID3_MODO_$mode"
fi
