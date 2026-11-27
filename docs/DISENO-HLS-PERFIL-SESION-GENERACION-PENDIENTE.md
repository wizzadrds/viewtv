# Diseño pendiente — HLS ligado a perfil, sesión y generación (futuro hito 2)

**Estado: DISEÑO, NO IMPLEMENTADO NI DESPLEGADO.** No sustituye el laboratorio ASGI 0028/0029, no modifica el JWT ni los segmentos actuales. No se debe avanzar a implementación si permanece algún gate de calidad del 0030 sin resolver.

## Problema constatado

`backend/app/jellyfin_hls.py` firma hoy `{m,p,q,e}` con HMAC y usa TTL máximo de cuatro horas. `verify_hls_token` valida medio, firma, caducidad y ruta, pero no conoce el perfil, la sesión autenticada ni una generación revocable. `rewrite_hls_playlist` reescribe URLs de listas maestras, variantes, segmentos y atributos `URI` y `local_hls_url` firma cada una. El laboratorio 0029 demostró transferencia entre perfiles; está fuera de `app.main`.

## Diseño de contrato propuesto

1. Autenticación de perfil **antes de consultar el estado del medio** con `get_current_profile` real. Vincular una sesión de reproducción emitida por el servidor (identificador aleatorio no elegible por el navegador) a `perfil_id`, `medio_id`, sesión autenticada y `generation` persistida en SQLite. Un token de perfil no es una autorización administrativa.
2. Nueva capacidad HLS con versión estricta `v=2` y campos obligatorios y tipados `media_id`, `upstream_path`, `safe_query`, `expires_at`, `profile_id`, `play_session_id`, `generation` y, si se necesita, identificador anti-repetición. Firmar con HMAC-SHA256 y comparar en tiempo constante; canonizar la ruta antes de firmar y comprobarla otra vez al leer. Rechazar duplicados, campos desconocidos, valores ambiguos, tokens antiguos `v1`, firma ausente y caducidad. Mantener clave solo en backend, sin claves Jellyfin en URL.
3. Cada petición de `/jellyfin/media/{id}/hls` deberá contrastar **perfil autenticado + sesión activa + generación actual + medio + expiración** en un único control de acceso antes de abrir Jellyfin, aunque se solicite directamente un `.ts`, `.m4s`, `.key`, variante o lista hija. Las reproducciones directas, reintentos `Range` y redirecciones también participan del gate; sin excepciones por tipo MIME.
4. Al emitir la master, propagar **la misma sesión y generación** cuando se reescriban variantes y cada segmento; no abrir una nueva sesión por fragmento. Drenaje: transacción que primero marca `draining`, incrementa generación o revoca los tokens previos y deniega nuevas lecturas; sesiones/lecturas previas cuentan hasta terminar sus cuerpos reales. La generación debe sobrevivir reinicios y evitar respuestas cacheadas, races entre validación/apertura y revocación.
5. Migración coordinada con la API y los clientes web/Samsung: ventana de cambio controlada, sin aceptar `v1` para medios en drenaje y **sin compatibilidad silenciosa** que mantenga tokens transferibles; pruebas reales en reproductor y códec antes de desplegar. Respuestas 401/423/404 sin filtrar si un título está en retirada y `Cache-Control: private, no-store`.

## Pruebas obligatorias que faltan

| Caso | Resultado esperado |
| --- | --- |
| Perfil A emite URL y perfil B la reutiliza | Denegación antes de petición upstream |
| Misma cuenta/perfil, sesión B usa token de sesión A | Denegación si no coincide sesión autenticada |
| Token caducado, manipulado, v1 o de otro medio | Denegación sin revelar datos |
| Inicio de drenaje después de emitir URL | Token anterior revocado para master, variante y segmentos |
| Acceso directo a segmento o clave sin visitar master | Denegación, sin transcodificación |
| Playlist con `URI` incrustada, URLs relativas, ruta de salto o sitio externo | Reescritura segura o rechazo cerrado |
| Varios perfiles con streams en curso, interrupción/reinicio y respuesta parcial | Recuento durable, ninguna retirada prematura |
| Cliente Samsung y navegador, HLS normal y reintentos | Reproducción confirmada físicamente, no solo HTTP 200 |

**No desplegado**, **0 tokens nuevos emitidos**, **0 películas liberadas**, **ninguna retirada autorizada**.
