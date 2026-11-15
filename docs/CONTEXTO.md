# VIEWTV — Contexto del proyecto

**Última actualización:** 15 de noviembre de 2026
**Rama de trabajo:** `inventario-trabajo-local`
**Último commit de código revisado:** `f050115`
**Estado:** fase 1 cerrada; fase 2 en curso.

Este documento recoge el contexto general, las decisiones técnicas y los criterios de trabajo de VIEWTV. Es una referencia para continuar el desarrollo sin reabrir decisiones ya aprobadas ni confundir funcionalidades previstas con funcionalidades implementadas.

---

## 1. Objetivo del proyecto

VIEWTV es una aplicación doméstica para organizar y reproducir contenido multimedia desde una interfaz web instalable (PWA), utilizando Jellyfin como servidor multimedia.

El proyecto contempla dos perfiles domésticos con acceso protegido mediante PIN y una experiencia orientada principalmente a Android TV y Fire TV.

La evolución prevista incluye un flujo controlado de solicitudes y descargas: el usuario solicita contenido, el sistema consulta fuentes autorizadas, permite seleccionar un resultado y gestiona la descarga mediante qBittorrent. La disponibilidad final del contenido se comprueba a través de Jellyfin.

Este flujo es el objetivo de desarrollo. No debe considerarse completamente implementado hasta que se cierren los entregables correspondientes de fase 2.

## 2. Glosario

- **Indexer:** buscador de enlaces torrent consultado mediante un agregador.
- **Torznab:** protocolo HTTP para consultar indexers; las respuestas utilizadas por VIEWTV son XML RSS.
- **Jackett:** agregador de indexers elegido para la integración de búsqueda de esta fase.
- **Prowlarr:** agregador alternativo; no forma parte de la integración aprobada actualmente.
- **qBittorrent:** cliente de descargas, con API web.
- **Jellyfin:** servidor multimedia y motor de reproducción.
- **TMDB:** fuente de metadatos de cine.
- **Lease:** bloqueo temporal de un trabajo para evitar que dos procesos lo procesen simultáneamente.
- **Backoff:** espera creciente entre reintentos.
- **LRU:** política de expulsión que prioriza lo utilizado hace más tiempo.
- **PWA:** aplicación web instalable.

## 3. Entorno real

- Windows 11, WSL2 con Ubuntu 24.04 y Docker Desktop con integración WSL.
- El proyecto se ejecuta desde `~/projects/viewtv` dentro del sistema de archivos de WSL, nunca desde `/mnt/c`.
- La aceleración de vídeo prevista es Intel Quick Sync (QSV). No utilizar NVENC.
- El portátil no está siempre encendido; se inicia manualmente cuando se necesita.
- Cliente previsto: Android TV / Fire TV mediante navegador compatible.
- Uso doméstico en red local, con dos perfiles protegidos mediante PIN.

Los servicios y su disponibilidad efectiva deben comprobarse en el entorno antes de dar por operativa cualquier integración.

## 4. Decisiones cerradas

Estas decisiones no deben reabrirse sin una justificación técnica y, cuando corresponda, un ADR.

1. Integración de búsqueda mediante adaptador Torznab genérico contra Jackett.
2. No implementar parseo de páginas HTML.
3. Jellyfin es el motor de reproducción y biblioteca.
4. La cola de trabajos debe ser durable y persistente en SQLite, nunca únicamente en memoria.
5. El worker debe ser independiente del proceso web.
6. Intel Quick Sync (QSV) es la tecnología de aceleración de vídeo elegida; no NVENC.
7. La aplicación es una PWA, no un envoltorio nativo.
8. Interfaz, logs, documentación y mensajes de commit en español de España.
9. Utilizar únicamente fuentes y contenido cuyo uso esté autorizado.

Las decisiones describen la arquitectura aprobada. Su inclusión aquí no significa que todas las funcionalidades estén implementadas.

## 5. Fuentes e indexers

La integración aprobada para fase 2 utiliza Jackett mediante Torznab.

