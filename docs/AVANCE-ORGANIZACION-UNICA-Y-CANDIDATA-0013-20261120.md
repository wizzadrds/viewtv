# VIEWTV — organización por una ID y candidata integrada de entrega 0013

**Fecha:** 20 de noviembre de 2026.
**Rama:** `viewtv-seguimiento-descargas-0012`.
**Objetivo:** preparar el despliegue funcional de la cola 0013 con el
mismo alcance **de una única descarga identificada** utilizado para
enviar e iniciar torrents. Priorizar entrega, sin ampliar el broker
sandbox ni activar acciones sobre medios del usuario.

**Plan:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Cambio necesario: la organización debía respetar la ID de la descarga

La cola `claim_next_organization` aún seleccionaba el primer trabajo
elegible del conjunto. Tras limitar la **alta** y el **inicio** de
qBittorrent a `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID`, la organización
necesitaba la misma restricción para una prueba de una sola descarga.

Cambios:

- `backend/app/organization_queue.py`: filtro opcional
  `allowed_download_id` validado como entero SQLite positivo no
  booleano, dentro de las condiciones de **selección y UPDATE** de
  la transacción de reclamación `BEGIN IMMEDIATE`. Si no existe esa
  descarga, no reclama ninguna otra ni consume intentos.
- `worker/organization_runner_sandbox.py`: admite y transmite
  `allowed_download_id` al reclamador; siguen vigentes todos los
  controles de sandbox, lease y no sobrescritura.
- `worker/organization_jellyfin_bridge_sandbox.py`: elimina una
  preconsulta no transaccional que rechazaba dos descargas elegibles;
  ahora restringe directamente el claim a `expected_download_id`
  para que un trabajo diferente nunca se publique por error.
- `backend/tests/test_organization_one_download_release.py` nuevo,
  junto al ajuste focal del test anterior de puente: dos descargas
  ficticias, solo la segunda autorizada reclamable, otra sin cambios,
  no coincidencia, IDs malformadas, dos trabajadores, lease caducado
  y compatibilidad de llamadas históricas. El caso de integración
  con Jellyfin simulado verifica que publicar una ID no altera otra.

**Resultado:** 99 pruebas focales aprobadas de cola, ejecución de
organizador y puente a Jellyfin, sin red ni datos de producción.

## Dos imágenes candidatas 0013, NO desplegadas

Se crearon **dos** Dockerfiles de actualización incremental, sin
reconstruir componentes ajenos al hito:

- `deploy/Dockerfile.release-0013-api-candidate`:
  desde `viewtv:predeploy-0012-release`.
- `deploy/Dockerfile.release-0013-worker-candidate`:
  desde `viewtv:inicio-torrent-unico-0012`, preservando la
  protección de envío e inicio por ID ya desplegada.
- Ambos incorporan modelo 0013, cola compatible, módulo de
  organización y la migración `0013_cola_organizacion.py`.
  El worker **no importa ni ejecuta** el organizador desde
  `worker/main.py`; no hay servicio Windows de publicación activo.
- `deploy/compose.release-0013-disabled-candidate.yaml`:
  muestra las dos imágenes juntas y fija explícitamente
  `VIEWTV_ENABLE_TORRENT_SUBMIT=false`,
  `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=""`,
  `VIEWTV_ENABLE_DOWNLOAD_START=false` y
  `VIEWTV_ENABLE_ORGANIZATION=false`.
  **La última variable es solo informativa actualmente:** el worker
  no tiene consumidor de organización que pueda habilitarse.
  Este override es una **candidata para un ensayo posterior**; NO
  se ha utilizado `docker compose up` con él.

Imágenes Docker construidas localmente, sin red:

- API `viewtv:release-0013-api-candidate`:
  `sha256:8ee3cd921e064b68ff6a30a86b7f812ecaa92dd47e70b7bfeb1c5ee655239489`
- Worker `viewtv:release-0013-worker-candidate`:
  `sha256:de016cf991108061e1a647f1330753134c260b822694301423c824b70843ca1c`

El `docker compose config --format json` de las cuatro capas
base, los overrides anteriores y esta capa final confirmó que
API y worker apuntarían a las candidatas, frontend conservaría
`viewtv-frontend:solicitudes-0012`, alta e inicio seguirían
**desactivados**, ID vacía y organización desactivada.

Las **dos imágenes** respondieron al comando Alembic `heads`
sin privilegios con `0013_cola_organizacion (head)`.

## Problema detectado y solucionado antes del despliegue

El primer intento de migrar la COPIA SQLite como UID 1000 falló
**antes de ejecutar DDL** porque la imagen antigua conservaba
`0008_solicitud_jellyfin_nullable.py` con permisos 0600 de root.
Al resolver todas las migraciones, Alembic no podía leerla.
La copia permaneció íntegra y en revisión 0012 (verificada de nuevo).

Se añadió `RUN chmod 0644` **solo para ese archivo de código**
en ambas imágenes candidatas. No se alteró la instalación real.
Después, Alembic ejecutado como usuario **1000**, con
`--network none`, `--read-only`, sin privilegios ni
capacidades, pudo resolver la cadena y completar el ensayo.
Esto evita exigir root para la migración de la futura entrega.

