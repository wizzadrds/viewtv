# VIEWTV — verificación del tamaño REAL antes de seleccionar

**Fecha:** 21/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
**Plan:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

> **Actualización 21/11/2026, posterior a este hito:** se confirmó
> que Jackett puede anunciar tamaños erróneos. VIEWTV **ya no bloquea
> únicamente por esa diferencia**: el tamaño canónico se obtiene y
> guarda desde el `.torrent`, manteniendo bloqueos por identidad
> descartada o metainfo inválido. Véase
> [AVANCE-TAMANO-CANONICO-DESDE-TORRENT-20261121.md](AVANCE-TAMANO-CANONICO-DESDE-TORRENT-20261121.md).
> Lo descrito debajo refleja el comportamiento de la versión anterior.

## Objetivo

El usuario quiere usar VIEWTV para llegar a un flujo automático
de búsqueda → elección → transferencia → verificación → Jellyfin,
pero detectó dos resultados donde el tamaño de Jackett no era
el del archivo `.torrent`. El más reciente es
`La.Odisea.2026.4K.4K.SPANISH`, solicitud **#6**,
descarga canónica **ID 2**, anunciado **20 GiB**
(`21474836480` bytes), frente a metainfo `33260748236`
bytes (aproximadamente **33,26 GB** o 31 GiB). El resultado
todavía está `seleccionada`, 0 % y **0 intentos de envío**.

No se debe añadir ni iniciar ese torrent ni abrir automáticamente
la cola por coincidir el título; las comprobaciones de metadatos
no prueban que el vídeo sea el título correcto ni derechos de uso.

## Cambios desplegados

- `GET /solicitudes/{solicitud_id}/resultados/{resultado_id}/verificacion`:
  autenticado por perfil, solo solicitud `esperando_seleccion`,
  resultado de esa solicitud y título coincidente. El cliente
  no controla ni recibe URLs, infohash, claves ni rutas.
  Realiza únicamente GET de metainfo `.torrent` desde el
  Jackett `/dl/` guardado (misma instancia, sin redirecciones,
  timeout 15 s y 4 MB máximo mediante el módulo de
  `worker/torrent_metadata.py` existente).
  Devuelve `tamano_anunciado_bytes`, `tamano_real_bytes`,
  `estado=apto/bloqueado/no_verificable`,
  `puede_seleccionar` y mensajes seguros.
  Coteja el tamaño real y hashes de torrents anteriormente
  fallidos en solicitudes canceladas **solo del mismo perfil**.
- `POST /solicitudes/{id}/seleccion` comprueba otra vez los
  resultados de `/dl/` Jackett antes de `BEGIN IMMEDIATE`.
  Si el tamaño difiere o el torrent está descartado, responde
  409, sin cambiar DB ni enviar nada a qBittorrent.
  Recomprueba dentro del bloqueo que no cambiaron enlace,
  título, tamaño ni hash. Los resultados de fuentes ajenas
  se mantienen en la ruta legacy por compatibilidad,
  pero la nueva PWA los clasifica como no verificables y
  no permite seleccionarlos desde la interfaz.
- `frontend/components/requests-panel.tsx`: botón
  **«Comprobar tamaño real»** por resultado, sin N consultas
  automáticas cada 10 s. Muestra tamaño publicado y real,
  junto con advertencias, bloquea **«Seleccionar»** hasta
  obtener estado `apto`. Permite verificar otra vez y
  cambia la unidad binaria de GB/MB a **GiB/MiB**.
  La API revalida al seleccionar para no fiarse de un
  estado visual previo. Interfaz y estilos accesibles
  con `data-spatial`, avisos `role=status` y opciones
  compatibles con móvil.

## Validación de seguridad y despliegue

- Suite de solicitudes: **47/47 PASS**. Nuevos casos cubren
  discrepancia de tamaño, POST directo rechazado, mismo hash
  descartado, resultado apto, fuente no verificable sin GET
  externo, falta de respuesta de Jackett y aislamiento por
  perfil/estado. Se preservan las pruebas de selección legacy.
