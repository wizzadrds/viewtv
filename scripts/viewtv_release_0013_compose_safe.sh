#!/usr/bin/env bash
# Compose release 0013: archivos de la configuración REAL en orden,
# pero fuente de código y cambios solo en worktree autorizado.
# No imprimir jamás "docker compose config" sin filtro de secretos.
set -euo pipefail
root=/home/viewtv/projects/viewtv-broker-0013-20261119
legacy=/home/viewtv/projects/viewtv
candidate="$root/deploy/compose.release-0013-disabled-candidate.yaml"
cd "$root"
# Solo flags no secretos observados en el worker activo 0012.
# Resolver placeholders de overrides antiguos sin tocar ni imprimir .env.
export VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1
export VIEWTV_ENABLE_AUTO_DOWNLOAD=true
export VIEWTV_ENABLE_DOWNLOAD_START=false
export VIEWTV_ENABLE_DOWNLOAD_VERIFICATION=true
export VIEWTV_ENABLE_ORGANIZATION=false
export VIEWTV_ENABLE_TORRENT_SUBMIT=false
export VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=''
test "$(git branch --show-current)" = viewtv-seguimiento-descargas-0012
test -f "$candidate"
test -d "$legacy"
source_labels="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' viewtv-api-1)"
test -n "$source_labels"
IFS=',' read -ra original <<<"$source_labels"
test "${#original[@]}" -ge 5
compose=(-p viewtv --project-directory "$legacy")
for path in "${original[@]}"; do
    # Tras el primer reinicio Docker ya incluye 0013 en sus labels.
    # No heredarla al reconstruir la configuración anterior.
    if [[ "$path" == "$candidate" ]]; then continue; fi
    case "$path" in
      "$legacy/compose.yaml"|"$legacy/compose.production.yaml"|"$legacy/compose.release-0012.yaml"|/home/viewtv/viewtv-backups/compose-verification-enabled.yaml|"$root"/deploy/*.yaml)
        test -f "$path" || { echo "Falta un override autorizado" >&2; exit 3; }
        compose+=(-f "$path")
        ;;
      *) echo "Override fuera de las rutas conocidas" >&2; exit 3 ;;
    esac
done
rollback=("${compose[@]}")
compose+=(-f "$candidate")
# Preflight del esquema de producción SIN tocar SQLite; los cambios a
# 0013 solamente los hará la API nueva al arrancar con worker parado.
schema_0013_ok() {
    docker run --rm --pull never --network none --user 1000:1000 \
      --mount type=volume,source=viewtv_viewtv_data,target=/data,readonly \
      --mount type=bind,source="$root/scripts/viewtv_release_0013_sqlite_verify_readonly.py",target=/tmp/verify.py,readonly \
      --entrypoint python viewtv:release-0013-api-candidate \
      /tmp/verify.py /data/viewtv.db 0013_cola_organizacion >/dev/null
}
case "${1:-check}" in
    check)
        docker compose "${compose[@]}" config --quiet
        echo COMPOSE_RELEASE_0013_CONFIG_OK
        ;;
    summary)
        docker compose "${compose[@]}" config --format json |
        python3 "$root/scripts/viewtv_release_0013_summary_safe.py"
        ;;
    rollback-summary)
        docker compose "${rollback[@]}" config --format json |
        python3 "$root/scripts/viewtv_release_0013_summary_safe.py"
        ;;
    up-api)
        # El único servicio recreado aquí será API.
        test "$(docker inspect --format '{{.State.Running}}' viewtv-api-1)" = false
        test "$(docker inspect --format '{{.State.Running}}' viewtv-worker-1)" = false
        test -f /home/viewtv/viewtv-backups/api-resultados-predeploy-20261121-232158.db
        docker compose "${compose[@]}" config --quiet
        docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate api
        echo COMPOSE_0013_API_RECREADA
        ;;
    up-worker)
        # La API 0013 ya debe estar saludable y la SQLite en 0013.
        test "$(docker inspect --format '{{.State.Health.Status}}' viewtv-api-1)" = healthy
        test "$(docker inspect --format '{{.State.Running}}' viewtv-worker-1)" = false
        schema_0013_ok
        docker compose "${compose[@]}" config --quiet
        docker compose "${compose[@]}" up -d --no-deps --no-build --force-recreate worker
        echo COMPOSE_0013_WORKER_RECREADO
        ;;
    *)
        echo "Solo se admite check|summary|rollback-summary|up-api|up-worker" >&2
        exit 2
        ;;
esac
