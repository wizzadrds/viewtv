# VIEWTV — Relevo técnico y continuidad

**Fecha:** 18 de noviembre de 2026 (Europe/Madrid)  
**Repositorio:** `wizzadrds/viewtv`  
**Rama de trabajo local:** `inventario-trabajo-local`  
**Último commit local confirmado:** `a9ffe88` (`Registrar estados persistentes de verificacion de descargas`)  
**Estado Git al cierre:** 23 commits locales por delante del remoto; no se ha hecho push de esos 23 commits.  
**Importante:** Esta documentación se publica en una **rama separada** para no crear divergencias en la rama de desarrollo.

## Resumen ejecutivo

VIEWTV es una PWA multimedia con Next.js, FastAPI, SQLite y un worker independiente. Integra Jackett y qBittorrent nativos en Windows; FlareSolverr y Jellyfin en Docker. La búsqueda, selección, cola durable, envío detenido a qBittorrent, supervisión del progreso y Direct Play de Jellyfin han avanzado considerablemente.

**Última suite completa que pasó:** 209 pruebas, 2 advertencias de deprecación no bloqueantes. Ruff correcto para `app tests ../worker` y la migración nueva `0009`; Ruff sobre *todas* las migraciones históricas reporta 8 incidencias preexistentes de estilo en 0001, 0002, 0003, 0004 y 0006. No modificar migraciones históricas solo para corregir formato.

**Estimación orientativa:** ~81 %; 17–28 horas pendientes. Son cifras aproximadas, no compromisos ni métricas objetivas. La funcionalidad pendiente más relevante es conectar la descarga completada con la verificación persistente, la incorporación a Jellyfin y la disponibilidad real en la PWA.

## 1. Estado exacto al cerrar — problema inmediato

El usuario añadió nuevas pruebas transaccionales a `backend/tests/test_queue.py` para `record_download_verification()`. Al ejecutarlas, pytest **no llegó a iniciar las pruebas**, porque falta una importación:

```text
ERROR collecting tests/test_queue.py
NameError: name 'pytest' is not defined
tests/test_queue.py:1042: @pytest.mark.parametrize(...)
Ruff: F821 Undefined name pytest (líneas 1042 y 1055)
```

Archivos modificados localmente, **SIN COMMIT**:

```text
 M backend/app/queue.py
 M backend/tests/test_queue.py
```

La nueva función `record_download_verification` se añadió a `backend/app/queue.py`: valida identificador, hash, bool y error; exige descarga completada, progreso 1 y hash coincidente; utiliza `_begin_write(session)` (`BEGIN IMMEDIATE` en SQLite), impide volver de verificada a fallida, registra `verificada_en`, `error_verificacion` y actualiza `actualizado_en`. **Sus nuevas pruebas aún no han corrido**, y por tanto no se puede afirmar que la implementación esté validada.

**Primer paso al reanudar:**

1. Añadir `import pytest` a `backend/tests/test_queue.py`, respetando orden de importaciones.
2. Ejecutar desde `backend`: ` .venv/bin/python -m pytest tests/test_queue.py -k record_download_verification -q`.
3. Corregir cualquier fallo real que aparezca (distinguir fallo de importación de fallo de lógica).
4. Ejecutar ` .venv/bin/python -m pytest tests -q` y ` .venv/bin/python -m ruff check app tests ../worker migrations/versions/0009_verificacion_descarga.py`.
5. Revisar `git diff --check`, staged exacto, y guardar solo los archivos validados en un commit local.

**No ejecutar aún migraciones de producción ni reiniciar API/worker con el modelo de 0009.**

## 2. Infraestructura y rutas confirmadas

