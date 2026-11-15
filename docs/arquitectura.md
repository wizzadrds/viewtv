# Arquitectura de VIEWTV

**Última revisión:** 15 de noviembre de 2026
**Rama de referencia:** `inventario-trabajo-local`

Este documento describe los límites entre componentes, la persistencia, la seguridad y las integraciones de VIEWTV. Para el estado de implementación y los entregables pendientes, consultar `docs/ESTADO.md` y `docs/FASE-2.md`.

## 1. Límites entre componentes

- **Web (Next.js):** presenta la experiencia de usuario. No accede directamente a SQLite, Jellyfin ni a secretos del servidor.
- **API (FastAPI):** valida peticiones, aplica autenticación y autorización y constituye la puerta de entrada de la interfaz a los datos de VIEWTV.
- **SQLite:** conserva perfiles, metadatos, solicitudes, descargas y estado de trabajos. Su almacenamiento es persistente y está separado del almacenamiento temporal.
- **Worker:** ejecuta trabajos fuera del ciclo de petición HTTP. La cola debe sobrevivir a reinicios y permitir recuperar tareas abandonadas.
- **Jellyfin:** servicio externo responsable de la biblioteca y reproducción. VIEWTV consume su API mediante credenciales guardadas únicamente en el servidor.
- **Jackett:** servicio de consulta de fuentes mediante Torznab. VIEWTV lo consumirá desde el backend, exclusivamente para fuentes y contenido autorizados.
- **qBittorrent:** cliente de transferencias integrado mediante un cliente HTTP desde el backend, cuando exista una fuente autorizada y se habilite el flujo correspondiente.
- **TMDB:** proveedor externo opcional de metadatos y atribución.

La existencia de un cliente de integración no significa que el flujo funcional completo esté implementado.

## 2. Persistencia y almacenamiento temporal

La base de datos y los datos necesarios para reconstruir el estado de la aplicación deben residir en almacenamiento persistente.

Los archivos de vídeo temporales pertenecen a la caché y podrán eliminarse de acuerdo con las reglas de cuota, caducidad y protección de elementos activos.

Cuota inicial prevista para caché: **80 GB**. Debe ser configurable y nunca debe provocar la eliminación de la base de datos, perfiles, solicitudes ni metadatos persistentes.

La política futura de almacenamiento contempla:

- Protección de archivos en reproducción y transferencias activas.
- Elementos fijados excluidos de la expulsión automática.
- Expulsión LRU de elementos vistos y no fijados cuando se supere el umbral configurado.
- Separación estricta entre datos persistentes, archivos multimedia y copias de seguridad.

La implementación de cuotas y expulsión debe comprobarse por separado; no se considera terminada por estar definida en este documento.

## 3. Cola durable y procesamiento

La cola reside en SQLite, no en memoria del proceso.

El diseño contempla:

- Reclamación exclusiva de trabajos mediante transacciones.
- Lease inicial previsto de 120 segundos.
- Renovación del heartbeat cada 30 segundos.
- Recuperación de trabajos cuyo lease haya caducado.
- Backoff exponencial para reintentos.
- Estado visible cuando una tarea agote los intentos.
- Reconciliación con qBittorrent cuando la integración de transferencias esté operativa.

Las operaciones de reclamación, renovación y finalización deben impedir que dos workers procesen simultáneamente el mismo trabajo.

La infraestructura de worker existente no debe confundirse con el procesador real de solicitudes. El procesador constituye el siguiente entregable de fase 2 y su diseño debe revisarse antes de modificar código.

No se debe asumir que APScheduler es un requisito definitivo del procesador ni que su presencia demuestra que las tareas de descarga ya se ejecutan.

## 4. Seguridad

- Los PIN y contraseñas nunca se almacenan en claro; se utiliza hashing adecuado.
- Los tokens de sesión se entregan mediante cookies HttpOnly y configuración segura según el entorno.
- Los endpoints sensibles deben disponer de límites de frecuencia.
- Las claves API de Jellyfin, Jackett y qBittorrent permanecen exclusivamente en la configuración del servidor.
- La configuración de red inicial es doméstica/LAN. No se expondrán servicios directamente a Internet.
- Los secretos reales no se versionan ni se incluyen en documentación, logs o pruebas compartidas.
- La PWA no recibe credenciales de servicios externos ni se conecta directamente a ellos.
- Las fuentes consultadas deben estar autorizadas para el contenido solicitado.

## 5. Integraciones

### 5.1 Jellyfin

Jellyfin es el sistema externo responsable de la biblioteca y reproducción.

VIEWTV utiliza su API para consultar información del catálogo y, cuando corresponda, sincronizar metadatos. Las credenciales se guardan únicamente en el servidor.

La sincronización debe preservar la separación entre los registros de catálogo de VIEWTV y los archivos multimedia gestionados por Jellyfin.

### 5.2 TMDB

TMDB podrá aportar metadatos complementarios, con atribución y respeto a sus condiciones de uso.

Debe evitarse duplicar información sin una política clara de precedencia entre fuentes.

### 5.3 Jackett y Torznab

La integración acordada utiliza Jackett mediante un adaptador Torznab genérico.

- El backend y el worker consultan el adaptador.
- La PWA no accede directamente a Jackett ni recibe sus credenciales.
- Las respuestas se procesan como XML estructurado conforme a Torznab.
- No se implementará parseo HTML ni automatización de páginas web.
- Las URL, rutas y credenciales serán configuración del servidor.
- Los indexers deben comprobarse en la instancia real y utilizarse solo cuando su autorización y alcance estén acreditados.
- La compatibilidad Torznab no demuestra por sí sola que una fuente sea legal, fiable o adecuada.

