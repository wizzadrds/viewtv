
# Estado del proyecto VIEWTV

**Fecha de actualización:** 15 de noviembre de 2026
**Rama de referencia:** `inventario-trabajo-local`
**Último commit revisado:** `f050115`

Este documento resume el estado conocido del proyecto VIEWTV en la rama de trabajo. Para conocer las decisiones técnicas y el contexto completo, consultar `docs/CONTEXTO.md`.

## Resumen

VIEWTV es una aplicación doméstica autohospedada orientada a descubrir y solicitar contenido multimedia desde una interfaz adaptada a televisión, con Jellyfin como servidor multimedia.

El proyecto ya dispone de una base funcional de backend, persistencia, cola de trabajos, worker independiente, frontend y configuración de servicios.

- **Fase 1: cerrada.**
- **Fase 2: en curso.**
- **Entregables 1 a 4 de fase 2: cerrados.**
- **Siguiente entregable: procesador del worker.**

El estado descrito aquí corresponde a la rama local `inventario-trabajo-local`. En la fecha de actualización contiene seis commits que todavía no están en su rama remota correspondiente.

## Estado de las fases

### Fase 1 — Base de la aplicación

**Estado: cerrada.**

La fase estableció la infraestructura y los fundamentos necesarios para continuar el desarrollo:

- Servicios y entorno de desarrollo con Docker Compose.
- Backend basado en FastAPI y SQLModel.
- Persistencia SQLite y migraciones con Alembic.
- Cola durable de trabajos y reclamación transaccional.
- Infraestructura de worker independiente; el procesamiento del flujo real de descargas corresponde al entregable 5 de fase 2.
- Estructura de frontend.
- Pruebas automatizadas y herramientas de calidad.
- Makefile de desarrollo y licencia del proyecto.

El cierre de esta fase está documentado en el historial del proyecto. No debe reabrirse por la existencia de documentos de inventario antiguos.

### Fase 2 — Primera descarga real controlada

**Estado: en curso.**

El objetivo es completar el recorrido desde una solicitud autenticada hasta la gestión controlada de una descarga, respetando las fuentes autorizadas y manteniendo la persistencia del estado.

| Entregable | Descripción | Estado |
|---|---|---|
| 1 | Configuración de servicios de descarga | Cerrado |
| 2 | Clientes HTTP de Jackett y qBittorrent | Cerrado |
| 3 | Modelo de descarga y migración | Cerrado |
| 4 | Endpoint autenticado para crear solicitudes | Cerrado |
| 5 | Procesador del worker | Pendiente |
| 6 | Búsqueda y selección de resultados | Pendiente |
| 7 | Envío y seguimiento en qBittorrent | Pendiente |
| 8 | Pruebas de resiliencia | Pendiente |

El seguimiento detallado, los contratos técnicos y los criterios de aceptación están en `docs/FASE-2.md`.

## Avances confirmados en la rama de trabajo

Los seis commits locales posteriores a la referencia remota son:

| Commit | Descripción |
|---|---|
| `e3b4676` | Configurar servicios de descarga |
| `c51f3b7` | Añadir clientes HTTP de Jackett y qBittorrent |
| `ad2add4` | Documentar avance de fase 2 |
| `dfb00f7` | Añadir modelo y migración de descargas |
| `59e4d5e` | Documentar cierre del modelo de descargas |
| `f050115` | Añadir endpoint autenticado de solicitudes |

### Configuración e integraciones

- Configuración de Jackett y qBittorrent para el entorno de desarrollo.
- Cliente HTTP independiente para Jackett mediante Torznab.
- Cliente HTTP independiente para qBittorrent.
- La integración prevista utiliza Jackett; no requiere Prowlarr.
- No se contempla el análisis de páginas HTML.

### Persistencia de descargas

- Modelo `Descarga`.
- Migración Alembic `0004`.
- Estados de descarga definidos.
- Persistencia de hash, título, indexador, progreso, tamaño, errores y marcas temporales.
- Índice parcial único para evitar duplicados por `info_hash`.