- Las consultas se realizan mediante el endpoint Torznab de Jackett.
- Las respuestas se procesan como XML RSS.
- El cliente HTTP de Jackett está implementado y dispone de pruebas.
- La integración funcional de búsqueda y selección corresponde al entregable 6 de fase 2.
- La integración funcional de envío y seguimiento en qBittorrent corresponde al entregable 7.
- Prowlarr no forma parte de la integración aprobada para esta fase.
- No se implementará análisis de páginas HTML.
- Solo se utilizarán fuentes cuyo uso esté autorizado.

No se consideran verificadas las listas antiguas de indexers, su disponibilidad, sus dominios ni sus definiciones actuales. Cualquier incorporación deberá comprobarse y respetar las restricciones de uso autorizado.

## 6. Flujo funcional previsto

El objetivo funcional es que un perfil autenticado pueda solicitar contenido y que VIEWTV gestione el proceso de forma persistente y controlada.

El flujo previsto es:

1. El usuario accede con su perfil.
2. Selecciona o solicita un medio disponible en Jellyfin.
3. El backend valida la sesión, el perfil y la solicitud.
4. La solicitud se registra de forma persistente.
5. El worker procesa la solicitud.
6. Se consultan los indexers autorizados mediante Jackett y Torznab.
7. El sistema presenta resultados para que el usuario pueda seleccionar uno.
8. El resultado seleccionado se envía a qBittorrent.
9. El worker realiza el seguimiento del estado de la descarga.
10. Se comprueba la disponibilidad del contenido mediante Jellyfin.

Este apartado describe el comportamiento objetivo. Los pasos pendientes no deben interpretarse como funcionalidades ya operativas.

## 7. Solicitudes y persistencia

Las solicitudes deben mantenerse en almacenamiento persistente para sobrevivir a reinicios del backend o del worker.

El diseño debe contemplar:

- Identificación del perfil que origina la solicitud.
- Identificación del medio solicitado.
- Prevención de solicitudes duplicadas.
- Estados y transiciones controlados.
- Registro de errores y marcas temporales.
- Reintentos seguros.
- Protección frente al procesamiento simultáneo de un mismo trabajo.

La persistencia debe apoyarse en SQLite. No se debe utilizar una cola en memoria como fuente de verdad.

### Estado implementado

El endpoint autenticado `POST /solicitudes` está implementado.

Su comportamiento documentado incluye:

- Exigencia de una sesión autenticada.
- Validación del perfil y del medio solicitado.
- Prevención de duplicados activos.
- Inserción transaccional mediante `BEGIN IMMEDIATE`.
- Respuestas diferenciadas para solicitudes inexistentes, conflictos y datos no válidos.
- Posibilidad de reintentar una solicitud fallida.
- Separación entre perfiles.

El endpoint registra solicitudes, pero esto no significa que el procesamiento completo de descargas esté terminado.

## 8. Modelo de descargas

El modelo `Descarga` está implementado y dispone de una migración de base de datos.

Los estados definidos son:

- `seleccionada`
- `enviada`
- `descargando`
- `pausada`
- `completada`
- `fallida`

El modelo contempla información como:

- Hash de la descarga.
- Título.
- Indexer de origen.
- Progreso.
- Tamaño.
- Error.
- Marcas temporales.

La migración correspondiente es `0004`. Existe un índice parcial único sobre `info_hash` para evitar duplicados conforme a las condiciones definidas en el modelo.

La existencia del modelo y de los clientes HTTP no implica que el ciclo completo de descarga, seguimiento y reconciliación esté integrado.

## 9. Worker y procesamiento

El worker debe ejecutarse de forma independiente del proceso web.

Su responsabilidad será procesar trabajos persistidos, gestionar estados, controlar reintentos y comunicarse con los servicios externos.

El procesamiento deberá diseñarse teniendo en cuenta:

- Recuperación después de reinicios.
- Prevención de ejecuciones simultáneas incompatibles.
- Transiciones de estado coherentes.
- Errores recuperables y no recuperables.
- Reintentos con backoff.
- Persistencia de resultados y errores.
- Comunicación con Jackett y qBittorrent mediante los clientes HTTP existentes.

