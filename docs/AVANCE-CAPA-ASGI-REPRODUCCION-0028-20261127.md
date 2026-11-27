# VIEWTV 0028 — Capa ASGI de admisión de reproducción, solo en ensayos

**Fecha:** viernes, 27 de noviembre de 2026 (Europe/Madrid).
**Repositorio:** `wizzadrds/viewtv`; rama `viewtv-seguimiento-descargas-0012`.
**PR #2:** OPEN, DRAFT, no fusionado.
**Prioridad:** seguridad de archivos y retirada, luego app Samsung Tizen y después «VIEWTV Momentos».

## Resultado ejecutivo

Se construyó una capa de pruebas **ASGI** que envuelve las rutas FastAPI actuales de VIEWTV, **sin modificar ni registrar el middleware en `backend/app/main.py`**. Es la evolución del laboratorio SQLite temporal 0027: cada petición HTTP de vídeo obtiene un registro durable de laboratorio antes de acceder al handler y lo libera **solo cuando la llamada ASGI ha terminado**, incluido el cuerpo streaming, una cancelación o una excepción.

Cuando se inicia el drenaje de una película, la capa deniega las nuevas peticiones de esa película, incluidas **negociación inicial, streaming directo y todas las playlists, variantes, segmentos y claves HLS que pasan por la misma ruta**. Las películas ajenas siguen siendo accesibles en el ensayo. Los enlaces HLS todavía firmados y con vigencia no dan acceso a una película en drenaje.

**Advertencia:** esta capa se importa exclusivamente por las pruebas automatizadas; no hay gate activado en API/frontend productivos, ni scripts Windows, ni qBit ni Jellyfin. No se ha impedido ningún acceso ni parado reproducción real. **Es imposible inferir de este experimento que se puedan borrar archivos.**

## Antecedentes

- Hito 0027: auditoría estática encontró tres rutas VIEWTV autenticadas: `POST /jellyfin/media/{id}/playback-info`, `GET /jellyfin/media/{id}/stream`, `GET /jellyfin/media/{id}/hls`. El HLS firma capacidades con TTL máximo de **14.400 s (4 horas)**. La publicación del puerto Jellyfin observada en el host está limitada a loopback, no todos sus accesos internos.
- El laboratorio `worker/retirement_playback_admission_0027.py` ya utiliza SQLite privada bajo TEMP con GUID, marca, permisos 0700/0600, `BEGIN IMMEDIATE` y `synchronous=FULL`; conserva sesiones en vuelo después de la caída del proceso para que el drenaje **no quede falsamente libre**.
- Persisten los bloqueos de la solicitud de retirada por película 0024–0026: otro perfil no la ha marcado vista, el torrent permanece activo y tiene archivos adicionales protegidos, sin autorización administrativa por título.

## Cambios realizados

### `backend/app/retirement_http_gate_lab_0028.py` — solo laboratorio

El wrapper `StreamingRouteGuardLab0028`:
1. Requiere explícitamente una instancia real del **laboratorio** `LaboratorioAdmision0027` con DB TEMP; rechaza controladores distintos. No abre la SQLite productiva ni concede permisos reales.
2. Reconoce las tres rutas de reproducción y métodos exactos por nombre. Las rutas de medios desconocidas se **deniegan de manera conservadora**, incluidas variantes no canónicas, métodos inesperados y path codificados; las imágenes verificadas y `/health` permanecen accesibles.
3. Antes de invocar `self.app(scope, receive, send)`, abre una sesión de petición y registra una lectura pendiente en dos transacciones serializadas. Si una retirada de laboratorio empezó antes, devuelve HTTP **423** con una respuesta genérica, no-cache, **sin invocar la ruta ni contactar con Jellyfin**.
4. Si la admisión llegó antes del drenaje, el registro queda contado hasta el `finally` posterior a `await self.app`. El guard conserva la petición mientras la aplicación envía bytes; el drenaje no aparece como libre hasta completar la petición.
5. En error o cancelación, intenta cerrar primero el registro de petición y luego la sesión. **Si el diario SQLite falla**, no elimina a ciegas la fila conservada: el drenaje debe permanecer bloqueado hasta conciliación fuera de banda. Nunca expira ni purga automáticamente.
6. No autentica perfiles ni revoca tokens HLS de forma independiente. La autenticación VIEWTV todavía corre **dentro** del handler FastAPI. Por ello el estado de drenaje (HTTP 423 frente a HTTP 401) podría quedar distinguible por una petición anónima si se desplegara tal cual. **No desplegar** hasta pasar la admisión detrás de la autenticación y ligar tokens a usuario, medio y generación de sesión.

No se han modificado `backend/app/jellyfin_playback.py`, `backend/app/jellyfin_hls.py`, `backend/app/main.py`, frontend, configuración Docker o base productiva. El wrapper no se ejecutará por defecto al reiniciar VIEWTV.

### Ensayos sobre app ASGI sintética y las rutas REALES de FastAPI

