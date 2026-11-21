# VIEWTV — enlaces Jackett 404 y rebúsqueda sin descargas

**Fecha:** 21/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
**Plan:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Síntoma y diagnóstico real

El usuario abrió «Nadie 2», solicitud #4, que mostraba:
- `Nadie.2.2025.4K.4K.SPANISH` → tamaño 16,5 GiB,
  «Es el mismo archivo .torrent que descartaste»,
  «Ya descartado».
- `Nadie.2.2025.DVDRip.SPANISH` → «Tamaño no disponible»,
  «No se pudo obtener un torrent válido», «No disponible».

Lecturas independientes **solo de metadatos** desde el Jackett
configurado, sin exponer claves ni URL, comprobaron:
- **Ambos enlaces guardados** (resultados #63 y #64)
  obtienen **HTTP 404** actualmente, repetido.
  La raíz de Jackett responde HTTP 301, así que el
  servicio es alcanzable. No es una incompatibilidad
  del parser bencode: Jackett no devuelve el archivo.
- **Nueva búsqueda directa** de `Nadie 2 2025`
  encontró 62 resultados, 2 coincidentes con el título,
  pero **los dos nuevos enlaces también devolvieron HTTP
  404**. Por tanto, rebuscar no garantiza resolverlo:
  la fuente/índice está ofertando entradas no descargables.
- En un examen **anterior**, ambos torrents sí pudieron
  leerse y presentaban el **mismo infohash** que la
  descarga #1 retirada por el usuario por incorrecta.
  Esto justifica mantener su bloqueo histórico, pero
  ahora que Jackett responde 404 no se debe interpretar
  el error de acceso como confirmación actual de identidad.
- Solicitudes #4 y #6 siguen `esperando_seleccion`;
  descarga histórica #1 `fallida` en solicitud #3
  `cancelada`. Modo automático del worker sigue
  con corte duradero ID 1.

## Solución implementada (no desbloquea enlaces rotos)

- Nuevo error `TorrentMetadataNotFoundError` dentro
  de `worker/torrent_metadata.py` para HTTP 404/410.
  Sigue dentro de `TorrentMetadataError` para mantener
  las protecciones del worker actual. El mensaje público
  no incorpora la URL ni el token del indexador.
- `backend/app/solicitudes.py` distingue
  `estado=no_verificable, motivo=enlace_no_encontrado`
  de `estado=bloqueado` por identidad previamente
  descartada; devuelve «Jackett ya no encuentra este
  resultado. Actualiza la búsqueda» y ningún hash.
  El POST directo de selección **sigue rechazando** los
  enlaces 404: la transferencia automática no se activa.
- Endpoint autenticado por perfil
  `POST /solicitudes/{solicitud_id}/actualizar-resultados`
  responde 202 y deja en `pendiente` únicamente una
  solicitud propia en `esperando_seleccion` o
  `sin_resultados` que **no contenga ningún registro
  de descarga**. Se realiza bajo `BEGIN IMMEDIATE`,
  reiniciando intentos, sin realizar networking dentro
  del bloqueo. No elimina los resultados anteriores
  hasta el resultado exitoso del worker; el procesador
  sustituye las URL actuales por el resultado de una
  búsqueda nueva. Estado pending durante la búsqueda.
  No selecciona, agrega ni inicia ningún torrent.
- Interfaz `frontend/components/requests-panel.tsx`:
  resultado con 404 muestra **«Enlace no disponible»**
  (botón deshabilitado) y mensaje útil; los bloqueados
  históricos conservan **«Ya descartado»**.
  Botón **«Actualizar resultados»** solicita una nueva
  búsqueda a petición del usuario, limpia la verificación
  obsoleta en la PWA y vuelve al listado de solicitudes.
  Sigue mostrando un solo tamaño cuando el .torrent
  realmente es legible.

## Pruebas, desplegado, limitaciones

- Pruebas nuevas:
  - Resultado 404/410 clasificado sin redirecciones.
  - Preview de perfil 404 sin exponer URL ni hash,
    POST de selección directo rechazado.
  - Rebuscar reencola solo solicitud propia, sin
    crear una descarga ni borrar resultados antiguos;
    doble petición rechazada y rechazado si ya hay
    descarga o pertenece a otro perfil.
- Tests focales **73/73 PASS**, compilación Next.js
  y TypeScript **PASS**, suite completa backend
  **864/864 PASS** (dos avisos deprecados anteriores),
  y smoke de producción de solo lectura **10/10 PASS**.
- Contenedores nuevos para API y PWA únicamente:
  `viewtv:actualizar-resultados-api-0012`,
  `viewtv-frontend:actualizar-resultados-0012`,
  **ambos healthy**. Preflight efectivo verificado con
  `PREFLIGHT_404_REBUSQUEDA_OK=1`.
  `deploy/compose.actualizar-resultados-0012.yaml`
  y `scripts/viewtv_compose_actualizar_resultados_0012.sh`
  desplegaron únicamente esos servicios con
  `--no-deps --no-build --force-recreate`,
  permitiendo rollback aislado. No se recrearon
  Jellyfin, qBittorrent ni el worker automático.
  Worker `viewtv:auto-worker-0012` permanece en
  ejecución con `VIEWTV_ENABLE_AUTO_DOWNLOAD=true`,
  `VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1`, y flags
  manuales `false`. El nuevo endpoint devuelve 401
  sin sesión, tanto vía API como PWA.
  DB real sin mutaciones: solicitud #4
  `esperando_seleccion` con dos resultados, solicitud #6
  `esperando_seleccion` con cinco; #1
  `fallida` y solicitud #3 `cancelada`.
  0 candidatas de inicio automático, un torrent ajeno
  conservado en qBittorrent y cero `viewtv-descarga-2`.
  Ningún POST de selección, envío ni inicio.
- **Limitación real:** si una búsqueda nueva sigue
  ofreciendo URLs 404, estas seguirán no seleccionables.
  Habrá que corregir el indexador/configuración de
  Jackett o usar otras fuentes válidas, pero NO
  descargar por un magnet no verificado ni ignorar
  bloqueos de identidad.
- Copia verificada del código previo:
  `~/viewtv-backups/enlaces-caducados-pre-20261121-013658.tar.gz`,
  SHA-256 `fdf8d886c4686ef7e6f00f04b88c759bfd9e178d45d428a43d32225c5a51af11`.
- SQLite real respaldo online coherente:
  `~/viewtv-backups/api-resultados-predeploy-20261121-014051.db.tar.gz`,
  SHA-256 `1184771fbd2f9a9b7de1f5044e062b9c4322495eb584457c2d9ab87e48416625`.
  `integrity_check` y `foreign_key_check` correctos,
  todos los tar.gz verificados con `tar -tzf`.
  Sin migración, sin modificaciones de medios/Jellyfin.

## Uso

Recargar `http://127.0.0.1:3000`. Abrir
«Buscar y solicitar» → «Nadie 2» → «Ver resultados».
Los que Jackett devuelva 404 figurarán «Enlace no
disponible», y los cuya identidad realmente coincida
con el torrent anterior «Ya descartado».

«Actualizar resultados» encarga otra búsqueda sin
descargar nada, aunque con las dos URLs recién
comprobadas que también devuelven 404 no se puede
garantizar la aparición de una fuente válida. No
desactivar el filtrado por infohash previamente descartado.