El procesador de solicitudes es el entregable 5 de fase 2 y constituye el siguiente trabajo de desarrollo.

Antes de modificar código se debe inspeccionar la implementación actual del worker, revisar los modelos y las transacciones existentes, y acordar el diseño técnico del procesador.

No se debe dar por supuesto que existe una planificación mediante APScheduler ni otra tecnología concreta sin comprobarlo en el código.

## 10. Interfaz y orientación visual

La aplicación debe mantener una experiencia de uso doméstica, sencilla y adecuada para pantallas de televisión.

La decisión de orientación de portadas está documentada en el ADR 0001:

- Póster vertical.
- Proporción 2:3.
- Presentación en filas.

**El ADR está aceptado.** La implementación visual de esta decisión sigue pendiente y no debe confundirse con una decisión de arquitectura abierta.

No modificar estilos, portadas, componentes visuales ni frontend por iniciativa propia. Cualquier cambio visual requiere autorización expresa.

## 11. Seguridad y configuración

Los servicios externos deben configurarse mediante variables de entorno y mecanismos adecuados de configuración.

Criterios obligatorios:

- No incluir contraseñas, tokens ni claves en el repositorio.
- No publicar archivos `.env`.
- No versionar bases de datos locales ni copias de seguridad con información sensible.
- No registrar secretos en logs.
- Validar las sesiones y los permisos en el backend.
- No confiar en la interfaz como único mecanismo de autorización.
- Mantener las credenciales de los servicios externos fuera del código.

Los ejemplos de configuración deben utilizar valores ficticios y dejar claro qué parámetros debe proporcionar cada instalación.

## 12. Pruebas y validación

Las pruebas deben acompañar a cada entregable y comprobar el comportamiento real de la funcionalidad modificada.

En la revisión del entregable 4 se documentaron:

- 73 pruebas backend ejecutadas correctamente.
- Ruff ejecutado correctamente.
- `git diff --check` sin errores.

No se documentó una prueba específica de concurrencia HTTP para ese entregable. Por tanto, no debe afirmarse que esa condición quedó cubierta por las pruebas.

Los resultados históricos de fases anteriores deben conservarse como antecedentes, diferenciándolos de las validaciones actuales.

Cada nuevo entregable debe registrar qué pruebas se ejecutaron, su resultado y las limitaciones conocidas.

## 13. Estado de desarrollo

### Fase 1

<badge color="success">Cerrada</badge>

La fase 1 está cerrada. Sus resultados y validaciones históricas se conservan en la documentación especializada.

### Fase 2

<badge color="warning">En curso</badge>

| Entregable | Descripción | Estado |
|---|---|---|
| 1 | Configuración de servicios de descarga | Cerrado |
| 2 | Clientes HTTP de Jackett y qBittorrent | Cerrado |
| 3 | Modelo de descarga y migración | Cerrado |
| 4 | Endpoint autenticado de solicitudes | Cerrado |
| 5 | Procesador de solicitudes en el worker | Pendiente |
| 6 | Búsqueda y selección de resultados | Pendiente |
| 7 | Envío y seguimiento mediante qBittorrent | Pendiente |
| 8 | Pruebas de resiliencia e integración | Pendiente |

El siguiente trabajo es el entregable 5. No adelantar los entregables 6, 7 u 8 sin cerrar y validar los anteriores conforme al plan.

## 14. Estado del repositorio

En la revisión del 15 de noviembre de 2026 se registró:

- Rama de trabajo: `inventario-trabajo-local`.
- HEAD local: `f050115`.
- Referencia remota: `a6b9daa`.
- Seis commits locales por delante de la rama remota.

Los seis commits locales registrados eran:

1. `e3b4676` — Configurar servicios de descarga.
2. `c51f3b7` — Añadir clientes HTTP de Jackett y qBittorrent.
3. `ad2add4` — Documentar avance de fase 2.
4. `dfb00f7` — Añadir modelo y migración de descargas.
5. `59e4d5e` — Documentar cierre del modelo de descargas.
6. `f050115` — Añadir endpoint autenticado de solicitudes.

