# VIEWTV 0027 — Admisión de reproducción antes de una retirada segura

**Fecha:** viernes 27 de noviembre de 2026, Europa/Madrid.
**Repositorio:** `wizzadrds/viewtv`, rama exclusiva `viewtv-seguimiento-descargas-0012`.
**PR #2:** abierto y en borrador, sin fusionar.

## Resultado

Se ha identificado y probado una solución de **admisión cooperativa para sesiones de vídeo VIEWTV** en un entorno de laboratorio **deliberadamente desconectado de la API productiva**. El motor guarda de forma transaccional sesiones y solicitudes de streaming activas, cierra la admisión al iniciar un drenaje y no marca la película libre hasta que **todas las sesiones y peticiones iniciadas hayan terminado**.

**No se ha desplegado un gate en ninguna ruta real, no se ha deshabilitado Jellyfin ni la reproducción, y no existe un ejecutor de retirada física.** Un estado `listo_para_preflight` solo significa que **el propio laboratorio** no tiene sesiones pendientes; no demuestra ausencia de sesiones Jellyfin externas, lecturas Windows o escrituras qBittorrent.

La solicitud de retirada que ya existía en la biblioteca sigue pendiente de revisión, con dos perfiles activos, uno que la ha marcado como vista, y ninguna autorización administrativa de borrado.

## A. Descubrimiento: existen TRES rutas de reproducción

`backend/app/jellyfin_playback.py` contiene:

1. `POST /jellyfin/media/{media_id}/playback-info`: negocia la reproducción con Jellyfin y emite URL directa o enlace HLS.
2. `GET /jellyfin/media/{media_id}/stream`: realiza solicitudes directas de vídeo, incluso peticiones Range que pueden continuar abiertas.
3. `GET /jellyfin/media/{media_id}/hls`: sirve playlists, variantes, segmentos y claves HLS a partir de tokens firmados. Cada segmento es una solicitud independiente.

Las tres rutas usan una dependencia de autenticación del perfil VIEWTV. `backend/app/jellyfin_hls.py` define `HLS_TTL_SECONDS=4*3600`, es decir, **14.400 segundos (4 horas)** de capacidad HLS por defecto. Por tanto, **negar solo la solicitud `playback-info` no basta**: una sesión ya iniciada podría descargar fragmentos HLS o reabrir rangos de vídeo.

El puerto Docker publicado de Jellyfin se ha observado en `127.0.0.1:8097` para su servicio interno 8096/tcp. Esta exposición **solo loopback** reduce vías directas desde la red por ese puerto, pero **no prueba** que no existan clientes por redes de contenedores, conexiones locales, puentes/redirecciones del host u otras superficies. No se han enumerado usuarios ni cambiado puertos.

`worker/retirement_playback_surface_0027.py` examina sintácticamente el código de las tres rutas, su dependencia de perfil y la constante TTL. `scripts/viewtv_retirada_superficie_reproduccion_0027.py` añade el puerto Docker mediante consulta read-only y publica **solo contadores y hechos de seguridad**, nunca tokens, credenciales, direcciones del usuario ni nombres de archivos.

Resultado real:

```text
SUPERFICIE_PLAYBACK_0027=SOLO_LECTURA
RUTAS_AUTENTICADAS_CONTADAS=3
TTL_HLS_SEGUNDOS=14400
PUERTO_JELLYFIN_PUBLICADO_SOLO_LOOPBACK=SI
OTROS_ACCESOS_JELLYFIN_DESCARTADOS=NO
PROTOCOLO_ADMISION_0027_INSTALADO=NO
BLOQUEO_REAL_DE_NUEVOS_STREAMS=NO
PERMISO_BORRADO_FISICO=NO
SERVICIOS_MODIFICADOS=0
REPRODUCCIONES_MODIFICADAS=0
```

## B. Protocolo de laboratorio para eliminar la carrera entre dos admisiones

`worker/retirement_playback_admission_0027.py` crea un SQLite **solo de prueba** en un directorio nuevo privado `TEMP/viewtv-admission-0027-{GUID}` generado por las pruebas. Requiere propietario actual, marca literal de sandbox, permisos de directorio 0700 y DB 0600, archivo regular con un solo enlace y sin redirecciones. El nombre de DB está fijado; rechaza rutas fuera de TEMP, enlaces adicionales y symlinks.

Los métodos `abrir_sesion`, `iniciar_peticion`, `terminar_peticion`, `cerrar_sesion` e `iniciar_drenaje` usan **transacciones SQLite `BEGIN IMMEDIATE` + `synchronous=FULL`**. Para cada película los estados son:

- `libre`: admite sesiones ficticias autenticadas por token de 24 bytes aleatorios (48 dígitos hexadecimales).
- `drenando`: rechaza **nuevas** sesiones, pero permite terminar solicitudes de vídeo de una sesión abierta antes del cierre. Las peticiones en vuelo permanecen registradas incluso si la sesión dejó de estar abierta.
- `listo_para_preflight`: no quedan sesiones ni peticiones *del laboratorio*. No equivale a permiso de borrar.

