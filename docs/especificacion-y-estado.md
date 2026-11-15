# VIEWTV — Especificación funcional e historial de implementación

**Última revisión documental:** 15 de noviembre de 2026
**Rama de trabajo:** `inventario-trabajo-local`
**Estado vigente:** fase 1 cerrada; fase 2 en curso.

Este documento recoge la visión funcional de VIEWTV, sus decisiones de diseño y un historial resumido de validaciones anteriores. Para conocer el estado operativo actual, los entregables cerrados y el siguiente trabajo autorizado, consultar primero `docs/ESTADO.md` y `docs/FASE-2.md`.

---

## 1. Visión del producto

VIEWTV será una aplicación web progresiva (PWA) doméstica, en español de España, con una experiencia de catálogo audiovisual adaptada a televisores Android TV y Fire TV y manejable con mando a distancia.

Principios del producto:

- El catálogo, los metadatos, los perfiles, las solicitudes y los estados son persistentes.
- Los archivos de vídeo se almacenan separadamente de los metadatos y están sujetos a una cuota configurable.
- La caché del navegador podrá conservar información del catálogo para mostrar los últimos datos conocidos cuando el servidor no esté disponible.
- El equipo se encenderá cuando se vaya a utilizar. Los servicios deberán tolerar reinicios y recuperar el trabajo pendiente.
- Se contemplan dos perfiles protegidos por PIN: Adultos e Infantil.
- La primera versión será de uso doméstico y no expondrá sus servicios directamente a Internet.
- Solo se utilizarán fuentes y contenidos propios, autorizados o de dominio público.

La visión funcional no implica que todas estas capacidades estén implementadas.

## 2. Experiencia funcional prevista

### 2.1 Catálogo y navegación

La experiencia objetivo contempla:

- Inicio con filas horizontales: Continuar viendo, Novedades, Tendencias, Por género y Fijados.
- Pósteres verticales con proporción 2:3.
- Ficha de contenido con fondo, sinopsis, año, duración, géneros, reparto, calidad, audio, disponibilidad y títulos similares.
- Búsqueda mediante teclado en pantalla.
- Navegación completa con cruceta, Enter y Atrás.
- Estados de carga, error, catálogo vacío y servidor apagado.
- Administración desde escritorio para consultar solicitudes, almacenamiento, ajustes y registros.

### 2.2 Acciones de una ficha

- **Ver ahora:** solicita contenido que el usuario tenga derecho a obtener o permite reproducirlo si ya está disponible.
- **Mantener:** fija un elemento para excluirlo de la expulsión automática.
- **Borrar:** elimina el archivo temporal cuando no esté en reproducción ni tenga una transferencia activa.
- **Consultar disponibilidad:** informa del estado real. No se afirmará que existe una fuente hasta haberla consultado.

Estas acciones describen el comportamiento objetivo; su disponibilidad depende de la implementación de cada fase.

### 2.3 Reproducción y ciclo de vida

Estados funcionales propuestos para el ciclo de vida completo:

`pendiente`, `buscando`, `descargando`, `listo`, `en_reproduccion`, `visto`, `expira`, `borrado`, `fallido`, `vigilando`, `fijado` y `cancelado`.

Comportamiento previsto:

- Reutilizar un archivo que ya esté en caché.
- Cuando una fuente autorizada permita descarga progresiva, valorar el inicio de reproducción antes de finalizar la transferencia.
- Registrar el progreso de visionado.
- La propuesta inicial contempla marcar como visto al alcanzar el 90 % y programar el borrado 48 horas después.
- Al borrar el archivo temporal, conservar el catálogo y sus metadatos.
- Limitar inicialmente la concurrencia a una transferencia y una reproducción simultáneas.
- No borrar archivos en reproducción ni transferencias activas.

Los umbrales de reproducción progresiva deberán validarse con Jellyfin, el cliente y el formato de archivo. No se consideran garantizados por diseño.

### 2.4 Almacenamiento

La planificación inicial contempla:

- Cuota de caché de 80 GB en el SSD de 1 TB.
- Expulsión por antigüedad (LRU) de elementos vistos y no fijados al superar el 90 % de la cuota.
- Protección de elementos en reproducción y transferencias activas.
- Umbral propuesto de 15 GB libres para bloquear nuevas solicitudes, pendiente de validar frente al espacio real y las necesidades de Windows y WSL.
- Panel de ocupación, cuota, elementos almacenados y acción Vaciar caché.
- El borrado de la caché no debe eliminar SQLite, perfiles, catálogo ni metadatos.

