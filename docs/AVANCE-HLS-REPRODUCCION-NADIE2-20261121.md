# VIEWTV — corregida la reproducción de Nadie 2 mediante Jellyfin HLS

**Fecha:** 21/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`.

## Incidencia comunicada

Tras publicar el vídeo en `Peliculas/Nadie 2 (2025)`, el usuario
pudo ver título, carátula y sinopsis, pero la PWA rechazaba
«Reproducir» con **«No hay una fuente Direct Play disponible»**.
El MKV existe en Jellyfin y estaba correctamente verificado.
No era un error de la descarga, de la carátula ni de permisos.

Diagnóstico sin exponer identificadores ni credenciales:
- Jellyfin devuelve una fuente de contenedor `mkv`, vídeo
  **HEVC/H.265** 3836×1600 (aprox. 24,3 Mb/s), audio
  **E-AC3** y otras pistas AC3/E-AC3.
- El perfil web antiguo de VIEWTV solo anunciaba
  Direct Play para `mp4/m4v/webm` con códecs de
  navegador, **sin `TranscodingProfiles`**.
  Jellyfin respondía `SupportsDirectPlay=false`,
  `SupportsTranscoding=false`, sin URL de reproducción.
- Una negociación de solo metadatos con perfil HLS
  H.264/AAC devolvió `SupportsTranscoding=true`,
  protocolo `hls` y lista `.m3u8`. La aceleración
  de hardware de Jellyfin está `none`, por lo que
  la conversión 4K puede consumir CPU y no queda
  garantizada reproducción fluida en todos los equipos.

## Implementación desplegada

- `backend/app/jellyfin_playback.py`: el dispositivo
  VIEWTV Web anuncia **HLS TS, vídeo H.264 y audio AAC**,
  bitrate máximo inicial de 8 Mb/s; conserva preferencia
  por Direct Play cuando sea compatible. `POST
  /jellyfin/media/{id}/playback-info` ahora devuelve
  `modo=direct|hls` y un URL privado local para
  una fuente Jellyfin transcodificable.
- Nuevo `backend/app/jellyfin_hls.py`: proxy de HLS
  same-origin, listas master, variantes y fragmentos.
  Firma rutas con HMAC-SHA256 usando clave privada
  del backend, caducidad 4 horas y vínculo a ID de
  medio. Solo admite host de Jellyfin configurado,
  prefijo `/videos/`, sufijos multimedia concretos y
  rutas sin escapes ni redirecciones. Elimina campos
  `ApiKey`/`api_key`/tokens de los parámetros
  upstream y utiliza `Authorization` únicamente entre
  API y Jellyfin. Reescribe los URI de variantes,
  `#EXT-X-MEDIA`, mapas y fragmentos a
  `/api/viewtv/jellyfin/media/{id}/hls`.
  No expone hosts, rutas de disco, hash ni clave de
  Jellyfin al navegador.
- `GET /jellyfin/media/{id}/hls`: requiere la sesión
  de perfil VIEWTV, medio disponible, enlace firmado y
  no caducado. Las listas `.m3u8` se reescriben
  con máximo 2 MiB de entrada; los fragmentos se
  transmiten en flujo, conservando los rangos
  permitidos, no se descargan íntegros en memoria
  del backend.
- PWA `frontend/components/viewtv-app.tsx`: selecciona
  Direct Play si existe y si no HLS; incorpora
  `hls.js 1.7.4` para MediaSource en Chrome/Firefox/
  dispositivos compatibles y HLS nativo donde exista.
  Limpia el reproductor al cerrar la ficha y conserva
  los controles HTML5 y la navegación de la aplicación.
  La firma de contenido se mantiene protegida por API,
  sin meter claves en el cliente.
- Imágenes nuevas:
  `viewtv:playback-hls-api-0012`,
  `viewtv-frontend:playback-hls-0012`.
  Se recrearon **únicamente API y PWA** mediante
  `scripts/viewtv_compose_playback_hls_0012.sh`.
  Worker sigue `viewtv:verificacion-compatible-worker-0012`,
  descarga automática y corte ID 1 intactos; Jellyfin,
  torrents, vídeo y SQLite sin modificaciones.
  Rollback aislado API/PWA disponible.

## Comprobaciones

- Tests de HLS y reproducción: negociación, compatibilidad,
  rutas firmadas, caducidad, host externo prohibido,
  rechazo de redirecciones, proxy de listas/fragmentos,
  401 sin sesión y ausencia de claves en URLs.
  Backend completo **879/879 PASS** con 2 warnings
  preexistentes de deprecación; nueva suite específica
  **12/12 PASS**. Next.js 15.5.28 build producción
  y TypeScript **PASS** con `hls.js 1.7.4`.