### Solicitudes autenticadas

Se ha incorporado `POST /solicitudes`:

- El perfil se obtiene de la sesión autenticada.
- Se comprueba que el medio existe en Jellyfin.
- Se evita duplicar solicitudes activas.
- La operación utiliza una transacción `BEGIN IMMEDIATE`.
- Se contemplan respuestas para medios inexistentes, conflictos y solicitudes inválidas.
- Se permite volver a solicitar un medio cuando la solicitud anterior ha fallado.

La validación documentada para el entregable 4 incluye 73 pruebas de backend superadas, Ruff correcto y `git diff --check` correcto. Esta cifra corresponde a esa validación, no necesariamente al total actual de pruebas del proyecto. No se considera acreditada una prueba específica de concurrencia HTTP.

## Siguiente trabajo

El siguiente paso aprobado es el **entregable 5: procesador del worker**.

Antes de modificar código:

1. Inspeccionar el worker actual y sus responsabilidades.
2. Revisar la interacción con la cola y el modelo `Descarga`.
3. Acordar el diseño técnico del procesador.
4. Implementar únicamente el alcance de este entregable.
5. Añadir las pruebas correspondientes y documentar su cierre.

No adelantar los entregables 6, 7 u 8 sin cerrar previamente el diseño y el trabajo del entregable 5.

## Decisiones y restricciones vigentes

- Intel Quick Sync (QSV) como tecnología de aceleración de vídeo; no NVENC.
- Jackett como integración de búsqueda para esta fase.
- Cliente Torznab genérico, sin parseo HTML.
- Utilizar únicamente fuentes de contenido cuya autorización esté acreditada.
- No incluir credenciales, tokens, archivos `.env` ni bases de datos locales en Git.
- No modificar la interfaz visual, portadas o estilos sin autorización expresa.

Las decisiones arquitectónicas y sus justificaciones se mantienen en los documentos de contexto y ADR.

## Documentación del proyecto

| Documento | Responsabilidad |
|---|---|
| `README.md` | Presentación del proyecto, puesta en marcha y enlaces principales |
| `docs/ESTADO.md` | Resumen del estado actual y próximos pasos |
| `docs/CONTEXTO.md` | Contexto de traspaso, decisiones y seguimiento general |
| `docs/FASE-2.md` | Alcance, contratos y seguimiento de los entregables de fase 2 |
| `docs/arquitectura.md` | Arquitectura y límites entre componentes |
| `docs/plan-operativo.md` | Planificación y decisiones operativas |
| `docs/backup-operativo.md` | Copias de seguridad y recuperación |
| `docs/reproduccion-jellyfin.md` | Integración y reproducción mediante Jellyfin |
| `docs/especificacion-y-estado.md` | Especificación funcional e historial de planificación |
| `docs/REVISION-IMPLEMENTACION.md` | Registro histórico de revisiones de implementación |
| `docs/adr/` | Decisiones de arquitectura aceptadas |

Los documentos históricos se conservan para trazabilidad. Si un diagnóstico antiguo contradice una implementación posterior, prevalece el estado confirmado más reciente y debe indicarse expresamente en el documento histórico.

## Estado Git de referencia

En la revisión del 15 de noviembre de 2026:

- Rama activa: `inventario-trabajo-local`.
- Rama remota de seguimiento: `origin/inventario-trabajo-local`.
- Diferencia: seis commits locales por delante.
- Árbol de trabajo: limpio en la revisión previa a la edición de este documento.
- Último commit local revisado: `f050115`.

Este estado Git debe actualizarse cuando se publique la rama o se incorporen nuevos cambios.

---

**Regla de mantenimiento:** actualizar este documento al cerrar entregables o fases, y mantenerlo como resumen breve. Los detalles de implementación deben permanecer en sus documentos especializados.