- Backend completo **835/835 PASS**, dos avisos de deprecación
  ya existentes. Build Next.js y TypeScript **PASS**.
- `scripts/viewtv_preseleccion_real_copia_sandbox.py`:
  SQLite real copiada **solo a memoria**, solicitud #6
  vuelta a `esperando_seleccion` **en la copia únicamente**,
  conexión a Jackett para metadatos reales:
  **5/5 PASS** (33,26 GB, bloqueo, sin filtrado de URLs/hashes,
  POST directo rechazado, producción no tocada). El sandbox
  no contactó qBittorrent para alta ni inicio.
- Imagen API `viewtv:preseleccion-real-api-0012`, derivada de
  `viewtv:descartar-incorrecta-api-0012`, copia el módulo
  de verificación del worker y el endpoint nuevo sin migración.
  PWA `viewtv-frontend:preseleccion-real-0012`.
  `deploy/compose.preseleccion-real-0012.yaml` y
  `scripts/viewtv_compose_preseleccion_real_0012.sh`
  para preflight, despliegue y rollback por separado.
- Despliegue `--no-deps --no-build --force-recreate`
  **solo API y frontend**, ambas `healthy`.
  El worker `viewtv:validacion-tamano-0012` se conservó
  y permanece `running`. Config efectiva:
  `VIEWTV_ENABLE_TORRENT_SUBMIT=false`,
  `VIEWTV_ENABLE_DOWNLOAD_START=false`,
  `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID` vacía.
  Producción smoke de solo lectura **10/10 PASS**,
  endpoint nuevo sin sesión responde **401**,
  proxy de la PWA devuelve 401. Jellyfin intacto.
  Tras deploy ID 2 sigue `seleccionada`, 0 %,
  0 intentos, sin hash; qBittorrent 0 coincidencias
  para `viewtv-descarga-2`.

## Respaldos verificados

1. Antes de modificar API, tests, PWA y plan:
   `~/viewtv-backups/preseleccion-tamano-real-20261121-004209.tar.gz`;
   SHA-256 `b70a0c61db8fdce5af50c5615e640a05af2a50179a68b5558294f7223b31b221`.
2. Estilos, antes de modificar:
   `~/viewtv-backups/preseleccion-estilos-20261121-004422.tar.gz`;
   SHA-256 `1628f39559905b857fe052807f0b37e744f9e58989e2d5ac2ddfde89c9b66fbc`.
3. SQLite online íntegra, `integrity_check=OK` y
   `foreign_key_check=0`:
   `~/viewtv-backups/api-resultados-predeploy-20261121-004613.db.tar.gz`;
   SHA-256 `ce6c4419bb20596b4a4422b2dcdc456beb23ad2d2ed52973b7c35337ffa406da`.

Cada tar.gz se verificó con `tar -tzf`, y SQLite mediante
copia consistente con `sqlite3.backup`. No se restauraron
datos ni se modificó `C:\VIEWTV\media\Peliculas`.

## Qué debe hacer el usuario / próximo hito

1. Recargar `http://127.0.0.1:3000` (PWA en caché puede
   requerir reinicio).
2. «Mis descargas»: pulsar **«Deshacer selección»** en
   `La.Odisea.2026.4K.4K.SPANISH` (ID 2). Es una elección
   con **0 intentos**, sin hash y sin torrent en qBittorrent.
3. «Buscar y solicitar» → solicitud #6 →
   **«Ver resultados»** → **«Comprobar tamaño real»**.
   El candidato de 20 GiB debe quedar BLOQUEADO
   porque los metadatos indican 33,26 GB. Buscar otra opción
   verificable y distinta.
4. No habilitar aún el inicio ni la cola automática.
   Faltan demostrar alta detenida, inicio específicamente
   autorizado, progreso, verificación del contenido y
   organización para un resultado correcto. El objetivo
   futuro de automatización sigue abierto.

**Rollback:** `bash scripts/viewtv_compose_preseleccion_real_0012.sh rollback-api`
y `rollback-frontend`, cada uno de forma aislada; no
hacen migraciones ni afectan al worker ni a media.
PR #2 permanece borrador, sin fusionar.