El estado limpio del árbol de trabajo corresponde a la revisión previa a las modificaciones documentales actuales. No debe presentarse como estado actual sin ejecutar antes `git status`.

No se debe cambiar de rama, hacer push, crear PR, fusionar a `main`, hacer pull, resetear ni limpiar archivos sin autorización expresa.

## 15. Criterios de trabajo

El desarrollo debe avanzar en entregables pequeños, verificables y con límites claros.

Reglas de trabajo:

1. Inspeccionar el código existente antes de proponer cambios.
2. No dar por implementada una funcionalidad por el mero hecho de estar descrita.
3. No modificar código fuera del alcance del entregable acordado.
4. No alterar estilos ni interfaz visual sin autorización.
5. Ejecutar las pruebas pertinentes después de cada cambio.
6. Revisar los cambios con `git diff` y `git diff --check`.
7. Mantener la documentación coherente con el estado real del código.
8. Utilizar commits pequeños, en español y con un único entregable por commit.
9. Detenerse al terminar cada tarea y esperar indicaciones.
10. No hacer push ni operaciones de integración sin permiso explícito.

## 16. Restricciones de contenido y servicios

VIEWTV debe utilizar únicamente fuentes y contenido cuyo uso esté autorizado.

No se deben incorporar fuentes, indexers, dominios, definiciones ni mecanismos de acceso sin comprobar previamente su legitimidad y compatibilidad con las restricciones del proyecto.

La integración técnica no justifica eludir controles de acceso, restricciones de uso o condiciones de servicio.

No implementar parseo HTML como mecanismo alternativo a Torznab.

## 17. Documentación del proyecto

La documentación debe tener una fuente de verdad coherente y evitar duplicidades innecesarias.

Cada documento tiene una responsabilidad concreta:

| Documento | Responsabilidad |
|---|---|
| `README.md` | Presentación del proyecto y navegación documental |
| `docs/CONTEXTO.md` | Contexto general, decisiones y criterios de trabajo |
| `docs/ESTADO.md` | Estado actual, entregables y siguiente tarea |
| `docs/FASE-2.md` | Plan y seguimiento detallado de fase 2 |
| `docs/REVISION-IMPLEMENTACION.md` | Revisiones técnicas e incidencias históricas |
| `docs/arquitectura.md` | Arquitectura y relaciones entre componentes |
| `docs/especificacion-y-estado.md` | Especificación funcional y estado de funcionalidades |
| `docs/plan-operativo.md` | Plan de trabajo y operaciones del proyecto |
| `docs/backup-operativo.md` | Procedimiento de copias de seguridad y recuperación |
| `docs/reproduccion-jellyfin.md` | Configuración y funcionamiento de la reproducción |
| `docs/adr/0001-orientacion-de-portadas.md` | Decisión de orientación y proporción de portadas |

También deben mantenerse los README específicos de `backend`, `frontend` y `worker` cuando describan instrucciones propias de cada componente.

Los documentos especializados no deben eliminarse por duplicar parcialmente información. Se deben corregir sus referencias y responsabilidades para que no contradigan esta fuente de contexto.

## 18. Mantenimiento de este documento

Actualizar este documento cuando cambien:

- Las decisiones de arquitectura.
- El entorno real de desarrollo.
- El estado de los entregables.
- Las responsabilidades de los componentes.
- Las restricciones de seguridad o contenido.
- La organización de la documentación.

Los resultados de pruebas, commits y estados del repositorio deben fecharse y verificarse antes de documentarlos.

No convertir objetivos futuros en afirmaciones sobre funcionalidades disponibles.

---

**Regla principal:** el código y las pruebas determinan qué está implementado; los ADR determinan las decisiones aceptadas; `ESTADO.md` y `FASE-2.md` reflejan el avance; este documento proporciona el contexto general para mantener todo coherente.
