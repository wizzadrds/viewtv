#!/usr/bin/env bash
# Cambia solo la API a la revisión HLS 0013, sin tocar worker/archivos.
# No imprimir Docker Compose config completo: contiene credenciales.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
base="$root/deploy/compose.release-0013-disabled-candidate.yaml"
new="$root/deploy/compose.playback-sin-subtitulos-0013.yaml"
mode="${1:-check}"
case "$mode" in check|summary|deploy|rollback) ;; *) exit 2 ;; esac
cd "$root"
test "$(git branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$base"
test -f "$new"
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
original="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' viewtv-api-1)"
test -n "$original"
IFS=',' read -ra paths <<<"$original"
test "${#paths[@]}" -ge 5
compose=(-p viewtv --project-directory "$legacy")
for path in "${paths[@]}"; do
    if [[ "$path" == "$base" || "$path" == "$new" || "$path" == "$root/deploy/compose.publicacion-una-id-0013.yaml" ]]; then
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
compose+=(-f "$base")
if [[ "$mode" != rollback ]]; then
    compose+=(-f "$new")
fi
docker compose "${compose[@]}" config --quiet
if [[ "$mode" == check ]]; then
    echo COMPOSE_HLS_SIN_SUBTITULOS_CONFIG_OK
elif [[ "$mode" == summary ]]; then
    docker compose "${compose[@]}" config --format json |
        python3 "$root/scripts/viewtv_release_0013_summary_safe.py"
else
    if [[ "$mode" == deploy ]]; then
        test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:release-0013-api-candidate
        test -f /home/viewtv/viewtv-backups/playback-sin-subtitulos-pre-20261122-001906.tar.gz
    else
        test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:playback-sin-subtitulos-api-0013
    fi
    docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
    echo "HLS_0013_API_$mode"
fi
