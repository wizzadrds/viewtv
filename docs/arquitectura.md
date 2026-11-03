# Arquitectura inicial

## Límites entre componentes

- **Web (Next.js):** presenta la experiencia de usuario. No accede directamente a SQLite, Jellyfin ni a secretos del servidor.
- **API (FastAPI):** valida las peticiones, aplica autenticación y autorización, y es la única puerta de entrada de la interfaz a los datos de VIEWTV.
- **SQLite:** conserva perfiles, metadatos, solicitudes y estado de trabajos. Su ubicación es persistente y separada del almacenamiento temporal.
- **Worker:** procesa trabajos fuera del ciclo de petición HTTP. La cola debe sobrevivir a reinicios.
- **Jellyfin:** sistema externo responsable de la biblioteca y de la reproducción. VIEWTV consumirá su API con credenciales guardadas solo en el servidor.

## Persistencia frente a caché

La base de datos y cualquier dato necesario para reconstruir el estado de la aplicación deben residir en un volumen persistente. Los ficheros de vídeo descargados o almacenados temporalmente pertenecen a la caché y pueden eliminarse según las reglas de cuota y caducidad.

Cuota inicial de caché: **80 GB**. Debe ser configurable y nunca debe provocar la eliminación de la base de datos, perfiles o metadatos persistentes.

## Cola y leases

La cola será durable en SQLite. Un trabajador reclamará un trabajo mediante una concesión temporal (lease) con vencimiento y heartbeat. La configuración inicial prevista es:

- Duración de lease: 120 segundos.
- Renovación del heartbeat: cada 30 segundos.
- Los trabajos cuyo lease expire podrán recuperarse tras una caída del worker.
- Los reintentos utilizarán backoff y un estado visible para el usuario.

La reclamación y actualización del lease deberán implementarse con operaciones transaccionales para evitar que dos workers procesen simultáneamente el mismo trabajo.

## Seguridad

- Contraseñas y PIN nunca se almacenan en claro; se utilizará hashing adecuado.
- Los tokens de sesión se entregan mediante cookies HttpOnly y configuración segura según el entorno.
- Se aplicarán límites de frecuencia a los endpoints sensibles.
- Las claves API de integraciones solo existen en el backend/worker.
- La configuración predeterminada es LAN; no se expondrá el servicio a Internet.
- Los secretos reales no se versionan.

## Integraciones

Jellyfin será la fuente de reproducción y biblioteca. TMDB podrá aportar metadatos. Los adaptadores de indexadores y cliente de torrents, si se habilitan, se limitarán a contenido propio, autorizado o de dominio público.

## Almacenamiento del entorno actual

En el equipo de desarrollo Windows 11 + WSL2, el SSD es la unidad `C:`. Las carpetas anfitrionas creadas son `C:\\VIEWTV\\media`, `C:\\VIEWTV\\cache`, `C:\\VIEWTV\\data` y `C:\\VIEWTV\\backups` (accesibles desde WSL como `/mnt/c/VIEWTV/...`).

- `api` y `worker` montan `/mnt/c/VIEWTV/cache` en `/cache`; la escritura se ha probado desde ambos contenedores.
- SQLite permanece en el volumen Docker `viewtv_data` montado en `/data`. No mover ni borrar este volumen al cambiar la caché.
- `media` queda reservado para compartir contenido con Jellyfin nativo de Windows. La conexión y los permisos se configurarán al crear las bibliotecas.
- `data` y `backups` están creados, pero todavía no están montados en los contenedores.

## Entorno de desarrollo

El objetivo inicial es Windows 11 + WSL2 (Ubuntu 24.04) + Docker Desktop. Se recomienda clonar y ejecutar el proyecto desde el sistema de archivos Linux de WSL. La aceleración Intel Quick Sync se investigará más adelante y no se dará por disponible hasta verificar el hardware, los controladores y el acceso desde contenedores.
