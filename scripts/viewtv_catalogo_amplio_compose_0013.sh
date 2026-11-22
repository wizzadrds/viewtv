#!/usr/bin/env bash
# Despliegue/reversión con límites: solo API/frontend y nuevo catalogador.
# Tarea periódica Windows debe pausarse antes de deploy/rollback.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
new="$root/deploy/compose.categorias-netflix-0013.yaml"
previous="$root/deploy/compose.categorias-netflix-pre-catalogo-0013.yaml"
mode="${1:-check}"
case "$mode" in check|previous|deploy|rollback) ;; *) exit 2 ;; esac
test "$(git -C "$root" branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$new"
test -f "$previous"
test -f "$legacy/.env"
test -f /home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-021820.db
test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:release-0013-worker-candidate
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
test "${original[${#original[@]}-1]}" = "$new"
compose=(-p viewtv --project-directory "$legacy")
for path in "${original[@]}"; do
  if [[ "$path" == "$new" && ( "$mode" == previous || "$mode" == rollback ) ]]; then
    continue
  fi
  case "$path" in
    "$legacy/compose.yaml"|"$legacy/compose.production.yaml"|"$legacy/compose.release-0012.yaml"|/home/viewtv/viewtv-backups/compose-verification-enabled.yaml|"$root"/deploy/*.yaml)
      test -f "$path"
      compose+=(-f "$path")
      ;;
    *) echo COMPOSE_NO_AUTORIZADO >&2; exit 3 ;;
  esac
done
if [[ "$mode" == previous || "$mode" == rollback ]]; then
  compose+=(-f "$previous")
  target=previous
else
  target=new
fi

docker compose "${compose[@]}" config --quiet
docker compose "${compose[@]}" config --format json |
  python3 "$root/scripts/viewtv_catalogo_amplio_compose_verify_0013.py" "$target"

if [[ "$mode" == deploy ]]; then
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:categorias-0013-api-conservative
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:categorias-0013-candidate
  # El volumen es nuevo, independiente de viewtv_data y los archivos NTFS.
  volume=viewtv_viewtv_catalogo_data
  docker volume inspect "$volume" >/dev/null 2>&1 && {
    echo VOLUMEN_YA_EXISTE_REVISAR_MANUALMENTE >&2; exit 4;
  }
  # Compose crea el volumen con sus etiquetas, SIN arrancar el proceso.
  docker compose "${compose[@]}" create --no-recreate catalogador
  docker volume inspect "$volume" >/dev/null
  docker run --rm --pull never --network none --user 0 \
    --mount "type=volume,source=$volume,target=/catalogo" \
    --entrypoint chown viewtv:catalogo-amplio-api-0013 1000:1000 /catalogo
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:catalogo-amplio-api-0013
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate frontend
  docker compose "${compose[@]}" up -d --no-deps --no-build catalogador
  echo CATALOGO_DESPLEGADO=SI
elif [[ "$mode" == rollback ]]; then
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:catalogo-amplio-api-0013
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:catalogo-amplio-0013
  docker stop viewtv-catalogador-1 >/dev/null
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate frontend
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  echo CATALOGO_ROLLBACK=SI
fi