La primera operación transaccional entre `abrir_sesion` e `iniciar_drenaje` determina el orden: una apertura ganadora queda contabilizada y deberá cerrarse; un drenaje ganador rechaza la apertura. No existe vencimiento automático ni recogida optimista de sesiones perdidas: una caída del proceso mantiene la sesión registrada y bloquea la decisión hasta conciliación supervisada. Reintentos de tokens o solicitudes ya cerradas se rechazan; otras películas conservan sus sesiones independientes.

**Limitaciones deliberadas:** no se vincula a cookies de perfil, sesiones Jellyfin, al generador de chunks HTTP, al streaming HLS productivo, al frontend Samsung ni a los cierres reales de conexión. Un cliente que acceda directamente a Jellyfin tampoco participa. **Este prototipo no debe usarse para autorizar borrados** aunque todos sus contadores lleguen a cero. No detiene, pausa, reproduce, elimina, mueve ni lee ficheros de vídeo.

## C. Requisitos antes de conectar una barrera real

1. Crear una autoridad de reproducción compartida, duradera y autenticada, con permisos mínimos, que pueda iniciar/cerrar sesiones y mantener registro de solicitudes de streaming efectivas. Mantener separados el PIN de perfil y la aprobación de administrador de biblioteca 0019.
2. Comprobar en **`playback-info` antes de llamar a Jellyfin** que la admisión está abierta y asociar la sesión a una identidad de perfil y medio concreta. Negar nuevas reproducciones durante drenaje, sin interferir con películas ajenas.
3. En la ruta **directa** `stream`, exigir un token de sesión vivo e iniciar una petición en vuelo antes de abrir el upstream; cerrarla **en el `finally` del iterador del cuerpo HTTP**, incluso en cancelación, desconexión o excepciones. No basta con verificar la URL.
4. Para **HLS**, ligar todas las capacidades firmadas a la identidad y generación de la sesión; verificar el estado **en cada playlist, variante, segmento y clave**, sin confiar únicamente en el vencimiento de cuatro horas. Una revocación o cierre de sesión debe invalidar fragmentos posteriores.
5. Manejar caídas sin purga automática: retener estado «drenando» y exigir reconciliación administrativa de sesiones abiertas, tokens viejos, caché de navegador y lecturas de red todavía activas.
6. Antes de declarar quiescencia física, cerrar o aislar **todas** las rutas directas de Jellyfin, confirmar los lectores de Windows y la política de streams, actualizar de forma supervisada el publicador con mutex 0022/0023 y demostrar exclusión con los torrents qBit **sin detenerlos por conveniencia**.
7. Revalidar perfil/solicitud, propiedades, diarios, NTFS y **autorización administrativa concreta de una película**, con journal durable y medición de bytes reales liberados. Ninguna de estas condiciones se deduce de `listo_para_preflight`.

**No añadir un botón «Retirar ahora» ni alterar el comportamiento de reproducción en producción antes de completar todos estos controles.**

## D. Pruebas y estado del sistema

`backend/tests/test_admision_reproduccion_0027.py` prueba sesión, streaming en vuelo, cierre, tokens inválidos, separación entre películas, 16 aperturas en carrera contra el drenaje, persistencia entre procesos cuando una sesión no se cierra, rechazo de hardlinks/symlinks de la DB, permisos privados y ausencia de funciones destructivas.

`backend/tests/test_superficie_reproduccion_0027.py` verifica el inventario de tres rutas y cuatro horas HLS, rechaza rutas o dependencias de perfil eliminadas, TTL inesperado, exposición Docker `0.0.0.0` o informes no confiables. No hace conexiones con Jellyfin ni modifica un contenedor.

- **43/43 pruebas específicas PASS**, Ruff PASS.
- Smoke 0012 read-only de producción **10/10 PASS**.
- Consulta `/Sessions` del guard 0021 reportó **cero sesiones en el instante consultado**, sin bloqueo efectivo de nuevas reproducciones.
- **Suite backend completa 1467/1467 PASS**, con 2 avisos de deprecación en dependencias externas, ejecutada dentro del contenedor de pruebas sin red. Auditoría Windows NTFS final: 2/2 diarios verificados, 0 bloqueados y 1 carpeta sin diario protegida; 0 borrados reales. Ruff PASS de código nuevo.
- Sin migraciones, reinicios, detenciones, emisiones de tickets administrativos ni cambios en qBit, Jellyfin, tareas Windows, medios o base productiva. La única SQLite creada está dentro del TEMP del ensayo y las pruebas limpian sus directorios ficticios.

### Respaldo previo

`/home/viewtv/viewtv-backups/admisiones-reproduccion-0027-pre-20261127-172113.tar.gz`
SHA-256: `58640099e5382d5dede4a86d3caaaf45825cebf4b07fe706efcdb0b29c98a769`.

Verificado con `sha256sum` y `tar -tzf`. Contiene solamente las fuentes existentes de rutas Jellyfin, tests y dos documentos antes del trabajo; no contiene medios, SQLite productiva ni credenciales.

## E. Próxima prioridad

**Falta todavía un despliegue coordinado del control de streams y un mecanismo comprobable de exclusión con qBittorrent/Windows**, sin detener torrents ni expulsar usuarios de manera silenciosa. El proyecto mantiene el orden:

**Liberación segura de espacio → app Samsung Tizen instalable → VIEWTV Momentos.**
