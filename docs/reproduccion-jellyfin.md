# Reproducción Jellyfin — backend, primera etapa

Fecha: 6 de noviembre de 2026.

## Alcance de esta entrega

Esta etapa prepara la negociación de reproducción con Jellyfin y el transporte privado de vídeo para fuentes que Jellyfin declara compatibles con **Direct Play** en el perfil web inicial de VIEWTV.

- `POST /jellyfin/media/{media_id}/playback-info`: exige sesión VIEWTV, resuelve el ID local del catálogo y consulta `POST /Items/{jellyfin_id}/PlaybackInfo` en Jellyfin con un perfil de dispositivo web.
- La respuesta pública se normaliza: no devuelve rutas locales, `DirectStreamUrl`, `TranscodingUrl`, tokens ni la clave API. Solo expone los datos mínimos de las fuentes y una ruta local de reproducción cuando se permite Direct Play.
- `GET /jellyfin/media/{media_id}/stream`: exige sesión VIEWTV, solicita el vídeo a Jellyfin desde el backend y conserva `Range`, `If-Range`, `206 Partial Content`, `Content-Range`, `Accept-Ranges`, `Content-Length`, `ETag` y `Last-Modified` cuando el servidor los proporciona.
- La clave API permanece en la cabecera `Authorization` entre backend y Jellyfin. Nunca se envía al navegador.
- Los IDs de medio se resuelven contra SQLite; no se aceptan URLs, rutas de disco ni hosts proporcionados por el cliente.
- Se rechazan rangos mal formados y respuestas upstream con tipos de contenido que no sean vídeo o `application/octet-stream`.

## Contrato de respuesta

La negociación devuelve `estado`, `play_session_id` y `fuentes`. Cada fuente indica `id`, `contenedor`, `bitrate`, `reproduccion_directa`, `requiere_transcodificacion` y `url`. `url` solo se incluye para Direct Play y apunta al proxy same-origin de VIEWTV.

Si Jellyfin no declara ninguna fuente Direct Play compatible, el estado es `requiere_transcodificacion` y no se genera una URL de vídeo que no pueda funcionar.

## Límites conocidos — no confundir con reproducción completa

Esta entrega **no** completa todavía toda la reproducción de VIEWTV:

1. La PWA aún no contiene el reproductor ni llama a estos endpoints.
2. La ruta de vídeo cubre Direct Play de archivo; aún no implementa remux/Direct Stream ni la ruta HLS de transcodificación. No se debe exponer directamente al navegador la `TranscodingUrl` devuelta por Jellyfin porque puede contener credenciales y porque HLS requiere proxy y reescritura de manifiestos/segmentos.
3. Aún no se envían eventos de inicio, pausa, progreso, finalización ni reanudación a Jellyfin.
4. Aún no se han probado subtítulos, selección de pistas, seek real, compatibilidad de códecs ni Fire TV.

## Pruebas incluidas

Las pruebas con `httpx.MockTransport` comprueban que la negociación POST incluye el perfil de dispositivo, que las URLs/credenciales upstream no se filtran, que el proxy reenvía `Range` e `If-Range`, que conserva respuestas parciales y que rechaza tipos no vídeo.

La validación de integración debe ejecutarse en el equipo del usuario con el vídeo autorizado ya presente en Jellyfin. No se declara superada hasta que el backend se reconstruya, pase pytest/Ruff y una petición real devuelva bytes del vídeo (incluida una respuesta 206 al solicitar un rango).

## Siguiente etapa

1. Validar estos endpoints con el vídeo real en el portátil.
2. Añadir reproducción adaptativa para fuentes no compatibles con Direct Play (HLS/remux/transcodificación), manteniendo el proxy y las credenciales en el backend.
3. Conectar el reproductor HTML5 de la PWA y los controles de mando.
4. Reportar estado/progreso a Jellyfin y probar reanudación, pistas de audio/subtítulos y Fire TV.