## Ensayo actual de migración y reversión: 0012 → 0013 → 0012

Antes de probar, se creó una copia SQLite **online consistente**
desde el volumen de producción montado en **solo lectura**,
mediante `sqlite3.backup()` y un contenedor efímero sin red:

`/home/viewtv/viewtv-backups/rc-0013-migracion-pre-20261120-212556/viewtv-api-0012-before-recreate.db`

SHA-256:
`592af113617f4b4fc3c30507f02219d44c3d6a7e0d68744a20f6b83781b27c95`

Tamaño: 163840 bytes. `integrity_check=ok`, sin errores
de `foreign_key_check`, revisión 0012.

**Nunca se migró este respaldo original:** se copió a
`.../rc-0013-migracion-pre-20261120-212556/ensayo/viewtv.db`.
Solo esa segunda copia se montó **escribible** como `/data`
en un contenedor desechable. Ningún contenedor real fue
reiniciado; no se montaron archivos de películas.

Comprobaciones con el nuevo script
`scripts/viewtv_release_0013_sqlite_verify_readonly.py`:

1. Antes: `0012_inicio_torrent`, seis columnas 0013 ausentes,
   integridad y FK correctas, cero organización pendiente.
2. `alembic upgrade 0013_cola_organizacion`: **exit code 0**,
   usuario no privilegiado. Revisión 0013, seis columnas presentes,
   ninguna descarga histórica activada.
3. `alembic downgrade 0012_inicio_torrent`: **exit code 0**;
   revisión 0012, columnas 0013 ausentes, integridad y FK correctas.
4. En las tres fases se mantuvieron los mismos agregados
   **2 perfiles, 2 medios, 1 solicitud, 0 descargas, 0 resultados**.
5. El respaldo de origen conserva su mismo SHA-256 tras el ensayo.

**Limitación:** esta copia productiva contiene cero descargas;
no se ha probado con trabajos activos de producción. La reversión
0013 solo es legal si no se crearon estados de organización: el
downgrade está diseñado para denegar una pérdida de estado.
Las pruebas en SQLite ficticia cubren los trabajos con leases y
dos descargas, pero no sustituyen una migración sobre una base
con operaciones reales.

## Respaldos selectivos del código

Antes de editar los cuatro archivos de implementación y plan:

`/home/viewtv/viewtv-backups/organizacion-id-unica-pre-20261120-211852.tar.gz`

SHA-256:
`dac387656901747e49d801778ea043d54063be9a05c18fad9bd54dbbc0b596de`

Contiene únicamente:
- `backend/app/organization_queue.py`
- `worker/organization_runner_sandbox.py`
- `worker/organization_jellyfin_bridge_sandbox.py`
- `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`

Antes de ajustar el test previo:
`/home/viewtv/viewtv-backups/organizacion-id-pruebas-pre-20261120-211852.tar.gz`

SHA-256:
`6582bec67404fc6ab02433d3b3d0b1654023798dde1b099541f7ef877d85b2d4`

Solo `backend/tests/test_organization_jellyfin_bridge_sandbox.py`.

Antes de corregir el permiso 0008 en Dockerfiles nuevos:
`/home/viewtv/viewtv-backups/rc0013-permisos-alembic-pre-20261120-212556.tar.gz`

SHA-256:
`3f603c84bb6749e94227863732907ce8ef0a41c4b31993e1fee05d08c9667862`

Solo los dos Dockerfiles de candidata. Los tests nuevos,
script de verificación, override y este informe son archivos
creados durante el hito, sin versión anterior.

## Estado de entrega y siguiente paso REAL

- Producción continúa en **Alembic 0012**:
  API `viewtv:predeploy-0012-release`,
  worker `viewtv:inicio-torrent-unico-0012`,
  frontend `viewtv-frontend:solicitudes-0012`.
  Las descargas permanecen desactivadas; Jellyfin y la PWA
  siguen operativos. Smoke de solo lectura **10/10 PASS**.
- El siguiente hito funcional es probar **una búsqueda y selección
  legítimas con resultados desde la interfaz**, y una única
  descarga autorizada con seguimiento.
- Antes de desplegar 0013, falta conectar de verdad un ejecutor
  Windows confinado al directorio de biblioteca y a la ID,
  revalidar lease y torrent durante publicación, y verificar
  detección **en Jellyfin real** con una biblioteca de demostración.
- Las imágenes candidatas y el ensayo de migración están listos,
  **pero la candidata no incluye un organizador productivo**.
  No fusionar PR #2 ni anunciar la app totalmente terminada.

**Reversión del cambio de este hito:** no hay cambios en los
servicios productivos ni en su base; los nuevos artefactos
Docker son versiones separadas. No es necesario revertir
contenedores. El rollback Alembic solo se ensayó sobre una
copia desechable y no se ejecutará automáticamente en producción.

**Tests backend completo:** **754 pruebas aprobadas**, exit code 0
(99,14 segundos) y 2 advertencias conocidas de deprecación
Starlette, con pytest sin caché y sin generación de bytecode.
La suite incluye la cola 0013 por ID y el puente de organización.
`ruff check` y `git diff --check` correctos; formato de
los archivos nuevos verificado. El smoke HTTP después de las
pruebas siguió en **10/10 PASS**.