- Pruebas estáticas de la interfaz con Node.js 22 en
  contenedor aislado de red **10/10 PASS**. Se corrigió
  una prueba antigua que seguía esperando que la
  selección NO iniciara automáticamente un torrent,
  pese a que el usuario habilitó ese comportamiento
  en la release previa; se añadió comprobación del
  uso de `hls.js`, su limpieza y preferencia de Direct Play.
  Respaldo de prueba anterior:
  `~/viewtv-backups/frontend-test-auto-pre-20261121-031547.tar.gz`,
  SHA256 `8d91b06a18c3f5997f64f7e94d56fe3625d9f039abfa583248e5fb9e8fef0112`.
- Preflight Compose `PLAYBACK_HLS_PREFLIGHT_OK=1`,
  API/PWA healthy, worker sin recrear.
- **Jellyfin real**: tras instalar API HLS, el POST de
  negociación devuelve `estado=listo` y `modo=hls`
  para el mismo MKV. La lista principal responde
  HTTP **200**, `#EXTM3U`, y se reescribe
  correctamente a URL privadas. La lista variante
  responde HTTP **200**, con **1340 fragmentos**;
  la PWA/backend generan 1340 URLs locales firmadas,
  sin `ApiKey`/clave del proveedor.
- Se solicitó **solo el primer fragmento** a Jellyfin:
  HTTP **200**, `Content-Type: video/mp2t`,
  recibidos 32.768 bytes, sin guardar ni alterar
  el vídeo descargado. El mismo circuito de
  negociación y manifest pasó `TestClient` de la
  API autenticada (autorización solo de laboratorio
  por override en proceso efímero), sin PIN ni
  cambios de sesión del usuario. La reproducción
  visual continuada en el navegador **aún debe
  comprobarla el usuario**.
- Smoke producción read-only **10/10 PASS**,
  catálogos y Jellyfin saludables.

## Otro fallo detectado y reparado: backup diario recreaba API antigua

Durante el despliegue, el proceso de backup diario
de Windows, cuyo script de WSL es
`/home/viewtv/projects/viewtv/scripts/backup-daily.sh`,
recreó `viewtv-api-1` con la imagen **`viewtv:local`**
al ejecutar `docker compose up -d api` solo con el Compose
base. La imagen antigua reiniciaba por desconocer
la revisión real de SQLite `0012_inicio_torrent`.
Este fallo afecta a toda VIEWTV, incluida reproducción
y catálogo, no solo al vídeo.

- Se hizo respaldo **antes** de editar el script operativo:
  `~/viewtv-backups/backup-diario-compose-pre-20261121-030839.tar.gz`,
  SHA256 `ce98ad5aaefd2c088c33cbac494cfc1d35ca735bad45d1f39aa7ad1def325df5`,
  verificado `tar -tzf`.
- Se modificó **únicamente** ese script operativo,
  retirando el `docker compose up -d api` destructivo
  y sustituyéndolo por una comprobación del contenedor
  `viewtv-api-1` ya en ejecución. La copia diaria
  conserva `docker compose exec -T api` para realizar
  el backup sobre la imagen real; comprobado
  directamente que ejecuta comandos dentro de
  la API actual sin sustituirla. Sin tocar la
  tarea Windows `VIEWTV - Backup diario`, ni alterar
  las copias de seguridad existentes.
- Se volvió a desplegar `viewtv:playback-hls-api-0012`
  con el override completo; health 200 y
  `healthy`. Se comprobó el HLS real después de la
  restauración. No modificar el Compose base desde
  la rama de desarrollo ni restaurar el script
  antiguo salvo que se elimine la instrucción de
  recreación destructiva.
- Respaldo online coherente de SQLite anterior
  al despliegue de HLS:
  `~/viewtv-backups/api-resultados-predeploy-20261121-030428.db.tar.gz`,
  SHA256 `59d308a71c8c24cadc5ebe50b959fa03ddbaba6fef9d5d3c22843b6b7756581d`;
  `integrity_check` y `foreign_key_check` OK.
- Código anterior HLS:
  `~/viewtv-backups/hls-playback-pre-20261121-025559.tar.gz`,
  SHA256 `e9a8e0303344696f5b41660cd31df9962b373af801e67e3890ba9148f10f496f`.
  Los scripts de backup operativos no se subieron ni
  copiaron al repositorio de desarrollo; el cambio
  queda registrado aquí y protegido por respaldo.

## Pendiente y uso

Recargar `http://127.0.0.1:3000` (si se mantiene código
antiguo en caché, refresco forzado), abrir «Nadie 2»
y pulsar **Reproducir**. Ahora se usa HLS si no hay
Direct Play. El tiempo de inicio y la fluidez dependen
del procesador de Jellyfin: la prueba del primer
fragmento no demuestra 2 horas de reproducción sin cortes.

**No son cambios del organizador:** las películas futuras
continúan pendientes de automatización de publicación.
La reparación HLS únicamente mejora la reproducción
de los medios ya catalogados. No hay cambios de biblioteca,
descargas ni permisos de torrents.

**Rollback:** `bash scripts/viewtv_compose_playback_hls_0012.sh
rollback-api` y `rollback-frontend` revierten solamente
API y PWA; restaurar la versión antigua **no**
rehabilita la seguridad del backup, que es un arreglo
operativo independiente necesario.