La cuota, la expulsión y el umbral de espacio libre no deben considerarse implementados por el mero hecho de estar definidos aquí.

## 3. Solicitudes, cola y procesamiento

### 3.1 Prioridades funcionales propuestas

- **P0:** petición confirmada desde el chat.
- **P1:** petición desde una ficha o elemento fijado.
- **P2:** descubrimiento o relleno automático opcional.

El descubrimiento automático, si se habilita, deberá tener límites configurables, presupuesto por ciclo, deduplicación, idempotencia, criterios de calidad y modo de simulación. Por defecto, podrá enriquecer metadatos y novedades, pero no iniciará transferencias sin activación explícita.

### 3.2 Requisitos de la cola

La cola debe ser durable y persistir en SQLite, no depender de memoria del proceso.

Requisitos funcionales previstos:

- Reclamación exclusiva de tareas.
- Lease inicial propuesto de 120 segundos y heartbeat cada 30 segundos.
- Recuperación de tareas cuyo lease haya caducado.
- Reconciliación al arrancar con el cliente de transferencias, cuando esté configurado.
- Backoff exponencial.
- Estado de vigilancia cuando se agoten los intentos, con motivo visible y comprobaciones periódicas.
- Reactivación de tareas vigiladas cuando vuelva a existir una fuente autorizada.
- Lista de espera con estado, motivo, intentos, próxima comprobación y acciones de reintento o retirada.

Los intervalos, máximos de intentos y comportamiento de recuperación deben configurarse y probarse. La presencia de campos de lease no demuestra que exista un procesador completo.

### 3.3 Estado de implementación

La infraestructura de API, solicitudes, persistencia y worker ha avanzado por entregas. El procesador real de solicitudes en el worker es el siguiente trabajo previsto en fase 2.

Antes de implementarlo se debe inspeccionar el worker existente, acordar el diseño y comprobar las responsabilidades de la cola, los modelos y los clientes HTTP. No se debe asumir que la infraestructura actual ya procesa descargas reales.

## 4. Chat integrado — visión futura

Intenciones funcionales previstas:

- `buscar_y_encolar`
- `consultar_disponibilidad`
- `borrar`
- `pausar`
- saludo

Flujo objetivo:

1. Extraer título y año.
2. Resolver el contenido con TMDB y desambiguar cuando sea necesario.
3. Presentar una tarjeta de confirmación con los datos del contenido.
4. Crear una solicitud P0 únicamente después de la confirmación.
5. Informar del estado real de la solicitud.
6. Pedir aclaración si no se resuelve el contenido.
7. Explicar si no existe una fuente autorizada y, cuando proceda, dejar la solicitud en vigilancia.

El parser inicial será determinista, basado en patrones y búsqueda difusa. Un modelo local podrá ser opcional, pero no será obligatorio. El chat no podrá modificar ajustes y el historial estará separado por perfil.

Esta sección describe una capacidad futura, no una funcionalidad que deba darse por implementada.

## 5. Arquitectura y decisiones técnicas

### 5.1 Componentes

La arquitectura prevista comprende:

- **PWA:** Next.js, React y TypeScript; manifest, service worker, modo standalone y navegación espacial.
- **API:** FastAPI, SQLModel y SQLite; autenticación, perfiles, catálogo, solicitudes, almacenamiento y ajustes.
- **Worker:** proceso separado de la API HTTP para ejecutar tareas largas y procesar solicitudes.
- **Jellyfin:** servidor de biblioteca y reproducción. VIEWTV no implementará un motor de reproducción propio.
- **TMDB:** proveedor de metadatos y atribución.
- **Jackett:** servicio de consulta de fuentes mediante un adaptador Torznab genérico.
- **qBittorrent:** cliente de transferencias, sujeto a la configuración de fuentes y contenido autorizados.
- **Notificaciones:** inicialmente dentro de la aplicación. Cualquier integración externa requerirá configuración expresa y segura.

### 5.2 Decisiones vigentes sobre fuentes