`backend/tests/test_stream_guard_asgi_0028.py`:
- Comprueba que antes del drenaje las tres rutas pasan y dejan contadores a cero cuando terminan.
- Inicia drenaje y confirma HTTP 423 **antes del handler** para las tres rutas, mientras `/health`, imágenes y películas distintas siguen accesibles.
- Confirma que rutas futuras o ambiguas, métodos erróneos y codificación alternativa no eluden el guard.
- Mantiene una petición ASGI real **en vuelo** después de emitir headers y un fragmento de vídeo; al iniciar el drenaje no queda libre hasta que se envía el fragmento final.
- Cancela una petición asíncrona y verifica el cierre de los registros del laboratorio.
- Mantiene bloqueada una lectura abandonada a propósito; no libera por timeout ni corrige registros a ciegas.
- Verifica que el wrapper **no está registrado** en la API productiva.

`backend/tests/test_stream_guard_real_routes_0028.py`:
- Monta la app FastAPI REAL `app.main.app` dentro del guard **solo en `TestClient`**. Crea una SQLite efímera en memoria con una película y un perfil **ficticios** mediante sustitución de dependencias de pruebas; restaura todos los overrides al terminar.
- Sustituye el cliente Jellyfin por respuestas `httpx.Response` simuladas y una fuente HLS con playlist + fragmento ficticios. **Ninguna conexión de red ni vídeo real.**
- Antes del drenaje, las rutas reales sirven negociación, bytes de vídeo ficticio, playlist HLS y fragmento; la cuota de peticiones pendientes termina en cero.
- Después del drenaje, **todas** esas mismas rutas devuelven HTTP 423, incluso la playlist y el segmento HLS con su token todavía firmado. Se comprueba que **el contador de llamadas upstream no aumenta**.
- El acceso sin sesión aún obtiene HTTP 401 cuando no hay drenaje: la capa no otorga identidad de VIEWTV, pero tampoco resuelve el posible canal lateral de 423 cuando el drenaje sí está activo.

Se han validado **23/23 pruebas específicas**, sin red, Ruff PASS. **Suite backend completa: 1490/1490 PASS** (dos avisos de deprecación de dependencias externas), ejecutada en el contenedor de pruebas sin red. Smoke web/API **10/10 PASS**. Auditoría NTFS Windows posterior: **2/2 diarios de publicación verificados, 0 bloqueados, 1 carpeta sin diario protegida y 0 borrados reales**. Servicios productivos API/frontend/Jellyfin saludables.

## Seguridad y restricciones para la fase siguiente

Este prototipo no es aún aceptable para usar con medios reales. En particular:

- La barrera se ejecuta **antes de autenticación** en el wrapper genérico. No vincula sesiones ASGI con cookies/perfil Jellyfin, ni mantiene una sesión reproducible entre los segmentos; cada petición es una admisión temporal nueva. Con una futura integración real tendrá que autenticar primero, usar capacidades ligadas a sesión y generación y aplicar la política incluso a tokens HLS emitidos con anterioridad.
- La capa reconoce solo las **tres rutas actuales** y supone que el proxy inverso ha eliminado `/api/viewtv` al llegar al backend. La inspección de rutas no sustituye una auditoría de todos los accesos directos a Jellyfin, redes Docker/host y HLS externos.
- No controla sesiones Jellyfin **que no pasen por VIEWTV**, ni capacidades fuera del proxy, ni procesos que retengan handles NTFS, ni escrituras/siembra de qBittorrent. Tampoco detiene una reproducción en curso ni purga tickets perdidos.
- Cada petición hace dos transacciones SQLite de laboratorio antes del handler. Se deberán evaluar denegación de servicio, control de sesiones con conexiones desconectadas y bloqueo durable entre varias instancias antes de integrar la capa real.
- No coordina con el publicador Windows instalado, que aún no participa en el mutex 0022; no consume tickets administrativos 0019, no ejecuta diario 0020, no libera ni mide bloques de ficheros.
- **Nunca interpretar `listo_para_preflight` como quiescencia física o autorización para retirar**. Es solo el estado de los clientes incorporados al laboratorio.

## Copia previa y operación

Antes de editar los documentos del repositorio se ha generado y verificado:
`/home/viewtv/viewtv-backups/prototipo-asgi-0028-pre-20261127-173506.tar.gz`
SHA-256 `1c90cb0951904a45042800663d9f343df9dca895ef056bf9a8c28987a55c775b`.
`tar -tzf` PASS; contiene exclusivamente código y documentación anteriores. Sin medios, descargas, credenciales, SQL productiva ni archivos de claves.

**Cero borrados de medios; cero torrents modificados; cero migraciones; cero reinicios; cero despliegues.**

## Próximos pasos

1. Diseñar e implementar una admisión **autenticada** dentro de las tres rutas reales, con gestión de sesión/stream HLS por perfil/medio, generaciones y prueba de cierre de todas las respuestas. Mantener el reproductor funcional durante el desarrollo y no desplegar parcialmente.
2. Probar el bloqueo de accesos Jellyfin que se salten el proxy y de lectura de ficheros/handles Windows. No declarar exclusión si falta una vía.
3. Coordinar qBit sin pausarlo ni tocar metadatos ajenos, actualizar publicador con mutex de forma supervisada, exigir firmas admin por película y todas las vistas de perfiles, diario durable y comprobación de espacio físico NTFS.
4. Únicamente tras finalizar esta prioridad, avanzar a app instalable Samsung Tizen; posteriormente VIEWTV Momentos.
