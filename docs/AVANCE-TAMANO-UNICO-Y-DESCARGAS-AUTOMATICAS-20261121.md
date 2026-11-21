# VIEWTV — solo tamaño del torrent y descargas automáticas al elegir

**Fecha:** 21/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
**Plan maestro:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Petición y alcance

El usuario pidió explícitamente:
> «solo pon el tamaño que ponga el torrent y quita lo de comprobar
> tamaño real y solo pon ese y ya y lo hacemos automatico las descargas».

Se interpreta como opt-in **para futuras selecciones explícitas del
usuario**, no como licencia para lanzar toda la cola, recuperar la
descarga antigua #1 que el usuario descartó ni modificar otros
torrents de qBittorrent. Este hito automatiza el **envío a qBittorrent
y su inicio** al elegir «Descargar»; **NO** acredita aún un medio
finalizado ni su organización completa en Jellyfin.

## Cambios de pantalla

- `frontend/components/requests-panel.tsx`: el botón
  «Comprobar tamaño real» **se eliminó**. Al abrir «Ver resultados»
  la PWA verifica automáticamente los metadatos `.torrent` de
  las opciones mediante el endpoint ya autenticado, con máximo
  **3 consultas concurrentes**, evitando consultas duplicadas en
  cada refresco de 10 segundos.
- Antes de la respuesta aparece «Consultando tamaño…»;
  después se muestra **una única cifra de tamaño**, procedente
  del diccionario `info` del torrent y en unidades **GiB/MiB**
  precisas. Se retiraron el tamaño anunciado por Jackett,
  los avisos secundarios por diferencia de tamaños y el
  mensaje de éxito redundante. Si falla la validación o se
  había descartado ese infohash, la acción sigue bloqueada
  con mensaje de error. Nunca se presenta la cifra de Jackett
  como si fuera el tamaño real.
- El botón pasa de «Seleccionar» a **«Descargar»**. Pulsarlo
  hace POST autenticado de selección; la API existente revalida
  y guarda tamaño e infohash canónicos. La PWA ofrece ir
  a «Ver descargas» y explica que comenzará automáticamente.
- `frontend/components/downloads-panel.tsx`: estado inicial
  «Preparando descarga automática» en lugar de exigir permisos
  manuales que ahora se han concedido; el tamaño se expresa
  como GiB/MiB, no como GB/MB engañosos.

## Cola automática conservadora

- `worker/automatic_downloads.py`: nuevo selector durable.
  El umbral de activación es una **ID máxima existente** guardada
  a la hora de habilitarlo; no se envían históricos ni la ID 1.
  Solo descargas seleccionadas con resultado y infohash
  (es decir, resultado previamente autorizado por pulsación
  y verificado), con ID superior al umbral.
- Admite **una transferencia activa VIEWTV cada vez**. Da
  prioridad a una descarga ya `enviada`, `descargando` o
  `pausada`; si está pausada manualmente, **no la reanuda
  ni empieza otra**. Pasa a la próxima seleccionada cuando
  la anterior se complete. Fallidas/descartadas no regresan
  automáticamente.
- `worker/main.py`: modo
  `VIEWTV_ENABLE_AUTO_DOWNLOAD=true` únicamente cuando
  `VIEWTV_AUTO_DOWNLOAD_AFTER_ID` es válido. Al escoger una
  ID nueva, llama a `process_one_download` con **esa ID
  exacta**, staging Windows fijo y `protect_unrelated=True`;
  después llama al iniciador individual con la misma ID,
  que comprueba etiqueta, hash, ruta, estado detenido y que
  no hubo arranque ambiguo. Las flags manuales globales
  antiguas se mantienen en `false`.
- `worker/download_processor.py` evita registrar un
  .torrent si el mismo infohash ya está en qBittorrent
  **sin la etiqueta propia de VIEWTV**, por GET read-only
  previo al POST. También verifica que el hash registrado
  realmente corresponda al metainfo elegido y no envía
  ningún torrent de identidad distinta. Mantiene el
  anti-duplicado HTTP 202 de qBittorrent 5.3, la ruta
  `C:\VIEWTV\media\descargas_temporales` y `stopped=true`
  antes de ordenar el inicio por separado.
- No se tocó el esquema SQLite, los archivos de películas,
  las bibliotecas ni torrents ajenos.

## Implementación en producción

