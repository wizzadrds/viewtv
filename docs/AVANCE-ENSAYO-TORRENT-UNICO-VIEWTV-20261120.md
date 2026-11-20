# VIEWTV — preparar un ensayo de un único torrent, sin activarlo

**Fecha:** 20 de noviembre de 2026.
**Rama:** `viewtv-seguimiento-descargas-0012`.
**Prioridad:** terminar el flujo funcional con pruebas reales progresivas
antes de mejoras opcionales.
**Plan:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Problema que resuelve

El hito anterior separó la selección del envío real:
`VIEWTV_ENABLE_TORRENT_SUBMIT=false`. Al prepararnos para la
primera descarga controlada se detectaron dos riesgos restantes:

1. Al activar el envío global, `claim_next_download` elegiría
   **cualquier descarga seleccionada**, aunque la persona hubiese
   autorizado probar **solo una**. Por ejemplo, otra solicitud
   anterior podría consumir el ensayo.
2. `process_one_download` enviaba `stopped=true` pero no fijaba
   explícitamente la carpeta de destino. El iniciador posterior
   espera `C:\VIEWTV\media\descargas_temporales`. La discrepancia
   debe impedir iniciar la transferencia; también debemos
   detectarla **antes de declarar el alta correcta**.

No se alteró ni inspeccionó el contenido real de esa carpeta ni
se creó ningún torrent productivo.

## Código implementado

- `worker/main.py`: configura el nuevo
  `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID`, que debe ser un entero
  decimal positivo canónico. Un valor vacío, negativo, cero,
  malformado, múltiple, con ceros iniciales o fuera del rango
  SQLite hace que el envío quede **bloqueado**, aunque alguien
  habilite `VIEWTV_ENABLE_TORRENT_SUBMIT=true`.
  El worker sigue atendiendo solicitudes y refrescando el catálogo.
- `backend/app/queue.py`: añade filtro opcional
  `allowed_download_id` a `claim_next_download`. Se aplica
  **durante la selección transaccional del ID**, antes de tomar
  cualquier lease; no se reclama una segunda descarga de la cola.
- `worker/download_processor.py`: en modo de ensayo acotado,
  verifica la ruta antes de reclamar, pasa
  `save_path=C:\VIEWTV\media\descargas_temporales` a la
  llamada POST de qBittorrent, siempre `stopped=true`, y
  comprueba mediante GET posterior la **única** coincidencia de
  etiqueta, hash hexadecimal válido, carpeta de staging
  autorizada y estado `stoppedDL`/`stoppedUP`/pausado.
  Si la identidad/ruta/estado son incorrectos, no se declara
  `enviada`: se registra fallo terminal para impedir reenvío
  ciego y exigir revisión humana.
- `deploy/Dockerfile.ensayo-torrent-unico-0012`:
  overlay versionado sobre `viewtv:seleccion-sin-envio-0012`.
  Solo cambia cola, procesador de descargas y main del worker.
  API y SQLite continúan en revisión 0012.
- `deploy/compose.ensayo-torrent-unico-0012.yaml`:
  última capa Compose que conserva
  `VIEWTV_ENABLE_TORRENT_SUBMIT=false`,
  `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=""` y
  `VIEWTV_ENABLE_DOWNLOAD_START=false`.
- Los tests históricos del ciclo de worker se adaptaron a
  pasar explícitamente la ID de ensayo cuando simulan envío.

### Alcance y limitaciones deliberadas

La comprobación de staging **no crea ni da permisos** al directorio.
Una futura prueba real debe verificar en lectura la ruta efectiva
de qBittorrent en Windows, la propiedad del torrent y que sea
contenido legítimo autorizado. `stopped=true` se envía en el
formulario HTTP, pero se verifica el estado real en respuesta
antes de registrar éxito. Si qBittorrent colocase un torrent
en ruta incorrecta, queda en revisión; no se borra automáticamente.

**No activar todavía `VIEWTV_ENABLE_DOWNLOAD_START`:**
el iniciador conserva un reclamador general de trabajos pendientes.
Falta aplicar la misma restricción por ID al inicio para impedir
que arranque un torrent ajeno. Es el siguiente hito técnico
antes de la primera transferencia autorizada.

El filtro `allowed_download_id=None` se conserva como
compatibilidad de pruebas y herramientas internas; **la llamada
del worker de producción nunca lo omite si el envío está habilitado**.

## Pruebas sin red ni torrents reales

Nuevo `backend/tests/test_release_one_torrent_trial.py`.
SQLite en memoria, dos descargas ficticias **de hash diferente**,
qBittorrent de prueba y `httpx.MockTransport`.

Se comprobaron:

- Con ID autorizada de la **segunda descarga**, la primera
  permanece `seleccionada`, sin lease ni intentos consumidos;
  la autorizada recibe una sola alta detenida, etiqueta por ID
  y staging exigido.
- ID ausente o ajena: cero llamadas HTTP, cero leases y ninguna
  modificación de las descargas.
- ID cero, booleana, negativa, textual o fuera de rango y
  rutas de staging omitidas/incorrectas: rechazo previo.
- GET de reconciliación con etiqueta ambigua, hash no válido,
  estado `downloading`, etiqueta ajena, ruta inesperada o
  segmentos de navegación: rechazo cerrado, sin POST.
- Reconciliación de único torrent ya registrado: sin POST
  duplicado ni intentos consumidos.
