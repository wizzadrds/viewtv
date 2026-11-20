# VIEWTV — recuperación efectiva de la API 0012

Fecha: 20-11-2026. Prioridad: devolver funcionalidad a la aplicación
antes de seguir ampliando el organizador 0013.

## Problema y causa comprobada

El contenedor `viewtv-api-1` estaba reiniciándose con código 255 y
`Can't locate revision identified by '0012_inicio_torrent'`.

No era un fallo general de SQLite ni del worker. Se verificó:

- API antigua: imagen `viewtv:local` (id `7dc447a6...`),
  empaquetaba migraciones solo de 0001 a 0008.
- Worker activo: `viewtv:predeploy-0012-release`
  (id `cc73b747...`), empaquetaba hasta 0012.
- El esquema de base de datos estaba en `0012_inicio_torrent`.
- La configuración Compose existente **ya señalaba para api y worker**
  `viewtv:predeploy-0012-release`; el contenedor API
  conservaba una imagen vieja.

## Respaldo verificado ANTES de actuar

Se creó directorio restringido, modo 0700:
`/home/viewtv/viewtv-backups/api-0012-restauracion-20261120-181400/`.

Dentro se preservó:
`viewtv-api-0012-before-recreate.db` (163840 bytes, modo 0600).

SHA-256:
`331d98722f7869631ee8d90cc16689b49fa9679775f10134edaf35d705d45a83`

El script nuevo
`scripts/viewtv_api_0012_sqlite_backup_readonly.py`
utilizó la función `sqlite3.backup()` para una instantánea
consistente desde un contenedor **efímero sin red**,
con el volumen `viewtv_viewtv_data` montado en
**solo lectura**, sin detener el worker.
Se verificaron `PRAGMA integrity_check = ok`,
revisión Alembic = 0012 y cero errores de
`foreign_key_check`. SHA-256 confirmado posteriormente desde Ubuntu.

El respaldo **no fue una copia directa potencialmente inconsistente
de un archivo abierto**; se utilizó la API online de SQLite.
No se compartió ni imprimió información de perfiles,
credenciales o datos multimedia.

## Reparación aplicada

Se ejecutó exactamente `docker compose up -d` con
`--no-deps --no-build --force-recreate api`, usando:
1. `/home/viewtv/projects/viewtv/compose.yaml`
2. `/home/viewtv/projects/viewtv/compose.production.yaml`
3. `/home/viewtv/viewtv-backups/compose-verification-enabled.yaml`
4. `/home/viewtv/projects/viewtv/compose.release-0012.yaml`

Con `--project-directory /home/viewtv/projects/viewtv`.

**Solo se recreó el servicio API**. No se modificaron esos
cuatro Compose ni la fuente del árbol principal, ni el worker,
Jellyfin, frontend, torrents o archivos multimedia.
No se forzó ninguna migración ni se alteró su revisión.

## Validaciones posteriores

- `viewtv-api-1` quedó en imagen `viewtv:predeploy-0012-release`,
  estado `Up ... (healthy)` y sin nuevos reinicios durante la prueba.
- Alembic API: `0012_inicio_torrent (head)`.
- `GET http://127.0.0.1:8000/health`: **HTTP 200**,
  `{"estado":"ok","servicio":"viewtv-api"}`.
- `GET http://127.0.0.1:3000/api/viewtv/health`: **HTTP 200**
  y respuesta idéntica, atravesando el proxy Next.js.
- Frontend en `127.0.0.1:3000/`: **HTTP 200**.
- `GET /api/viewtv/auth/profiles` a través del frontend:
  **HTTP 200**, estructura JSON validada sin revelar nombres.
- Rutas sin sesión (identidad, solicitudes, descargas y
  catálogo/estado Jellyfin): **HTTP 401**, protección correcta.
- Jellyfin `127.0.0.1:8097/health`: **HTTP 200**.
- Worker sigue ejecutándose con la misma imagen 0012; FlareSolverr
  y Jellyfin siguen saludables.
- Script nuevo `scripts/viewtv_release_smoke_0012_readonly.py`:
  **10 comprobaciones PASS**, ejecución GET sin credenciales,
  sin accesos de escritura ni inicio de descargas.
- Ruff: correcto en los dos scripts nuevos.

## Marcha atrás y límites

La imagen antigua `viewtv:local` NO es una reversión funcional
sobre la SQLite 0012: reintroduciría el error. No volver a ella
para "deshacer" la reparación.

Para una incidencia posterior, primero preservar el nuevo estado,
revisar logs y estado sin cambiar el volumen; nunca restaurar
la copia mientras el worker o la API puedan escribir.
Cualquier restauración de SQLite requeriría detener
escrituras, conservar estado actual y coordinar una vuelta atrás
entre API/worker/esquema, con autorización aparte.
No se ha ejecutado ninguna restauración porque la API está sana.

**No se ha verificado todavía un login completo con PIN ni
descarga y reproducción real desde la interfaz**. No se ha leído
ningún PIN; el flag `VIEWTV_ENABLE_DOWNLOAD_START=false`
permanece desactivado. El organizador 0013 sigue sin despliegue.

## Decisión

**Incidencia API 0012 corregida y verificada.** Retomar ahora las
pruebas de funcionalidades principales y el plan de salida rápida.
No confundir disponibilidad de servicios con verificación completa
del circuito multimedia.