- `deploy/Dockerfile.worker-automatico-0012`:
  `viewtv:auto-worker-0012`.
  Frontend: `viewtv-frontend:automatico-0012`.
  API existente: `viewtv:tamano-canonico-api-0012`.
- `deploy/compose.automatico-0012.yaml` conserva
  `VIEWTV_ENABLE_TORRENT_SUBMIT=false`,
  `VIEWTV_ENABLE_DOWNLOAD_START=false` e ID manual vacía,
  y activa **solo** `VIEWTV_ENABLE_AUTO_DOWNLOAD=true`.
- `scripts/viewtv_compose_automatico_0012.sh` hace
  preflight estricto, despliega o revierte servicios
  individualmente, y congela **una vez** el corte de ID
  (no lo recalcula en reinicios) en
  `~/viewtv-backups/viewtv-auto-floor-0012.txt`, modo 0600.
  En este despliegue el corte confirmado es **ID 1**.
- Se recreó primero **solo el worker** y después
  **solo la PWA** con
  `docker compose up -d --no-deps --no-build --force-recreate`.
  No se recrearon API, Jellyfin ni qBittorrent.
- Validación posterior: API/frontend healthy, worker
  running, API proxy 200, smoke read-only **10/10**,
  env real `AUTO=true`, `AFTER_ID=1`, flags
  antiguas false, ID manual vacía.
  En SQLite solicitud #6 `esperando_seleccion` con
  cinco candidatos; **ninguna descarga seleccionada** y
  **ninguna candidata de autoarranque**, ID 1 permanece
  `fallida`/descartada, y qBittorrent conserva exactamente
  **un torrent ajeno**, sin etiqueta `viewtv-descarga-2`.
  No se transmitió ni inició ningún torrent en este despliegue.

## Pruebas y respaldos

- Pruebas focales de selector automático, worker,
  procesamiento y arranque acotado: **73/73 PASS**,
  incluyen id de corte, rechazo de ID antigua,
  serie de una descarga, pausa manual, errores sin
  corte válido, etiqueta propia, evitar cambio de
  infohash, no modificar qBittorrent ajeno y
  `stopped=true`.
- Suite backend completa **858/858 PASS**, solo dos
  advertencias de deprecación existentes.
- Next.js compilado en producción y TypeScript
  comprobado: **PASS**. Preflight Compose:
  `AUTO_PREFLIGHT_OK=1`, corte 1.
  Un contenedor de solo lectura con DB de producción
  montada read-only y sin red comprobó
  `AUTO_CANDIDATO_EXISTENTE=None`.
- Respaldo de código antes de los cambios:
  `~/viewtv-backups/auto-viewtv-tamano-ui-pre-20261121-011108.tar.gz`,
  SHA-256 `5c54555f8f1f363ef16bf6edad73f160bdf7ba213cde6bceb94c6e6ad94463a2`.
- Backup online SQLite antes del despliegue
  `~/viewtv-backups/api-resultados-predeploy-20261121-012009.db.tar.gz`,
  SHA-256 `1731841a478e09e838188fc5f78c69047795f3656db57e19b6bde32e03477337`,
  con `integrity_check=OK` y `foreign_key_check=OK`.
- Respaldo de informes:
  `~/viewtv-backups/auto-docs-pre-20261121-012239.tar.gz`,
  SHA-256 `74f9f18d5108a6a58159a763475964ddeca80939089efb21be8ecddb364eb408`.
  Los tres archivos tar.gz se comprobaron con `tar -tzf`.

## Límites y uso

El usuario puede recargar `http://127.0.0.1:3000`, abrir
«Buscar y solicitar» → solicitud #6 → «Ver resultados».
Al aparecer los tamaños reales, pulsar «Descargar» en
un contenido **correcto, autorizado y con espacio suficiente**.
La transferencia se añadirá y se iniciará automáticamente
si qBittorrent y Jackett responden. «Mis descargas»
refresca el progreso. Nunca se ha probado todavía
una **transferencia real completa** con este modo;
la afirmación de descarga automática es funcional,
no una confirmación de un archivo completado.

El flujo posterior de verificación final y
organización/publicación automática en Jellyfin
pertenece al hito 0013 y sigue pendiente.

Para desactivar el modo automático sin cambiar SQLite:
`bash scripts/viewtv_compose_automatico_0012.sh rollback-worker`.
Para volver también a la interfaz anterior:
`bash scripts/viewtv_compose_automatico_0012.sh rollback-frontend`.
No usar `down -v`, no fusionar PR #2 hasta verificación.
