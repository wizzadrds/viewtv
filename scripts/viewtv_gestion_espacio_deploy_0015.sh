#!/usr/bin/env bash
# Solo API, worker y frontend; conserva todas las otras funciones y medios.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
old="$root/deploy/compose.cohesion-caratula-0014.yaml"
new="$root/deploy/compose.gestion-espacio-0015.yaml"
rollback="$root/deploy/compose.gestion-espacio-rollback-0015.yaml"
mode="${1:-check}"
case "$mode" in check|deploy|check-rollback|rollback) ;; *) exit 2 ;; esac

test "$(git -C "$root" branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$legacy/.env"
test -f "$old" && test -f "$new" && test -f "$rollback"
source_tar=/home/viewtv/viewtv-backups/gestion-espacio-cache-pre-20261122-224320.tar.gz
source_db=/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-225105.db
test -f "$source_tar" && test -f "$source_db"
tar -tzf "$source_tar" >/dev/null
test "$(sha256sum "$source_tar" | cut -d' ' -f1)" = cd32ed2cf5ffa9041d06e2d4564cec44ce059506e8d9c2760d50b55fd78b8ca8
test "$(docker run --rm --network none -v /home/viewtv/viewtv-backups:/backup:ro --entrypoint sha256sum viewtv:tests-devtools-0013 /backup/api-resultados-predeploy-20261122-225105.db | cut -d' ' -f1)" = ac0352f867deae7d3336ef6c92cbe33049d1d7de75de56b25da5a80b13d32e30
test "$(docker inspect --format '{{.Config.Image}}' viewtv-catalogador-1)" = viewtv:catalogo-escalable-api-0013

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
if [[ "$mode" == check || "$mode" == deploy ]]; then
  test "$last" = "$old"
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:cohesion-caratula-api-0014
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:cohesion-caratula-worker-0014
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:samsung-busqueda-0013
  target="$new"
  expected=new
else
  test "$last" = "$new"
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:gestion-espacio-api-0015
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:gestion-espacio-worker-0015
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:gestion-espacio-0015
  target="$rollback"
  expected=rollback
fi
compose=(-p viewtv --project-directory "$legacy")
seen_old=false
for path in "${original[@]}"; do
  case "$path" in
    "$legacy/compose.yaml"|"$legacy/compose.production.yaml"|"$legacy/compose.release-0012.yaml"|/home/viewtv/viewtv-backups/compose-verification-enabled.yaml|"$root"/deploy/*.yaml)
      test -f "$path"
      compose+=(-f "$path")
      if [[ "$path" == "$old" ]]; then seen_old=true; fi
      ;;
    *) echo STACK_COMPOSE_NO_AUTORIZADO >&2; exit 3;;
  esac
done
test "$seen_old" = true
compose+=(-f "$target")
docker compose "${compose[@]}" config --quiet
docker compose "${compose[@]}" config --format json |
  python3 "$root/scripts/viewtv_gestion_espacio_compose_verify_0015.py" "$expected"

if [[ "$mode" == check || "$mode" == check-rollback ]]; then
  echo GESTION_ESPACIO_PREFLIGHT=PASS
  exit 0
fi

if [[ "$mode" == deploy ]]; then
  # API aplica 0015 antes que worker y frontend; nunca tocar volúmenes.
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:gestion-espacio-api-0015
  docker exec viewtv-api-1 sh -c 'cd /opt/viewtv/backend && alembic current' |
    grep -q 0015_gestion_espacio_vistas
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate worker
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:gestion-espacio-worker-0015
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate frontend
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:gestion-espacio-0015
  echo GESTION_ESPACIO_0015_DESPLEGADO=SI
else
  # Reversión de lógica sin bajar el esquema ni perder marcas de visto.
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate frontend
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate worker
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:gestion-espacio-rollback-api-0015
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:gestion-espacio-rollback-worker-0015
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:samsung-busqueda-0013
  echo GESTION_ESPACIO_REVERTIDA_SIN_PERDER_DATOS=SI
fi
