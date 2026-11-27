# VIEWTV 0029 — Identidad de perfil antes del drenaje, solo en tests

**Fecha:** viernes 27 de noviembre de 2026 (Europe/Madrid).
**Repo:** `wizzadrds/viewtv`; rama exclusiva `viewtv-seguimiento-descargas-0012`.
**PR #2:** OPEN/DRAFT, sin merge.
**Alcance:** módulo opcional de **laboratorio**, no instalado en la API activa.

## Qué hemos logrado

El laboratorio HTTP 0028 era capaz de impedir nuevas reproducciones durante el drenaje, pero actuaba **antes** de ejecutar la autenticación FastAPI. Un visitante no identificado podía distinguir HTTP 423 (película en revisión) de 401 (sin sesión): era un canal lateral de estado, por lo que **no podía instalarse en producción**.

En 0029 se añade un segundo wrapper ASGI de pruebas que invoca **la validación real de autenticación de VIEWTV**, `app.auth.get_current_profile`, antes de consultar la SQLite del drenaje y antes de mirar si el path de medios es reconocible. Esa función exige cookie JWT válida, firma HS256, `sub`, `iat`, `exp`, perfil existente y `activo=true`.

**Prueba:** con perfiles y JWT puramente ficticios, peticiones anónimas, vencidas, alteradas o de perfiles desactivados reciben **401 antes y después de empezar el drenaje**, incluso para URLs HLS. Una identidad activa obtiene acceso cuando el laboratorio está `libre` y HTTP **423** cuando ese medio entra en drenaje. Las peticiones denegadas **no llegan al cliente Jellyfin simulado**.

Se mantiene la seguridad principal: **ninguno de estos resultados concede permiso de borrar una película**.

## Código nuevo, sin cambiar los handlers existentes

### `worker/retirement_profile_admission_0029.py`

- `AdmisionPerfilLab0029` es una extensión estrictamente local del laboratorio SQLite TEMP GUID 0027.
- Una transacción SQLite `BEGIN IMMEDIATE` inserta simultáneamente el registro de sesión y una **vinculación inmutable al identificador del perfil**, sin ventana de sesión visible aún sin propietario.
- `empezar_lectura`, `terminar_lectura` y `cerrar_para_perfil` contrastan **medio, perfil y token de sesión** bajo bloqueo SQLite; otro perfil no puede aprovechar el token para entrar, consumir ni cerrar una lectura ajena.
- Sesiones cerradas siguen contabilizadas si tienen lecturas/streams en vuelo. La pérdida de una sesión conserva la fila sin vencimiento automático; el drenaje permanece bloqueado hasta reconciliación del caso.
- Salida **solo agregada**: recuento de sesiones y lecturas; nunca tokens, identidad de perfil, títulos ni rutas; `autoriza_borrado_fisico=false` incondicional.

### `backend/app/retirement_authenticated_gate_lab_0029.py`

- `VerificadorPerfilLab0029` recibe obligatoriamente una fábrica de SQLite **de pruebas** y llama a `get_current_profile(Request(scope), session)` real; no implementa una validación de JWT paralela ni permite aceptar un ID arbitrario como supuesta identidad.
- `AuthenticatedPlaybackGateLab0029` acepta únicamente `AdmisionPerfilLab0029` y ese verificador. Evalúa primero la identidad:
  - Sin cookie, cookie inválida, caducada o perfil inactivo → **401**, independientemente del drenaje.
  - Falla inesperada de la base de perfiles → **503** genérico, sin usar el estado de la película ni imprimir errores.
  - Ruta de medios no reconocida con perfil validado → **404**; nunca se sirve una ruta de vídeo nueva sin inventariarla.
  - Medio en drenaje con perfil validado → **423**, antes de abrir el vídeo.
  - Medio libre → registra sesión con perfil y lectura antes de llamar a FastAPI; la lectura sigue contabilizada hasta que termina **todo el cuerpo de respuesta ASGI**.
- Seguirán funcionando las rutas de salud/imágenes ajenas al gate. Cada respuesta denegada envía `Cache-Control: private, no-store`.
- La clase **no está importada, incluida ni registrada en `backend/app/main.py`**; no puede ejecutarse en el servidor activo sin una integración nueva y explícita.

## Pruebas específicas

`backend/tests/test_admision_perfil_0029.py`:

- Un perfil no puede iniciar, terminar o cerrar la lectura/sesión abierta por otro, ni cambiar su media ID.
- Dos perfiles pueden reproducir la misma película antes del drenaje, pero ambos son rechazados después; el drenaje espera a que terminen las sesiones previas.
- Una lectura que queda abierta tras reiniciar un objeto laboratorio sigue bloqueando; nunca se libera por caducidad optimista.
- IDs de perfil inválidos, tipos ambiguos, repetición de tokens y acceso fuera del sandbox fallan cerrado; los informes no incluyen identificadores personales.