- Respuesta de alta ambigua con ruta incorrecta: no se marca
  como enviada y no se permite reenvío automático.
- Parsing del objetivo configurado en el worker: ID canónica
  positiva o ninguna; activación global sin objetivo no envía.
- Integración **HTTP real del cliente** con servidor
  `httpx.MockTransport` sin red: secuencia
  `GET /torrents/info` →
  `POST /torrents/add` (`savepath`, `tags`,
  `stopped=true`) →
  `GET /torrents/info`.
  No se realizó ninguna llamada a `/torrents/start`.

**Resultados:** **49 pruebas focales correctas** incluyendo
los **32 tests nuevos** del ensayo acotado y del protocolo HTTP,
y **664 pruebas de la suite completa del backend correctas**,
con dos advertencias Starlette conocidas.
Ruff `check` correcto. `git diff --check` correcto.

## Respaldo antes de editar archivos existentes

`/home/viewtv/viewtv-backups/ensayo-torrent-unico-pre-20261120-195738.tar.gz`

SHA-256:
`999dfedcef3e5d2e5de27a67ec9cb94e74d1ec9dc96c84ad06860cd8c8d0caa1`

`tar -tzf` verificó exactamente seis archivos:
- `backend/app/queue.py`
- `worker/download_processor.py`
- `worker/main.py`
- `backend/tests/test_worker_main.py`
- `backend/tests/test_worker_main_verification.py`
- `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`

Se restauró selectivamente desde el respaldo el formateo
no relacionado de `queue.py` y se reaplicó solo el filtro
por ID, para evitar cambios masivos ajenos al hito.
Los tests del protocolo HTTP, Dockerfile, Compose y este
documento son **archivos nuevos**.

## Respaldo consistente de SQLite antes de desplegar

`/home/viewtv/viewtv-backups/ensayo-torrent-unico-despliegue-pre-20261120-200642/viewtv-api-0012-before-recreate.db`

SHA-256:
`adaa8f552e2bf876c85c26ae31fe58f0e7078d6b90eaa25054bf38d2d589a057`

Tamaño 163840 bytes. Copia con la API SQLite
`sqlite3.backup()` desde contenedor efímero **sin red**,
volumen origen en **solo lectura**. Comprobados
`integrity_check=ok`, revisión
`0012_inicio_torrent`, cero errores de
`foreign_key_check` y SHA-256 desde Ubuntu.
No se restauró ni modificó la estructura de SQLite.

## Despliegue

Imagen nueva:
`viewtv:ensayo-torrent-unico-0012`.

Identificador Docker:
`sha256:cd530d3e0e5508520fba3a13cc4d2aa4ed9a0d3cbf64ae307c087b094b369b8b`.

Se aplicó únicamente el worker con
`docker compose up --no-deps --no-build --force-recreate -d worker`,
usando los cuatro Compose base, los overrides previos
de catálogo, descargas, solicitudes y selección sin envío,
y como **último**:
`deploy/compose.ensayo-torrent-unico-0012.yaml`.

Compose efectivo antes de aplicar:
- API: `viewtv:predeploy-0012-release`
- Frontend: `viewtv-frontend:solicitudes-0012`
- Worker: `viewtv:ensayo-torrent-unico-0012`
- Permisos: envío **false**, ID objetivo **vacía**,
  inicio **false**.

Después del despliegue:
- Worker nuevo activo, sigue mostrando ciclos de cola.
- API, frontend, Jellyfin y FlareSolverr **healthy**.
- 10/10 smoke GET aprobados.
- Inventario SQLite en modo read-only: dos perfiles,
  dos medios, una solicitud fallida anterior,
  **cero descargas** nuevas.
- No se han hecho altas ni inicios de torrents reales,
  ni movimientos de medios ni cambios de servicios Windows.

### Reversión si hay una incidencia

**No es seguro** revertir a
`viewtv:seleccion-sin-envio-0012` mientras haya
posibilidad de activar el envío: esa imagen ignora el
nuevo requisito de ID y destino. Por eso no se proporciona
un override que regrese a esa versión insegura.

Reversión operativa **fail-closed**: detener **solo**
el worker con los mismos Compose efectivos
(`docker compose ... stop worker`), manteniendo API,
frontend, Jellyfin y datos; guardar logs y corregir hacia
delante. Esto pausa temporalmente búsquedas y sincronización
automática. No se ha necesitado ejecutar ese stop.
No usar `down -v` ni restaurar SQLite en caliente.

## Qué sigue para entregar VIEWTV

1. Comprobar con el usuario una búsqueda nueva desde
   «Buscar y pedir» y que aparezca en Descargas una
   selección real sin alta de torrent.
2. Implantar y probar **el inicio restringido a la misma ID**;
   mantener `VIEWTV_ENABLE_DOWNLOAD_START=false` mientras tanto.
3. Verificar en el host Windows la ruta de staging
   y preparar una sola descarga de prueba autorizada,
   con reversión manual y torrent identificado.
4. Verificar alta detenida, inicio separado,
   progreso, finalización y publicación segura del medio
   con el organizador 0013 y detección en Jellyfin.
5. Pruebas de recuperación, respaldo y cierre del PR
   tras autorización de la versión estable.

**No declarar la app completa todavía:** login,
biblioteca y reproducción funcionan, pero faltan
la prueba real de búsqueda/selección y la cadena de
descarga → organización → Jellyfin.
