# VIEWTV — Alta detenida ID 1: respuesta asíncrona de qBittorrent 5.3

**Fecha:** 20 de noviembre de 2026.
**Rama única:** `viewtv-seguimiento-descargas-0012`.
**Plan:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Autorización y objetivo

El usuario autorizó expresamente **dar de alta detenida únicamente la
descarga canónica ID 1**, seleccionada desde la solicitud #3 de «Nadie 2».
Reiteró que el objetivo final del producto es descargar automáticamente.
La autorización puntual NO equivale a permiso independiente para
**iniciar** un torrent ni a habilitar todos los futuros envíos. Ese
inicio y la automatización general siguen desactivados.

Antes de la prueba: SQLite real en modo lectura confirmó ID=1,
solicitud=3, selección aún no enviada, 0 % y sin hash, título/tipo
coincidentes con el buscado (no acredita derechos ni contenido real),
un enlace interno de Jackett y cero torrents con la etiqueta
`viewtv-descarga-1`. qBittorrent WebAPI respondió correctamente a
lecturas, versión **5.3.0**. En Windows: Jackett activo, staging
`C:\VIEWTV\media\descargas_temporales` directorio sin redirecciones,
preferencias de destino coincidentes y espacio disponible.

## Qué sucedió de verdad (NO se ha completado la transferencia)

1. Se creó un override de duración limitada con
   `VIEWTV_ENABLE_TORRENT_SUBMIT=true`,
   `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=1` e
   `VIEWTV_ENABLE_DOWNLOAD_START=false`. Se recreó solo el worker.
   El cliente original registró **dos intentos** sin confirmar el
   resultado de qBittorrent; se cerraron los flags inmediatamente.
2. Se constató que el enlace `/dl/` era accesible como archivo
   bencode desde Docker (GET HTTP 200), pero usaba
   `host.docker.internal`, que Windows **no resuelve**.
   Windows ejecuta Jackett en loopback puerto 9117 y qBittorrent en
   el mismo host. Se añadió una traducción estricta del enlace
   Jackett a `127.0.0.1` únicamente para el alta individual,
   sin alterar el token ni enlaces externos.
3. Se realizó **un único POST adicional puntual** (sin activar el
   envío global), con `stopped=true`, tag e ID únicos y staging.
   qBittorrent devolvió **HTTP 202**, mientras el cliente antiguo
   esperaba solo el texto `Ok.`. Total: **3 intentos registrados**.
   Tiempo después, GET encontró exactamente **un torrent etiquetado,
   detenido y con staging correcto**.
4. Mediante operaciones estándar de cola
   `claim_next_download(... allowed_download_id=1)` y
   `mark_download_submitted`, con **GET y SIN nuevo POST**, se
   reconcilió el registro en SQLite: `estado=enviada`,
   `inicio_estado=pendiente`, hash asociado, progreso 0 %.
5. **Incidencia posterior no resuelta:** una comprobación de
   estabilidad volvió a mostrar **0 coincidencias en qBittorrent
   por la etiqueta y por el hash guardado**. Su API continúa
   respondiendo y hay otro torrent, que se ha mantenido intacto.
   VIEWTV conserva la fila `enviada`, pero **no hay garantía de que
   el torrent permanezca en qBittorrent**. No iniciar ni afirmar
   que la descarga funciona hasta investigar la desaparición.
   El supervisor actual no resuelve automáticamente esta
   discrepancia mientras `inicio_estado=pendiente`.

Las últimas alertas de la API de logs de qBittorrent contienen
errores asociados a URLs HTTP de archivos .torrent, pero no prueban
qué proceso retiró la única entrada que apareció. No se muestran
los mensajes completos porque pueden contener URLs o información
privada. No se han eliminado torrents ni archivos.

## Corrección técnica desplegada, sin envíos nuevos

- `worker/download_processor.py`: traduce **solo** enlaces
  `http://host.docker.internal:<puerto>/dl/...` de la misma
  instancia Jackett configurada a loopback Windows durante el
  ensayo por ID; no reescribe otros dominios ni magnet.
- `backend/app/qbittorrent.py`: admite respuesta WebAPI 2.14+,
  reconoce JSON de éxito y distingue el HTTP 202 con alta
  asíncrona mediante `QBittorrentAddPending`.
- `worker/download_processor.py`: registra un marcador pendiente
  en `ultimo_error`; si todavía no aparece la etiqueta, las
  siguientes consultas **no vuelven a hacer POST** ni consumir
  otro intento. Si el torrent aparece con identidad, destino
  y estado detenido válidos, lo reconcilia. Una espera que nunca
  se materialice requiere diagnóstico manual, no bucles de envío.