- La integración acordada es Jackett mediante un adaptador Torznab genérico.
- No se adopta Prowlarr como componente de esta implementación.
- Las respuestas Torznab se procesarán como datos estructurados XML.
- No se implementará parseo HTML ni automatización de páginas web.
- Las credenciales y URL de servicios permanecerán en la configuración del servidor, nunca en el frontend.
- No se presumirá que un indexer está disponible por aparecer en documentación externa o instalaciones anteriores.
- Solo se consultarán fuentes y contenidos cuya autorización esté acreditada.

La compatibilidad Torznab no garantiza legalidad, fiabilidad ni disponibilidad de una fuente.

### 5.3 Hardware y entorno

- Entorno de desarrollo y ejecución: Windows 11, WSL2 y Ubuntu 24.04.
- Docker Desktop y Docker Compose para los servicios del proyecto.
- La aceleración de vídeo prevista se basa en Intel Quick Sync (QSV).
- No configurar NVENC como alternativa automática ni trasladar decisiones de un entorno NVIDIA antiguo.
- La ruta real de almacenamiento compartido y los montajes activos deben comprobarse en el entorno antes de modificarlos.

### 5.4 Seguridad

- Los perfiles se autentican mediante PIN y mecanismos de sesión protegidos.
- Las claves de servicios externos se mantienen fuera del repositorio.
- Los servicios internos no deben exponerse directamente a Internet en la primera versión.
- La API y el worker acceden a las integraciones desde el backend.
- Los endpoints de catálogo, solicitudes e imágenes deben aplicar la autenticación y las restricciones correspondientes.
- No registrar ni publicar secretos, cookies, tokens ni contenido sensible.

## 6. Estado real del proyecto

El estado vigente se mantiene en documentos específicos para evitar duplicar información que se desactualiza con facilidad.

Consultar en este orden:

1. `docs/ESTADO.md`: resumen actual, rama, entregables y próximo paso.
2. `docs/FASE-2.md`: alcance, entregables y validaciones de la fase en curso.
3. `docs/CONTEXTO.md`: contexto técnico, decisiones y reglas de trabajo.
4. `docs/REVISION-IMPLEMENTACION.md`: diagnóstico técnico e historial de revisiones.
5. `docs/plan-operativo.md`: entorno, operaciones, persistencia y procedimientos.

### 6.1 Situación vigente a esta revisión

- Fase 1: cerrada.
- Fase 2: en curso.
- Entregables 1–4 de fase 2: cerrados.
- Siguiente trabajo: entregable 5, procesador de solicitudes en el worker.
- La existencia de clientes HTTP de Jackett y qBittorrent no equivale a tener integrado el flujo real de búsqueda y transferencia.
- Antes de modificar el worker se debe revisar su estado actual y presentar el diseño técnico para aprobación.

Para el detalle de commits, pruebas, validaciones y alcance de cada entregable, consultar `docs/ESTADO.md` y `docs/FASE-2.md`.

## 7. Historial de validaciones anteriores

Esta sección conserva hitos históricos. Las casillas y resultados que aparecen aquí describen ejecuciones fechadas; no sustituyen una comprobación actual.

### 7.1 Infraestructura inicial, autenticación y persistencia

Durante noviembre de 2026 se documentaron, entre otras, las siguientes validaciones iniciales:

- Instalación de Windows 11, WSL2 Ubuntu 24.04 y Docker Desktop.
- API FastAPI con endpoint de salud.
- SQLite, SQLModel y migraciones Alembic iniciales.
- Modelos iniciales de perfil, medio y solicitud.
- Infraestructura inicial de cola con reclamación, leases, heartbeat, finalización, fallo y reintento.
- Worker separado de la API HTTP.
- Autenticación mediante PIN, Argon2 y JWT en cookie HttpOnly.
- Perfiles Adultos e Infantil.
- Ejecuciones iniciales de pruebas backend, Ruff y GitHub Actions.

Los recuentos de pruebas y los identificadores de CI pertenecen a aquellas ejecuciones y no deben interpretarse como los resultados actuales. Para cifras vigentes, consultar los documentos de estado.

### 7.2 Backup y restauración aislada — validación histórica del 4 de noviembre de 2026

En esa fecha se documentaron estas comprobaciones:

- Copia coherente de SQLite mediante `sqlite3.Connection.backup()`.
- Comprobación de integridad con `PRAGMA integrity_check`.
- Lectura de los perfiles y de la versión de Alembic.
- Restauración aislada en un contenedor temporal, sin modificar la base activa.
- Arranque de una API temporal y comprobación de `/health`.
- Eliminación posterior del contenedor temporal.

También se documentó el script `backend/scripts/backup_db.py`, con comprobación de integridad, publicación atómica y retención configurable mediante `BACKUP_RETENTION_DAYS`.

Se registró una ejecución manual correcta del script y una prueba del lanzador Windows/WSL:

- `scripts/backup-daily.sh`
- `scripts/backup-daily.ps1`

El historial del 4 de noviembre también indica que se creó en el Programador de tareas de Windows una tarea llamada `VIEWTV - Backup diario`, con desencadenador diario a las 03:00, y que una ejecución manual desde el Programador generó una copia correctamente.

**Alcance y cautela:** esto acredita las pruebas registradas en esa fecha. No acredita por sí solo que todas las ejecuciones programadas posteriores hayan tenido éxito, que el portátil haya estado encendido a la hora prevista ni que se haya ensayado una recuperación completa del host. El estado operativo actual del backup debe comprobarse en `docs/backup-operativo.md` y en el entorno.

### 7.3 Integración inicial con Jellyfin — validaciones históricas del 4 de noviembre de 2026

El historial de implementación recoge:

- Conectividad autenticada desde el contenedor API hacia Jellyfin nativo en Windows.
- Cliente HTTP de solo lectura.
- Endpoints protegidos por sesión VIEWTV para consultar el estado y sincronizar el catálogo.
- Sincronización de metadatos básicos de películas y series.
- Uso de una clave API conservada en la configuración local, sin incorporarla al repositorio.
- Sincronización autenticada que devolvió cero elementos porque las bibliotecas todavía no contenían archivos.

También se documentó un proxy autenticado para imágenes primarias y fondos, con límite de tamaño, tipos MIME permitidos y cabeceras de seguridad.

Las pruebas registradas validaron autenticación, conectividad y respuestas de error esperadas con un catálogo vacío. No demostraron una descarga correcta de bytes de una carátula real desde una biblioteca poblada ni una experiencia visual terminada en la PWA.

Estas comprobaciones deben entenderse como hitos históricos. Para saber qué endpoints, clientes y pruebas siguen presentes en el código actual, consultar `docs/REVISION-IMPLEMENTACION.md` y el estado vigente.

## 8. Diferencias respecto al planteamiento inicial

El proyecto ha evolucionado desde su planteamiento original. Las decisiones vigentes prevalecen sobre cualquier nota antigua:

- El entorno real es Windows 11 con WSL2 Ubuntu 24.04, no un host Linux nativo asumido.
- La GPU considerada para aceleración es Intel integrada; la decisión es evaluar y utilizar QSV, no NVENC.
- La integración de fuentes acordada utiliza Jackett y Torznab genérico; no se debe reintroducir Prowlarr como decisión vigente.
- La lectura de fuentes se hará mediante respuestas estructuradas; no se implementará parseo HTML.
- El worker separado existe como infraestructura, pero el procesador real de solicitudes sigue siendo trabajo pendiente.
- La existencia de un cliente HTTP no demuestra que el flujo de descarga esté integrado.
- El equipo no estará necesariamente encendido de forma permanente; los procesos deben tolerar reinicios, leases caducados y recuperación.

## 9. Reglas de mantenimiento de este documento

- Mantener aquí la visión funcional, las decisiones de arquitectura y el historial resumido.
- No duplicar tablas de entregables, listas de commits ni resultados de pruebas que ya tengan un documento de referencia.
- Cuando una decisión cambie, actualizar primero el documento que actúe como fuente de verdad y después reflejar aquí el cambio.
- Identificar claramente las propuestas futuras y no describirlas como funcionalidades implementadas.
- Las validaciones históricas deben conservar su fecha y su alcance.
- No eliminar el historial útil de backup, restauración o Jellyfin; trasladar los procedimientos detallados a sus documentos especializados.
- No incluir secretos, claves API, tokens, cookies, bases de datos locales ni archivos de configuración privados.
- No modificar estilos, portadas ni componentes visuales del frontend como parte de una tarea documental.