`backend/tests/test_auth_before_drain_0029.py`:

- App **real** FastAPI `app.main.app` envuelta solo con `TestClient`. Perfil activo/inactivo, película y tokens JWT se crean en **SQLite en memoria** con claves exclusivamente ficticias.
- `app.auth.get_current_profile` es real; se sustituye `get_settings` por una configuración aislada de prueba, y el acceso Jellyfin por respuestas `httpx.Response` simuladas sin red.
- Peticiones sin cookie, JWT caducado/alterado o perfil inactivo reciben siempre 401 **antes** de leer el estado de drenaje (incluidas rutas futuras y antiguas).
- Perfil activo reproduce negociación, streaming directo y una playlist y segmento HLS ficticios; después del drenaje las mismas solicitudes quedan en 423 **sin llamar al upstream**.
- En fallos de la SQLite de autenticación se devuelve 503 genérico y no se expone la excepción ni contenido confidencial; la capa no está en los middlewares productivos.

## Limitación comprobada explícitamente: HLS todavía no pertenece a un perfil

**Hallazgo de seguridad abierto:** las URLs HLS firmadas por `app.jellyfin_hls.sign_hls_url` contienen identificador de media, ruta segura y caducidad, **pero no perfil ni sesión/generación de reproducción**. En las pruebas se demostró que un enlace todavía vigente emitido para una película puede ser consumido por **dos perfiles activos distintos** si ambos disponen del enlace y una cookie válida.

El nuevo gate impide el acceso de ambos perfiles durante un drenaje, pero **no hace que el propio enlace sea intransferible entre perfiles**. No se ha cambiado el formato de tokens productivos, la clave de firma ni las rutas, para evitar romper reproducción real antes de contar con un diseño completo. Esta limitación tiene que resolverse con capacidades ligadas al perfil y generación de sesión, comprobadas en cada playlist, variante, segmento y clave; habrá que diseñar migración/revocación de tokens antiguos, tiempos de streaming y recuperación.

## Otras condiciones pendientes

- No hay exclusión verificada de clientes que entren a Jellyfin **por fuera de VIEWTV**, ni bloqueo transaccional de escrituras y seeding qBittorrent, ni protección completa de handles NTFS de Windows.
- La tarea del publicador Windows sigue con el código anterior al mutex 0022 y no puede actualizarse automáticamente; requiere ventana supervisada y autorización del administrador.
- La solicitud de retirada de una película de la biblioteca sigue **pendiente**, otro perfil no la marcó vista, el torrent sigue activo y los metadatos adicionales qBit permanecen protegidos. Las marcas y la solicitud no se han alterado.
- El laboratorio autoriza **cero** eliminaciones reales. El proceso de aprobación administrativa por título de 0019 no tiene ninguna clave productiva instalada. No existe un journal de retirada física autorizado ni medición de bloques recuperados.
- **Los prototipos 0027, 0028 y 0029 no se deben desplegar parcialmente** ni presentar como un sistema de bloqueo físico completo.

## Backup y validación

Respaldo **previo al trabajo** de código anterior y documentos:
`/home/viewtv/viewtv-backups/perfil-admision-0029-pre-20261127-175935.tar.gz`

SHA-256: `399fb9ed66e5d3eb04aabaad3f042ee8a568f4e43c9f036294bce3ff02d11f68`; `tar -tzf` comprobado. Solo código y documentación, sin datos de perfil, bases productivas, claves ni medios.

**38/38 pruebas específicas PASS**, Ruff PASS. **Suite backend completa 1528/1528 PASS**, dos avisos de deprecación de dependencias externas. Smoke web/API **10/10 PASS**. La revisión real mantiene una solicitud pendiente, un perfil sin marcar vista y cero permisos de borrado; qBit mantiene dos torrents no en reposo y cuatro extras protegidos. Sin migraciones, despliegues ni cambios de medios o servicios.

## Siguiente hito

Diseñar capacidad HLS firmada que incorpore **perfil y generación de sesión**, comprobarla en cada tipo de fragmento y revocar URLs anteriores sin interrumpir la reproducción real; después, evaluar la integración autenticada y el aislamiento efectivo Jellyfin/qBit/Windows en mantenimiento autorizado. Solo después abordar la eliminación física concreta con firma de administrador y verificación NTFS.

**Prioridades:** espacio y retirada segura → aplicación Samsung Tizen instalable → VIEWTV Momentos.