- Dos capas Docker: `viewtv:qbit-windows-url-0012` y
  `viewtv:qbit-async-0012` (esta última es la desplegada).
  Último override `deploy/compose.qbit-async-0012.yaml`;
  worker recreado solo con `--no-deps --no-build --force-recreate`.
  En producción los tres controles siguen cerrados:
  envío `false`, ID vacía, inicio `false`. API y PWA no se
  recrearon. No se modificó el esquema ni la versión 0013.
- Compatibilidad respaldada por el changelog oficial qBittorrent:
  https://github.com/qbittorrent/qBittorrent/blob/master/WebAPI_Changelog.md
  (WebAPI 2.14.0: `pending_count` y HTTP 202).

## Evidencia y seguridad

- 55/55 pruebas focales para URL/alta antes del cambio asíncrono;
  **81/81** focales después y backend completo **796/796**,
  dos avisos deprecados no bloqueantes.
- Pruebas HTTP simuladas con `httpx.MockTransport`, SQLite en
  memoria, distintas IDs, una sola orden detenida y recuperación
  sin repetir POST tras HTTP 202.
- Smoke GET posterior **10/10 PASS**. API y frontend `healthy`,
  worker `running`. No se ejecutó ninguna orden `start/resume`.
- No se han accedido ni modificado medios de
  `C:\VIEWTV\media\Peliculas`, no se movieron bibliotecas,
  no se tocó Jellyfin, no se leyó PIN/cookie ni se expuso URL,
  API key o hash del torrent.

## Respaldos previos con comprobación SHA-256 y tar

1. SQLite antes del ensayo,
   `~/viewtv-backups/api-resultados-predeploy-20261120-234038.db.tar.gz`,
   SHA-256 `664f80af4c5f49b3cb1db2df036795fac419a4a2657717a67bd98beb1090f27e`.
2. Código original antes del ajuste de enlace,
   `~/viewtv-backups/corregir-url-qbit-windows-20261120-234543.tar.gz`,
   SHA-256 `19891b285780d51f2816fa485b10c35e1f145265021beebea8f4e8366432384f`.
3. SQLite después de los intentos iniciales,
   `~/viewtv-backups/api-resultados-predeploy-20261120-234758.db.tar.gz`,
   SHA-256 `c21d3056777aae7cd6696c5a219b12e1d2d699d9b2f859f8a2c9aff50fbaac04`.
4. Código antes de tratar la respuesta HTTP 202,
   `~/viewtv-backups/qbit-202-asyncrono-pre-20261120-235310.tar.gz`,
   SHA-256 `febe41430b59d01477f3fe19fadad40d79d7d3eebd7b0ee3e460f445099149af`.
5. Configuración puntual de envío originalmente activa
   archivada antes de desactivarla:
   `~/viewtv-backups/viewtv-id1-submit-experiment-archive-20261120.tar.gz`,
   SHA-256 `58790450359b5be295cb9a1cf0f2a65e3bf064428e60ffe196e299117105768b`.

Cada archivo `tar.gz` se verificó mediante `tar -tzf`;
la copia SQLite mediante `sqlite3.backup`, `integrity_check=ok`
y `foreign_key_check=0`. El YAML operacional puntual que queda
fuera de Git se modificó a **flags false/ID vacía**, modo 0600;
el original activo solo consta dentro del tar archivado.

## Pendiente imprescindible

**No activar inicio ni envíos generales todavía**: confirmar dónde
desaparece el torrent de qBittorrent después de la aceptación
asíncrona; si procede, probar con nueva autorización puntual la
entrega de metadatos `.torrent` como archivo en vez de URL,
siempre sin iniciar y garantizando ausencia de duplicados. Verificar
identidad, destino, estado estable y después solicitar permiso
separado para arrancar ID 1. Solo después de una transferencia
completa autorizada plantear el modo automático opt-in del usuario,
sin abrir la cola a descargas ajenas. No se ha ejecutado otro POST.

Reversión de código: omitir la última capa
`compose.qbit-async-0012.yaml` y recrear solo el worker con
`compose.qbit-windows-url-0012.yaml`, conservando envío/inicio
en `false`. Mantener respaldo SQLite, no restaurar mientras
los servicios siguen funcionando, no usar `docker compose down -v`.
PR #2 sigue en borrador y no se fusiona.
