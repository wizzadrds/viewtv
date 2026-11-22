#!/usr/bin/env bash
# Actualización limitada de la API: no tocar torrents, medios ni SQLite.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
old="$root/deploy/compose.gestion-espacio-0015.yaml"
new="$root/deploy/compose.publicador-compatible-api-0016.yaml"
mode="${1:-check}"
case "$mode" in check|deploy) ;; *) exit 2;; esac
test "$(git -C "$root" branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$legacy/.env"
test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:gestion-espacio-api-0015
test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:gestion-espacio-worker-0015
test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:gestion-espacio-0015
test "$(sha256sum /home/viewtv/viewtv-backups/retirada-ntfs-compatibilidad-pre-20261122-230050.tar.gz | cut -d' ' -f1)" = a7956ddf51895883d8448b0a90082ba5c602eebe09e4b3016fcf570fa1890b53
tar -tzf /home/viewtv/viewtv-backups/retirada-ntfs-compatibilidad-pre-20261122-230050.tar.gz >/dev/null

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
test "${#original[@]}" -ge 26
test "${original[${#original[@]}-1]}" = "$old"
compose=(-p viewtv --project-directory "$legacy")
seen=false
for file in "${original[@]}"; do
  case "$file" in
    "$legacy/compose.yaml"|"$legacy/compose.production.yaml"|"$legacy/compose.release-0012.yaml"|/home/viewtv/viewtv-backups/compose-verification-enabled.yaml|"$root"/deploy/*.yaml)
      test -f "$file"
      compose+=(-f "$file")
      if [[ "$file" == "$old" ]]; then seen=true; fi
      ;;
    *) echo COMPOSE_NO_AUTORIZADO >&2; exit 3;;
  esac
done
test "$seen" = true
compose+=(-f "$new")
docker compose "${compose[@]}" config --quiet
docker compose "${compose[@]}" config --format json |
  python3 "$root/scripts/viewtv_publicador_compat_compose_verify_0016.py"
if [[ "$mode" == check ]]; then
  echo COMPAT_PREFLIGHT=PASS
  exit 0
fi
docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:publicador-compatible-api-0016
docker exec viewtv-api-1 python -m worker.organization_windows_cli status |
  python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["estado"]=="listo" and d["modo"]=="general" and d["after_id"]==3'
echo PUBLICADOR_STATUS_COMPATIBLE=PASS
