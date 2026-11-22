#!/usr/bin/env bash
# Solo API y worker; despliegue seguro de cohésion con esquema 0014.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
old="$root/deploy/compose.busqueda-samsung-0013.yaml"
new="$root/deploy/compose.cohesion-caratula-0014.yaml"
rollback="$root/deploy/compose.cohesion-rollback-0014.yaml"
mode="${1:-check}"
case "$mode" in check|deploy|check-rollback|rollback) ;; *) echo MODO_INVALIDO >&2; exit 2;; esac

test "$(git -C "$root" branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$legacy/.env"
test -f "$old" && test -f "$new" && test -f "$rollback"
test -f /home/viewtv/viewtv-backups/cohesion-caratula-pre-20261122-220940.tar.gz
test -f /home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-222154.db
test "$(sha256sum /home/viewtv/viewtv-backups/cohesion-caratula-pre-20261122-220940.tar.gz | cut -d' ' -f1)" = 8466086387539a4981e731298ef276d1f2005402b3079cc87ea70b746553ea59
test "$(docker run --rm --network none -v /home/viewtv/viewtv-backups:/backup:ro --entrypoint sha256sum viewtv:tests-devtools-0013 /backup/api-resultados-predeploy-20261122-222154.db | cut -d' ' -f1)" = d2d8c409a94a269cdb8677e79534c4387fb954984565794fd1596ea1ad087117
test "$(docker inspect --format '{{.Config.Image}}' viewtv-frontend-1)" = viewtv-frontend:samsung-busqueda-0013
test "$(docker inspect --format '{{.Config.Image}}' viewtv-catalogador-1)" = viewtv:catalogo-escalable-api-0013

export VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1
export VIEWTV_ENABLE_AUTO_DOWNLOAD=true
export VIEWTV_ENABLE_DOWNLOAD_START=false
export VIEWTV_ENABLE_DOWNLOAD_VERIFICATION=true
export VIEWTV_ENABLE_ORGANIZATION=false
export VIEWTV_ENABLE_TORRENT_SUBMIT=false
export VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=''
export VIEWTV_WINDOWS_PUBLICATION_DOWNLOAD_ID=''

reference=viewtv-frontend-1
if [[ "$mode" == check-rollback || "$mode" == rollback ]]; then
  # El frontend no se ha recreado, así que sigue etiquetado con
  # el stack anterior. La API sí incorpora el overlay 0014 nuevo.
  reference=viewtv-api-1
fi
files="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$reference")"
test -n "$files"
IFS=',' read -ra original <<<"$files"
test "${#original[@]}" -ge 25
last="${original[${#original[@]}-1]}"
# No usar un stack alternativo, ni sobrescribir los overlays que estaban vivos.
if [[ "$mode" == check || "$mode" == deploy ]]; then
  test "$last" = "$old"
else
  test "$last" = "$new"
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

if [[ "$mode" == check || "$mode" == deploy ]]; then
  compose+=(-f "$new")
  expected=new
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:busqueda-tmdb-api-0013
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:busqueda-tmdb-worker-0013
else
  compose+=(-f "$rollback")
  expected=rollback
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:cohesion-caratula-api-0014
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:cohesion-caratula-worker-0014
fi

docker compose "${compose[@]}" config --quiet
docker compose "${compose[@]}" config --format json |
  python3 "$root/scripts/viewtv_cohesion_compose_verify_0014.py" "$expected"

if [[ "$mode" == check || "$mode" == check-rollback ]]; then
  echo COHESION_PREFLIGHT_COMPOSE=PASS
  exit 0
fi

if [[ "$mode" == deploy ]]; then
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:cohesion-caratula-api-0014
  # La API migra a 0014 antes de sustituir el worker.
  docker exec viewtv-api-1 sh -c 'cd /opt/viewtv/backend && alembic current' |
    grep -q 0014_identidad_tmdb_solicitud
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate worker
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:cohesion-caratula-worker-0014
  echo COHESION_API_WORKER_0014=DESPLEGADOS
else
  # Retroceso de ALGORITMO: se conserva columna TMDB y toda solicitud
  # nueva, sin downgrades destructivos de la base real.
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate worker
  docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-api-1)" = viewtv:cohesion-rollback-api-0014
  test "$(docker inspect --format '{{.Config.Image}}' viewtv-worker-1)" = viewtv:cohesion-rollback-worker-0014
  echo COHESION_ALGORITMO_REVERTIDO_SIN_BORRAR_IDENTIDADES=SI
fi