Prowlarr no forma parte de la decisión vigente de integración.

### 5.4 qBittorrent

La comunicación se realiza mediante el cliente HTTP del backend.

La existencia del cliente no implica que las transferencias estén ya integradas en el procesamiento de solicitudes. El envío, seguimiento, reconciliación y recuperación forman parte de los entregables posteriores de fase 2.

Solo se utilizará con fuentes y contenido autorizados.

## 6. Almacenamiento del entorno

El entorno documentado es Windows 11 + WSL2 Ubuntu 24.04 + Docker Desktop.

Las carpetas anfitrionas creadas inicialmente son:

- `C:\VIEWTV\media`
- `C:\VIEWTV\cache`
- `C:\VIEWTV\data`
- `C:\VIEWTV\backups`

Desde WSL se accede a ellas mediante `/mnt/c/VIEWTV/...`.

El historial de configuración recoge:

- `api` y `worker` comparten un montaje de caché en `/cache`.
- SQLite reside en un volumen Docker persistente montado en `/data`.
- La base de datos no debe moverse ni eliminarse al cambiar la ubicación de la caché.
- `media` está reservado para compartir contenido con Jellyfin nativo de Windows; las rutas y permisos efectivos deben comprobarse antes de habilitar transferencias.
- El procedimiento de backup monta el directorio anfitrión de copias en `/backups` dentro del contenedor API.
- Los montajes efectivos deben verificarse con Docker Compose y `docker inspect` antes de realizar operaciones de mantenimiento.

Los nombres de los volúmenes Docker pueden variar según el proyecto y la configuración de Compose. No se debe asumir un nombre fijo sin comprobarlo.

## 7. Entorno y aceleración de vídeo

- Sistema anfitrión: Windows 11.
- Entorno Linux: WSL2 con Ubuntu 24.04.
- Contenedores: Docker Desktop y Docker Compose.
- Se recomienda mantener el repositorio en el sistema de archivos Linux de WSL.
- La decisión de aceleración de vídeo es Intel Quick Sync (QSV), no NVIDIA NVENC.

La disponibilidad efectiva de QSV depende del hardware, los controladores, los dispositivos expuestos a los contenedores y la configuración de Jellyfin. No se debe dar por validada hasta realizar una prueba real.

## 8. Referencias técnicas oficiales

Consultar versiones compatibles con las dependencias declaradas en el proyecto.

### Backend y persistencia

- [FastAPI](https://fastapi.tiangolo.com/): API HTTP, dependencias y pruebas.
- [SQLModel](https://sqlmodel.tiangolo.com/): modelos y acceso a datos.
- [SQLAlchemy](https://docs.sqlalchemy.org/): sesiones, transacciones y operaciones SQLite.
- [SQLite](https://www.sqlite.org/docs.html): motor de base de datos y concurrencia.
- [Alembic](https://alembic.sqlalchemy.org/en/latest/): migraciones del esquema.
- [APScheduler 3.x](https://apscheduler.readthedocs.io/en/3.x/): referencia de planificación si se utiliza en el worker; no implica que el procesador esté implementado.
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/): configuración y variables de entorno.
- [PyJWT](https://pyjwt.readthedocs.io/): gestión de tokens JWT.
- [argon2-cffi](https://argon2-cffi.readthedocs.io/): hashing de PIN y credenciales.

### Frontend y contenedores

- [Next.js](https://nextjs.org/docs): aplicación web y PWA.
- [React](https://react.dev/learn): componentes e interfaz.
- [Docker Compose](https://docs.docker.com/compose/): definición y ejecución de servicios.

### Servicios e integraciones

- [Jellyfin API](https://api.jellyfin.org/): biblioteca, metadatos e información de reproducción.
- [TMDB API](https://developer.themoviedb.org/docs): consulta y enriquecimiento de metadatos.
- [Jackett](https://github.com/Jackett/Jackett): servicio de indexadores y API Torznab.
- [Torznab](https://torznab.github.io/spec-1.3-draft/): especificación de respuestas estructuradas.
- [qBittorrent Web API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)): comunicación con el cliente de transferencias.

### Calidad y mantenimiento

- [Ruff](https://docs.astral.sh/ruff/): análisis estático y formato de Python.
- [pytest](https://docs.pytest.org/): pruebas automatizadas.
- [ESLint](https://eslint.org/docs/latest/): análisis estático del frontend.
- [TypeScript](https://www.typescriptlang.org/docs/): comprobación de tipos.

## 9. Documentos relacionados

- `docs/ESTADO.md`: estado actual, rama, entregables y próximo paso.
- `docs/FASE-2.md`: alcance y validaciones de fase 2.
- `docs/CONTEXTO.md`: contexto técnico, decisiones y reglas de trabajo.
- `docs/REVISION-IMPLEMENTACION.md`: revisión técnica e historial de diagnóstico.
- `docs/plan-operativo.md`: entorno, persistencia, copias de seguridad y operaciones.
- `docs/especificacion-y-estado.md`: visión funcional e historial resumido.

## 10. Reglas de mantenimiento

- Mantener aquí los límites entre componentes y las decisiones arquitectónicas.
- No duplicar el estado de entregables, commits o pruebas; utilizar los documentos de referencia.
- Actualizar este documento cuando cambie una decisión de arquitectura.
- Distinguir siempre diseño previsto de implementación comprobada.
- No documentar fuentes no verificadas ni contenido sin autorización.
- No incluir secretos, claves API, tokens, cookies, bases de datos locales ni archivos de configuración privados.
- No modificar estilos, portadas ni componentes visuales del frontend como parte de una tarea documental.
