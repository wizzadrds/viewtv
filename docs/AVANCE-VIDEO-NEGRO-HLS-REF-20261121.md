# VIEWTV — pantalla negra 00:00 al reproducir «Nadie 2»

**Fecha:** 21/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
**Contexto:** [AVANCE-HLS-REPRODUCCION-NADIE2-20261121.md](AVANCE-HLS-REPRODUCCION-NADIE2-20261121.md).

## Síntoma y causa demostrada en el código

El usuario comunicó que el reproductor de VIEWTV abre una pantalla
negra con duración **00:00**. Jellyfin ya tiene el MKV verificado
y publicado con ficha y carátula, y la revisión anterior había
confirmado la negociación HLS, listas y un primer fragmento `.ts`
completo y accesible.

En `frontend/components/viewtv-app.tsx`:
- El efecto HLS empieza con `if (!playbackUrl || playbackMode !== "hls" ||
  !videoRef.current) return;`
- Se crea `videoRef = useRef<HTMLVideoElement>(null)`, pero el JSX
  `<video>` visible **NO tenía `ref={videoRef}`**.
- Por tanto, el efecto HLS salía antes de ejecutar
  `player.attachMedia(video)` y `player.loadSource(playbackUrl)`.
  En modo HLS el JSX no asigna directamente `src`; el resultado
  esperado es vídeo sin fuente, negro y `00:00`.

**Corrección:** conectar `ref={videoRef}` en ese elemento
`<video>`. No modificar Jellyfin, la transcodificación, ni el
servidor, ni el archivo descargado.

## Prueba de regresión

Nueva prueba en `frontend/tests/requests-panel.test.mjs` comprueba
simultáneamente que se declara la ref, el efecto depende de ella,
el JSX la conecta al vídeo y hls.js invoca `attachMedia(video)`.
Antes de editar el JSX, habría fallado al exigir esa conexión.
Tras editarlo:
- Tests Node/Frontend **11/11 PASS** (contenedor Node 22,
  sin red ni datos de usuario).
- Next.js 15.5.28 `npm run build`, TypeScript y lint
  durante la construcción: **PASS**.
- `git diff --check` y preflight Compose
  `HLS_REF_PREFLIGHT_OK=1`: **PASS**.
- Smoke de producción en modo lectura **10/10 PASS**.
- API `viewtv:playback-hls-api-0012` healthy,
  worker `viewtv:verificacion-compatible-worker-0012` en marcha,
  Jellyfin sin cambios, PWA nueva healthy.

## Despliegue

- Imagen PWA: `viewtv-frontend:hls-video-ref-0012`,
  construcción sobre el mismo `frontend/Dockerfile`.
- `deploy/compose.hls-video-ref-0012.yaml` y
  `scripts/viewtv_compose_hls_video_ref_0012.sh`.
  Despliegue **solo de `frontend`** con
  `docker compose ... up -d --no-deps --no-build --force-recreate frontend`.
  Ningún contenedor API/worker/qBittorrent/Jellyfin fue recreado.
- Reversión aislada: `bash scripts/viewtv_compose_hls_video_ref_0012.sh rollback`
  para volver a la imagen frontend HLS previa.
- Respaldo código y pruebas anterior:
  `~/viewtv-backups/hls-black-video-ref-pre-20261121-222742.tar.gz`,
  SHA256 `e8f0f33ee660d95e51c83a0a564c650ac0a2a63fb8a295cb7e730fcede95379e`.
- Respaldo informes anteriores:
  `~/viewtv-backups/hls-black-docs-pre-20261121-223052.tar.gz`,
  SHA256 `80238b98ceedd3f93db709ce6f45e260d197ee8a49227eb57c8f22be6928bcea`.
  Ambas copias tar fueron listadas y comprobadas.

## Verificación de usuario pendiente

Recargar `http://127.0.0.1:3000` con **Ctrl+F5**,
abrir **Películas → Nadie 2 → Reproducir** y comprobar
si pasa de 00:00 a duración válida, inicia imagen y
audio. No se ha probado el navegador autenticado real:
no afirmar que una película completa reproduzca sin cortes.
Si sigue negro, inspeccionar eventos `hls.js` en navegador
y respuestas de fragmentos vía proxy; Jellyfin sin
aceleración de hardware podría provocar buffering CPU
con vídeo 4K.

## Seguridad

La solución no accede a PINs, no modifica SQLite, qBittorrent,
Jellyfin, carpeta `Peliculas`, descarga original, ni flag
de envíos automáticos. Se preserva la API privada para HLS y
la corrección previa que evita que el backup diario reemplace
la API por una imagen antigua.