- Host: Windows 11, WSL Ubuntu 24.04. Proyecto `~/projects/viewtv`.
- Docker Compose del proyecto contiene `api`, `worker`, `flaresolverr`; Jellyfin es un contenedor aparte llamado **`viewtv-jellyfin`** (no `viewtv-jellyfin-1`).
- API: `viewtv-api-1`, puerto local 8000; worker: `viewtv-worker-1`; FlareSolverr local 8191.
- Jackett y qBittorrent corren nativos en Windows. qBittorrent 5.3.0, API 2.16.2.
- Carpeta de qBittorrent: `C:\VIEWTV\media\descargas_temporales`. `temp_path_enabled=False`, `auto_tmm_enabled=False`.
- Jellyfin monta `C:\VIEWTV\media\Peliculas` como `/media/Peliculas`, `C:\VIEWTV\media\Series` como `/media/Series`; cache y config en `C:\VIEWTV\jellyfin-docker\`.
- El worker tiene `/data` (volumen rw), `/cache` (bind rw) y **`/media` (bind read-only)** desde `/mnt/c/VIEWTV/media:/media:ro`. Se confirmó desde el contenedor que ve `descargas_temporales`, `Peliculas` y `Series`; `docker inspect` mostró `/media ro`.
- Jellyfin se observó en estado `running/healthy`. Se comprobó previamente reproducción Direct Play y respuestas Range HTTP 206.

## 3. Descargas y seguridad comprobadas

- El envío real a qBittorrent desde VIEWTV usa `stopped=true` para añadir torrents detenidos: no confiar solo en preferencias globales. Se validó frente a qBittorrent real.
- Torrent ficticio de prueba sin transferencia: hash `83650dcea3d6ff86826211bb1aec386be689ac32`, etiqueta `viewtv-prueba-stopped-20261118`; qBittorrent devolvió `stoppedDL`, `progress=0`, `downloaded=0`, `total_size=-1`, API `/api/v2/torrents/files` HTTP 200 con cero archivos. No hay fila `Descarga` para ese torrent. No usarlo para validar archivos completados.
- El worker activo consulta periódicamente la cola (aproximadamente cada 10 s), y se comprobó que no había descargas `Descarga` en la base de producción, ni errores visibles en los logs recientes.
- `worker/download_monitor.py` interpreta estados y actualiza la tabla `Descarga` mediante `update_download_progress` de forma transaccional; **torrent completado no significa disponible en Jellyfin**.
- `backend/app/qbittorrent.py` incluye `torrent_files(hash)`, GET de lista con verificación de hash y respuesta JSON.
- `worker/file_validator.py` valida archivos terminados con rutas relativas seguras bajo directorio autorizado, tamaños, prioridad (rechaza excluidos), progreso, ausencia de escapes y enlaces simbólicos en componentes de ruta; sin escribir archivos. Este módulo se probó con **39 casos**.
- `worker/completed_files.py` consulta el hash exacto y estados completados (`stoppedUP`, `uploading`, `stalledUP`, `queuedUP`, `forcedUP`) y delega en el validador; **10 pruebas**. Todavía no se integra en el bucle activo.
- El montaje `/media:ro` impide escrituras por ese montaje, pero cualquier futura copia/publicación requerirá revalidación inmediatamente antes de operar, cuidado ante condiciones de carrera TOCTOU, prevención de duplicados y permisos expresos.

## 4. Persistencia y migraciones

- Base de producción: SQLite `/data/viewtv.db` dentro del volumen de Docker.
- Existe una copia previa con integridad verificada en `~/.local/share/viewtv-backups/viewtv-pre-worker-20261118-211407.db`. **No sustituye una copia nueva antes de migrar**.
- Migraciones en `backend/migrations/versions`; cadena 0001–0008 aplicada anteriormente.
- `0009_verificacion_descarga.py` está guardada en commit `a9ffe88`, junto con modelo ampliado `Descarga`.
- Nuevas columnas: `estado_verificacion` (`pendiente` por defecto), `verificada_en` nullable y `error_verificacion` nullable; índice `ix_descarga_estado_verificacion`.
- `0009` se probó sobre SQLite **temporal**: actualización 0008→0009, preservación de descarga preexistente, inicialización `pendiente`, downgrade sin datos, y downgrade bloqueado correctamente si existen datos de verificación.
- **0009 NO está aplicada a producción.** Evitar recrear la API desde imagen que contenga 0009 hasta tener backup actual y un procedimiento de migración controlado; el arranque de API ejecuta Alembic automáticamente.
- El worker activo puede estar ejecutando un código de imagen anterior al modelo local; nunca asumir que el commit nuevo está ya desplegado.

## 5. Commits locales recientes confirmados (sin push)

- `32aa8de` — Implementar supervision segura de descargas (enmienda de `7ccf41a`).
- `17c2907` — Montar biblioteca multimedia en worker solo lectura.
- `e17c839` — Consultar archivos de torrents con validacion de respuestas.
- `2d085d4` — Validar rutas y archivos descargados de forma segura.
- `6f0bd27` — Reforzar validacion de prioridades y tamanos de descargas.
- `3e76ffc` — Verificar archivos de torrents completados sin modificarlos.
- `a9ffe88` — Registrar estados persistentes de verificacion de descargas.

Otros commits anteriores cubren integración de búsqueda, cola, qBittorrent y reconciliación del envío ambiguo.

## 6. Siguientes hitos por orden

1. Resolver `import pytest`; ejecutar nuevas pruebas transaccionales de `record_download_verification`, fortalecer casos y guardar el cambio.
2. Comprobar semántica de estado `verificacion` y pruebas de persistencia/recuperación tras reinicio con SQLite temporal.
3. Conectar `verify_completed_files` a un proceso dedicado que detecte `Descarga.estado='completada'` con `estado_verificacion='pendiente'`, sin afectar cola principal; simular errores de qBittorrent y archivos con fixtures. Debe evitar reintentos descontrolados y nunca publicar disponibilidad por verificar.
4. Preparar copia **nueva** de la SQLite de producción, verificar `PRAGMA integrity_check`, revisar `alembic_version` y planificar migración 0009. No aplicar sin validación.
5. Incorporación segura de contenidos a `Peliculas`/`Series`: clasificación, nombres y rutas, política de copias frente a movimiento, prevención duplicados, manejo de archivos múltiples, permisos, revalidación y disponibilidad real en Jellyfin.
6. Confirmar que Jellyfin ha catalogado el medio y solo entonces reflejar `disponible` en API y PWA.
7. Probar ciclo completo, manejo de interrupciones, idempotencia, seguridad y documentación; mantener intactos originales y datos de producción.

## 7. Reglas operativas de seguridad

- Trabajar en `inventario-trabajo-local`, nunca modificar `main`.
- No hacer `push` de los 23 commits locales sin una decisión explícita de publicación; no forzar pushes.
- No usar `git add .`, `git reset --hard`, `git clean`, borrar directorios o sobrescribir copias `.bak`. Hay ficheros ajenos sin seguimiento (`=`, `CACHED`, `[auth]`, `[internal]`, `exporting`, `naming`, etc.) que deben conservarse.
- No añadir `exit 1` a bloques Bash destinados a una sesión interactiva de WSL: podría cerrar la sesión.
- Las pegadas largas en terminal muestran a veces texto mezclado, pero comprobar siempre salidas de comandos, test y diff.
- Evitar revelar credenciales de `.env` o valores de API keys en logs compartidos.
- Docker: para despliegue restringido del worker usar `docker compose up -d --no-deps --no-build --force-recreate worker`, **solo después** de validar imagen y esquema. No ejecutar `docker compose up` sin especificar servicio, ya que el arranque de API aplica migraciones.
- Estimaciones de 81 % / 17–28 h son aproximadas y no verificadas por auditoría.

## 8. Criterio de finalización

No declarar VIEWTV terminado hasta demostrar: búsqueda y selección; envío detenido a qBittorrent con confirmación; descarga real controlada; seguimiento de progreso; verificación de archivos y persistencia; incorporación reversible y sin pérdida de originales; reconocimiento y reproducción desde Jellyfin; interfaz PWA que refleja estado real; y pruebas de recuperación tras reinicios.

**Conclusión:** el bloqueador inmediato es exclusivamente la importación `pytest` en `backend/tests/test_queue.py`. No hay motivo para alterar Docker ni SQLite esta noche.