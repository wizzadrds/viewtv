# VIEWTV — sin bloqueo de selección por un torrent histórico descartado

**Fecha:** 21/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`.

## Requisito explícito del usuario

El usuario considera excesivamente restrictivo que Jackett publique un
torrent duplicado y VIEWTV bloquee su descarga por una acción anterior.
Pidió quitar los textos y restricciones «Ya descartado», «Descargar
de nuevo» y el error «No se pudo validar el torrent o coincide con uno
descartado», y usar simplemente «Descargar» como en los demás resultados.

La petición se aplica a **nuevas selecciones explícitas**; no supone
recuperar automáticamente la antigua descarga #1 ni permitir que VIEWTV
modifique otros torrents existentes en qBittorrent.

## Cambios efectivos

- La comprobación de metainfo en
  `backend/app/solicitudes.py` ya **no consulta el historial de
  torrents fallidos/cancelados** para decidir si un candidato se puede
  seleccionar. Devuelve `estado=apto` cuando un `.torrent` es válido,
  sea nuevo o repetido. No devuelve claves `descartado_anteriormente`.
- `POST /solicitudes/{id}/seleccion` ya no pide
  `confirmar_descartado`. Guarda tamaño y SHA-1 del metainfo de
  Jackett, sin aceptar una URL arbitraria de usuario. Si el origen es
  inaccesible (HTTP 404/410) o los metadatos no se pueden validar,
  responde 409 específico, **nunca por un descarte anterior**.
- `frontend/components/requests-panel.tsx` mantiene todas las
  opciones listadas y el tamaño **único del propio .torrent**.
  Se retiraron textos «Ya descartado», «Descargar de nuevo»,
  advertencias históricas y ventanas de confirmación. Los
  resultados verificables muestran simplemente **«Descargar»**.
  Los que Jackett no entrega siguen mostrando
  «Enlace no disponible» / «No disponible» y no se envían.
- `worker/download_processor.py` elimina el veto histórico por
  infohash anteriormente descartado. El nuevo resultado queda
  autorizado por la nueva selección realizada en la API.
  Conserva revalidación de metainfo/hash, ID individual,
  limitación de una transferencia VIEWTV activa, destino
  staging Windows y protección `protect_unrelated=True`:
  **no altera un torrent ya existente fuera de VIEWTV**.
- Modo `VIEWTV_ENABLE_AUTO_DOWNLOAD=true` y umbral persistido
  `VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1`, sin modificaciones.
  No se reanuda la descarga histórica #1 ni se envía una
  descarga durante despliegue.

## Pruebas

- Focales API/worker/selector automático/arranque **90/90 PASS**;
  caso con hash histórico descartado ahora devuelve vista
  seleccionable y permite POST de nueva selección **sin campo
  extra**, guardando tamaño/hash y sin mutar histórico.
  Caso del worker prueba alta detenida de nueva selección
  previamente descartada y conserva controles.
- Ensayo real sin efectos en producción con
  `scripts/viewtv_descartado_confirmado_copia_sandbox.py`:
  copia online SQLite real, montada RO y clonada en memoria,
  GET solo de metainfo de solicitud #7:
  **PASS** metainfo real, selección sin confirmación y
  conservación de la descarga #1 fallida. **No POST a qBit**.
- Backend completo **864/864 PASS**, únicamente dos
  avisos de deprecación preexistentes; build de
  Next.js/TypeScript **PASS**.
- Preflight Compose **DESCARTADOS_OPCIONALES_PREFLIGHT_OK=1**
  comprobó tres imágenes y que el worker conserva
  `VIEWTV_ENABLE_AUTO_DOWNLOAD=true`,
  `VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1`,
  las banderas manuales `false` y la ID manual vacía.
- Se desplegaron independientemente API, worker y PWA
  con `--no-deps --no-build --force-recreate`.
  La API y PWA están `healthy`, worker `running`,
  endpoint sin sesión responde **401**, y smoke
  read-only de producción **10/10 PASS**.
- La DB productiva permanece sin cambios en las selecciones:
  solicitud #7 `esperando_seleccion`, descarga histórica #1
  `fallida`, **cero seleccionadas** y **ningún candidato
  automático**. qBittorrent conserva **un torrent ajeno**
  y ninguna etiqueta VIEWTV #2. No se agregó ni inició
  ningún torrent durante el despliegue.
- Rollback independiente de API, frontend y worker con
  `scripts/viewtv_compose_descartados_opcionales_0012.sh`.
  Imágenes API `viewtv:descartados-opcionales-api-0012`,
  PWA `viewtv-frontend:descartados-con-opcion-0012`,
  worker `viewtv:descartados-opcionales-worker-0012`.

## Respaldo

- Archivos de código antes de cambiar:
  `~/viewtv-backups/permitir-redescarga-confirmada-pre-20261121-015320.tar.gz`,
  SHA-256 `48bd52665da59f2cf398cb9f6332fdc46b1839790c837c3d314cf2a6b88255c7`,
  tar verificado.
- SQLite online coherente antes de despliegue:
  `~/viewtv-backups/api-resultados-predeploy-20261121-015654.db.tar.gz`,
  SHA-256 `75dbcffa63b0eb04ec1f2beb58da591c922d95160a551f889e7894710607fb5b`,
  integrity_check y foreign_key_check OK.
- Plan previo guardado en
  `~/viewtv-backups/plan-sin-veto-prev-20261121-020017.tar.gz`,
  SHA-256 `c33a67b63e5bd30a205e64491622fe82306f734dc3276a963b78be68a6cf88c5`.

## Pendiente de validar con un archivo real

Que el usuario elija un resultado accesible y autorizado, el worker
lo añada y lo inicie correctamente, reporte progreso y compruebe
terminación; posterior organización para Jellyfin es otro hito.
**El que dos entradas tengan un mismo infohash no confirma
que sean la película correcta**. La descarga automática no
elude la validación del .torrent ni la protección de
torrents ajenos ya existentes.
