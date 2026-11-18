# VIEWTV — Plan operativo

**Última revisión:** 15 de noviembre de 2026
**Rama de trabajo:** `inventario-trabajo-local`
**Estado del proyecto:** fase 1 cerrada; fase 2 en curso.

Este documento recoge las instrucciones operativas del proyecto, el reparto de responsabilidades y los antecedentes de configuración del entorno.

Debe consultarse junto con `README.md`, `docs/CONTEXTO.md`, `docs/ESTADO.md`, `docs/FASE-2.md` y `docs/arquitectura.md`.

Los datos históricos se conservan como registro de operaciones realizadas. No deben interpretarse automáticamente como una comprobación del estado actual.

---

## 1. Reparto del trabajo

- **Usuario:** realiza instalaciones y configuraciones manuales en Windows, Ubuntu/WSL, Docker, Jellyfin y el televisor; ejecuta los comandos y valida cada tarea.
- **Asistente:** inspecciona el repositorio, propone diseños, prepara cambios de código y documentación, desarrolla pruebas y guía las operaciones manuales paso a paso.

Criterios de colaboración:

1. Indicar dónde ejecutar cada instrucción: PowerShell, Ubuntu/WSL o interfaz web.
2. Consultar el repositorio y la documentación antes de preguntar decisiones ya tomadas.
3. No dar una fase o entregable por terminado sin revisar sus pruebas y validaciones.
4. Separar los cambios en tareas pequeñas y verificables.
5. Detenerse al terminar cada tarea y esperar indicaciones.
6. No realizar operaciones destructivas ni de publicación sin autorización expresa.

El usuario debe ejecutar y comunicar los resultados de los comandos locales. No se debe afirmar que se ha modificado o validado el entorno cuando no existe una salida que lo demuestre.

## 2. Entorno de trabajo

### Configuración conocida

- Sistema anfitrión: Windows 11.
- Linux: Ubuntu 24.04 mediante WSL2.
- Docker: Docker Desktop con integración WSL2.
- Repositorio: `~/projects/viewtv` dentro del sistema de archivos Linux de WSL.
- Rama de trabajo: `inventario-trabajo-local`.
- Zona horaria de referencia: `Europe/Madrid`.
- GPU: Intel integrada.
- Aceleración de vídeo elegida: Intel Quick Sync (QSV), no NVENC.

El nombre del equipo y las direcciones locales pueden cambiar. No deben tratarse como configuración permanente sin comprobarlas.

### Reglas de ejecución

- Ejecutar los comandos del proyecto desde Ubuntu/WSL, dentro de `~/projects/viewtv`, salvo que se indique expresamente PowerShell o una interfaz web.
- No trabajar desde `/mnt/c` para ejecutar el repositorio.
- Mantener Docker Desktop y su integración WSL como entorno de contenedores.
- Comprobar `docker compose version` y `docker compose ps` cuando una tarea afecte al entorno.
- No asumir que WSL o Docker siguen ejecutándose cuando Windows suspende, hiberna o se apaga.

## 3. Almacenamiento y persistencia

El entorno se diseñó alrededor de un SSD anfitrión de 1 TB y una cuota inicial de caché de 80 GB.

En los registros históricos se documentaron estas rutas de Windows:

- `C:\VIEWTV\media`
- `C:\VIEWTV\cache`
- `C:\VIEWTV\data`
- `C:\VIEWTV\backups`

Desde WSL se accedía a ellas mediante `/mnt/c/VIEWTV/`.

La base de datos SQLite se ha mantenido históricamente en el volumen Docker `viewtv_viewtv_data`, montado en `/data`, con el archivo `/data/viewtv.db`.

La configuración de volúmenes y rutas debe comprobarse en Docker Compose antes de realizar cambios. No se debe deducir el estado actual de los montajes a partir de las pruebas históricas.

### Reglas de persistencia

1. Separar la caché temporal de SQLite, perfiles y metadatos persistentes.
2. No almacenar la base de datos únicamente en una carpeta temporal.
3. No eliminar volúmenes Docker sin identificar su contenido y obtener autorización.
4. No copiar una base SQLite activa mediante un `cp` ordinario como procedimiento de backup.
5. Utilizar el mecanismo de copia online de SQLite documentado en `docs/backup-operativo.md`.
6. Verificar la integridad de las copias antes de considerarlas válidas.
7. Mantener una copia adicional fuera del portátil para protegerse ante la pérdida del equipo o del SSD.

La cuota inicial de caché es 80 GB para el SSD de 1 TB. No modificarla sin revisar la decisión y sus consecuencias.

## 4. Docker y servicios

Docker Desktop con integración WSL2 es el entorno aprobado.

Antes de intervenir en servicios:

```bash
docker compose config --quiet
docker compose ps
```

Si se modifican imágenes o configuración, ejecutar las comprobaciones correspondientes y verificar el estado de los servicios.

No utilizar `docker compose down -v` como operación rutinaria: puede eliminar volúmenes persistentes.

La base de datos, la caché y los backups tienen responsabilidades y ubicaciones diferentes. Cualquier modificación de sus montajes debe revisarse antes de aplicarse.

No dar por operativo un servicio solo porque su configuración Compose sea válida. Cuando corresponda, comprobar también su arranque, logs, healthcheck y persistencia.

## 5. Jellyfin

Jellyfin es el servidor de biblioteca y reproducción.

VIEWTV conserva su propia gestión de perfiles, solicitudes, catálogo local y experiencia de usuario.

La integración desarrollada utiliza la API de Jellyfin para consultar el catálogo y sus metadatos. La comunicación se realiza desde el backend, manteniendo la clave API fuera del navegador.

Criterios:

- Utilizar una cuenta de servicio con privilegios mínimos.
- Guardar la clave API únicamente en la configuración local del servidor.
- No devolver credenciales ni URLs internas sensibles al frontend.
- Mantener las operaciones de catálogo dentro de los permisos previstos.
- No duplicar innecesariamente el enriquecimiento de metadatos entre Jellyfin y VIEWTV.
- Verificar la disponibilidad real de bibliotecas y archivos antes de validar una sincronización con contenido.

La instalación nativa de Jellyfin en Windows y las pruebas realizadas en noviembre forman parte del historial del entorno. No migrar Jellyfin a Docker sin una decisión expresa.

La integración de lectura y el proxy de imágenes tienen antecedentes de validación real documentados en este archivo histórico. Esas pruebas no equivalen a validar todo el flujo de reproducción desde VIEWTV.

## 6. Fuentes, búsqueda y transferencias

### Decisiones vigentes

- Agregador elegido: Jackett.
- Protocolo: Torznab.
- Formato de respuesta: XML RSS.
- Adaptador: genérico, mediante cliente HTTP.
- No implementar parseo de páginas HTML.
- No utilizar Prowlarr como integración aprobada de esta fase.
- Cliente de transferencias: qBittorrent.
- Utilizar exclusivamente fuentes y contenido cuyo uso esté autorizado.

TMDB puede aportar metadatos, pero no proporciona archivos de vídeo.

La integración técnica debe respetar las condiciones de uso de las fuentes. No se deben incorporar indexers, dominios o mecanismos de acceso sin verificar previamente que su uso está autorizado.

### Estado de desarrollo

Los clientes HTTP de Jackett y qBittorrent están implementados.

Esto no significa que la búsqueda funcional, la selección de resultados, el envío de descargas y su seguimiento estén terminados.

La secuencia de fase 2 está definida en `docs/FASE-2.md`:

- Entregable 5: procesador de solicitudes en el worker.
- Entregable 6: búsqueda y selección de resultados.
- Entregable 7: envío y seguimiento mediante qBittorrent.
- Entregable 8: pruebas de resiliencia e integración.

No adelantar esos trabajos ni instalar o configurar servicios adicionales sin que formen parte del entregable aprobado.

## 7. Seguridad y red local

La versión inicial está orientada al uso doméstico en red local.

Criterios:

1. No abrir puertos en el router.
2. No publicar API, Jellyfin ni paneles de administración en Internet.
3. Restringir los servicios a los dispositivos y redes necesarios.
4. Mantener las credenciales fuera del repositorio.
5. Utilizar sesiones y permisos validados en backend.
6. No confiar exclusivamente en los controles de la interfaz.
7. No compartir PIN, contraseñas, claves API, cookies ni tokens por chat.
8. No incluir archivos `.env`, bases de datos locales o copias con información sensible en commits.

Cualquier ampliación del acceso desde la LAN debe incluir una revisión del bind de los servicios, firewall y autenticación.

No se debe asumir que un nombre `.local` o una dirección IP siguen siendo válidos sin comprobar su resolución desde el dispositivo de destino.

## 8. Fire TV y validación en televisión

El cliente previsto incluye Android TV y Fire TV mediante un navegador compatible.

La validación en televisión debe comprobar, cuando el entregable afecte a la interfaz:

- Navegación con cruceta.
- Gestión del foco.
- Activación mediante Enter.
- Navegación hacia atrás.
- Desplazamiento.
- Legibilidad y disposición en pantalla.
- Acceso a carátulas e imágenes.

TV Bro se documentó como navegador de prueba para Fire TV.

La validación en TV no debe confundirse con las pruebas automatizadas del frontend.

No realizar modificaciones visuales ni cambios de diseño sin autorización expresa. La decisión de orientación de portadas está aceptada en el ADR 0001, pero su implementación visual requiere autorización dentro del alcance de trabajo correspondiente.

## 9. Plan de desarrollo vigente

La fase 1 está cerrada.

La fase 2 está en curso y se divide en ocho entregables:

| Entregable | Trabajo | Estado |
|---|---|---|
| 1 | Configuración de servicios de descarga | Cerrado |
| 2 | Clientes HTTP de Jackett y qBittorrent | Cerrado |
| 3 | Modelo de descarga y migración | Cerrado |
| 4 | Endpoint autenticado de solicitudes | Cerrado |
| 5 | Procesador de solicitudes en el worker | Pendiente |
| 6 | Búsqueda y selección de resultados | Pendiente |
| 7 | Envío y seguimiento mediante qBittorrent | Pendiente |
| 8 | Pruebas de resiliencia e integración | Pendiente |

El siguiente trabajo es el entregable 5.

Antes de modificar el worker se debe:

1. Inspeccionar su implementación actual.
2. Revisar los modelos de solicitudes y descargas.
3. Revisar la persistencia y las transacciones existentes.
4. Definir recuperación, concurrencia y responsabilidades.
5. Revisar la integración con los clientes HTTP existentes.
6. Presentar el diseño técnico para aprobación.

No adelantar los entregables 6, 7 u 8.

El seguimiento detallado está en `docs/FASE-2.md` y el estado resumido en `docs/ESTADO.md`.

## 10. Pruebas y criterios de aceptación

Cada entregable debe contar con comprobaciones adecuadas a su alcance.

Como mínimo:

- Pruebas automatizadas de la funcionalidad modificada.
- Ruff para el código Python cuando corresponda.
- Typecheck, lint y build para cambios de frontend.
- Validación de migraciones sobre una base temporal cuando corresponda.
- `git diff --check`.
- Revisión del diff para detectar cambios ajenos al alcance.

Las pruebas deben documentar sus límites. Una prueba concreta de concurrencia no demuestra la ausencia de todas las condiciones de carrera.

No ejecutar pruebas destructivas sobre la base de datos real.

Las pruebas funcionales con medios deben utilizar contenido propio o autorizado.

## 11. Copias de seguridad y recuperación

La documentación especializada es `docs/backup-operativo.md`.

Los registros históricos de noviembre de 2026 incluyen:

- Copias online de SQLite mediante `sqlite3.Connection.backup()`.
- Validación de integridad mediante `PRAGMA integrity_check`.
- Verificación de perfiles y revisión Alembic.
- Transferencia explícita de archivos al SSD anfitrión.
- Lanzadores Bash y PowerShell.
- Pruebas del Programador de tareas de Windows.

También se documentó una incidencia en el montaje de backups que obligó a sustituir la transferencia mediante bind mount por una copia explícita al SSD y validación posterior.

Estos registros acreditan las operaciones realizadas en aquellas fechas, no la ejecución continuada de la tarea en la actualidad.

Antes de considerar operativo el backup periódico, comprobar:

1. Que la tarea programada existe.
2. Que el lanzador funciona.
3. Que se crea un archivo nuevo en el destino esperado.
4. Que la copia supera la comprobación de integridad.
5. Que los errores quedan registrados.
6. Que se conserva una copia adicional fuera del portátil.

El equipo no es un servidor 24/7. Si está apagado, no puede ejecutar la tarea programada.

No sobrescribir `/data/viewtv.db` para probar una restauración. Utilizar un entorno aislado conforme al procedimiento especializado.

## 12. Repositorio y flujo Git

El repositorio privado es `wizzadrds/viewtv`.

Rama de trabajo vigente: `inventario-trabajo-local`.

Reglas obligatorias:

- No cambiar de rama sin autorización.
- No hacer push sin autorización.
- No crear PR ni fusionar a `main` sin autorización.
- No hacer pull, reset, checkout ni limpiar archivos sin autorización.
- No eliminar archivos auxiliares sin revisar su contenido e historial.
- No incluir secretos ni datos locales en commits.
- Realizar commits pequeños en español, con un entregable por commit.
- Revisar `git status`, `git diff` y `git diff --check` antes de preparar un commit.

La revisión documental actual debe completarse antes de realizar commits.

## 13. Documentación de referencia

| Documento | Uso |
|---|---|
| `README.md` | Presentación y navegación del proyecto |
| `docs/CONTEXTO.md` | Contexto general y decisiones |
| `docs/ESTADO.md` | Estado actual y siguiente tarea |
| `docs/FASE-2.md` | Seguimiento detallado de fase 2 |
| `docs/REVISION-IMPLEMENTACION.md` | Revisiones técnicas y validaciones históricas |
| `docs/arquitectura.md` | Arquitectura y componentes |
| `docs/especificacion-y-estado.md` | Especificación funcional |
| `docs/backup-operativo.md` | Copias de seguridad y recuperación |
| `docs/reproduccion-jellyfin.md` | Reproducción mediante Jellyfin |
| `docs/adr/0001-orientacion-de-portadas.md` | Decisión de orientación de portadas |

Los README de `backend`, `frontend` y `worker` deben conservar sus instrucciones específicas.

## 14. Historial operativo del entorno

Este apartado resume operaciones documentadas en noviembre de 2026. Se conserva como referencia histórica y no como inventario de disponibilidad actual.

### 14.1. Almacenamiento y Docker — 3 de noviembre

Se documentaron:

- Carpetas de medios, caché, datos y backups bajo `C:\VIEWTV`.
- Acceso desde WSL mediante `/mnt/c/VIEWTV/`.
- Montaje compartido de caché para API y worker.
- Base SQLite en el volumen Docker `viewtv_viewtv_data`.
- Verificación de escritura desde los contenedores.
- Arranque de API y worker.
- Respuesta HTTP 200 de `/health`.
- Persistencia de dos perfiles tras reiniciar los servicios.

También se eliminó un volumen de caché antiguo después de comprobar que ningún contenedor lo utilizaba.

Estas operaciones no autorizan a eliminar volúmenes actuales ni demuestran el estado presente de Docker.

### 14.2. Integración Jellyfin — 4 de noviembre

Se documentó:

- Creación de una clave API de servicio almacenada en configuración local.
- Conectividad desde el contenedor API hacia Jellyfin instalado en Windows.
- Cliente HTTP de solo lectura.
- Endpoints de estado y sincronización de catálogo.
- Sincronización de metadatos de películas y series.
- Pruebas automatizadas de autenticación y normalización.

Posteriormente se validó una sincronización con una biblioteca inicialmente vacía.

Más tarde se añadió un medio propio o autorizado y se comprobó:

- Inicio de sesión VIEWTV.
- Sincronización de un elemento.
- Lectura del catálogo.
- Respuesta correcta del proxy privado de imagen con `image/jpeg`.

Estas pruebas acreditaron el recorrido de catálogo e imagen en aquel entorno. No acreditaron por sí solas la reproducción completa desde VIEWTV.

### 14.3. Proxy de imágenes y catálogo

Se documentó un proxy privado de imágenes Jellyfin con:

- Sesión VIEWTV obligatoria.
- Identificador local del medio.
- Tipos de imagen permitidos.
- Límite de tamaño.
- Rechazo de tipos no permitidos.
- Cabeceras de seguridad.
- Caché privada.

También se incorporó un endpoint de lectura del catálogo con filtros y paginación.

Las pruebas históricas incluyen respuestas de autenticación, catálogo vacío y posteriormente una imagen real.

### 14.4. Primera interfaz PWA

En noviembre se documentó una primera iteración basada en Next.js, React y TypeScript.

Incluía selección de perfil, PIN, restauración de sesión, catálogo, búsqueda local, sincronización, ficha informativa y navegación inicial con mando.

La ficha era informativa y la reproducción no estaba conectada en aquella iteración.

La documentación histórica indicaba que quedaban pendientes validaciones en TV y varias capacidades de PWA. No se debe utilizar esa descripción como inventario actual sin inspeccionar el frontend.

### 14.5. Copias de seguridad — 4 y 5 de noviembre

Se realizaron pruebas de copia y restauración aislada de SQLite.

Se detectó una incidencia en el montaje de backups mediante bind mount, que se corrigió mediante transferencia explícita desde el contenedor al SSD y validación posterior.

Se incorporaron scripts Bash y PowerShell y se realizaron pruebas manuales de transferencia.

También se documentó una ejecución satisfactoria desde el Programador de tareas de Windows el 4 de noviembre y una prueba posterior de transferencia y validación manual el 5 de noviembre.

El procedimiento completo, sus limitaciones y las comprobaciones necesarias están en `docs/backup-operativo.md`.

No se debe inferir que la tarea diaria continúa funcionando sin una comprobación reciente.

---

**Regla operativa principal:** antes de actuar, comprobar el estado real del repositorio y del entorno. La documentación histórica explica cómo se llegó al estado actual, pero las operaciones futuras deben basarse en el código, las pruebas y las decisiones vigentes.

## Jackett y FlareSolverr — instalación comprobada

Fecha: 18 de noviembre de 2026.

- Jackett se ejecuta directamente en Windows, puerto 9117.
- El proceso identificado es JackettConsole.
- Desde Docker se alcanza mediante host.docker.internal:9117.
- La prueba HTTP necesitó Host: localhost:9117 y devolvió 302.
- FlareSolverr se ejecuta en Docker, puerto 8191.
- Se publica solamente en 127.0.0.1:8191.
- Docker Compose fue validado correctamente.
- El contenedor FlareSolverr aparece healthy.
- Su endpoint /health devolvió {"status":"ok"}.
- Jackett tiene configurada la URL http://127.0.0.1:8191.
- No se ha instalado un segundo Jackett en Docker.

Pendiente:
- Probar una consulta real que necesite FlareSolverr.
- Validar el circuito completo de búsqueda y descarga.
- No compartir claves API, PIN, tokens ni archivos .env.

Comprobaciones desde Ubuntu/WSL:
- docker compose config --quiet
- docker compose ps flaresolverr
- curl -fsS http://127.0.0.1:8191/health


### Validación de navegación de FlareSolverr — 18/11/2026

- FlareSolverr 3.5.2 con Chromium 152.
- El servicio HTTP y el healthcheck funcionan.
- Primera prueba con example.com: HTTP 500.
- El registro mostró net::ERR_CONNECTION_CLOSED.
- example.com también falló desde Windows y WSL.
- La conexión HTTPS desde WSL a Wikipedia respondió HTTP 200.
- Prueba mediante POST /v1 con request.get a
  https://www.wikipedia.org/: superada.
- FlareSolverr devolvió status=ok y HTTP destino=200.
- Mensaje recibido: Challenge not detected!
- Conclusión: navegación HTTPS mediante Chromium validada.
- Pendiente: probar un desafío real de Cloudflare
  mediante una fuente autorizada configurada en Jackett.


### Incidencia TLS de MejorTorrent — 18/11/2026

- Jackett: version 0.24.3065.0, instalado en Windows.
- La direccion principal del indexador funciona en navegador,
  segun comprobacion del propietario.
- Al configurar el indexador, Jackett intenta consultar /torrents.
- La conexion falla durante la negociacion TLS.
- Excepcion: HttpRequestException / SslStream.
- Jackett responde HTTP 500.
- FlareSolverr no registro peticiones durante ese intento.
- FlareSolverr funciona con otras paginas HTTPS.
- Existe una incidencia similar: Jackett GitHub #17190.
- Resultado: indexador no operativo; causa de red pendiente.
- No se han desactivado certificados ni protecciones TLS.
- No se han realizado descargas.

Pendiente: estudiar la conectividad TLS y la configuracion
del indexador mediante procedimientos oficiales.

## Validación real de Direct Play — 2026-11-18

- API VIEWTV reconstruida y saludable; Alembic en revisión
  `0008_solicitud_jellyfin_nullable`.
- Jellyfin utilizado: instancia Docker, puerto 8097.
- Fallo original: HTTP 400, `Guid can't be empty`, por ausencia
  de contexto `UserId` en la negociación de reproducción.
- Corrección: configuración `JELLYFIN_USER_ID` y envío de
  `UserId` a `/Items/{id}/PlaybackInfo`.
- Pruebas automatizadas: 5 superadas; Ruff y `git diff --check` correctos.
- Respaldo SQLite persistente comprobado: integridad `ok`.
- Sincronización del catálogo: 1 elemento procesado.
- `videoplayback`: registro antiguo VIEWTV ID 1 no disponible;
  registro actual VIEWTV ID 2 disponible.
- Autenticación de perfil VIEWTV: HTTP 200.
- `POST /jellyfin/media/2/playback-info`: HTTP 200,
  estado `listo`, 1 fuente Direct Play.
- `GET /jellyfin/media/2/stream` con `Range: bytes=0-1023`:
  HTTP 206, `Content-Type: video/mp4`,
  `Content-Range: bytes 0-1023/756644`,
  `Accept-Ranges: bytes`, 1024 bytes recibidos.
- Resultado: proxy de Direct Play y entrega parcial HTTP 206
  validados mediante prueba real.
- Pendiente: prueba visual de reproducción continuada en la PWA,
  si se requiere como aceptación adicional.

## Validacion visual del modo cine - 2026-11-18

- Frontend Next.js operativo en localhost:3000.
- Reproductor integrado con la API de VIEWTV.
- Negociacion Direct Play mediante PlaybackInfo.
- Streaming del video a traves del proxy de VIEWTV.
- Reproductor separado de la ficha de pelicula.
- Modo cine con video grande y fondo oscuro.
- Ficha mejorada y poster vertical 2:3.
- Controles de reproduccion, pausa, avance y volumen.
- Pantalla completa y regreso a la ficha comprobados.
- Prueba visual realizada en Windows: correcta.
- TypeScript: correcto.
- ESLint: correcto.
- git diff --check: correcto.
- Docker Compose: configuracion valida.
- Archivos de frontend:
  frontend/components/viewtv-app.tsx
  frontend/app/globals.css
- Backend, worker y SQLite sin cambios en esta tarea.

## Validacion de errores Torznab de Jackett - 2026-11-18

- Jackett Windows accesible desde Docker por el puerto 9117.
- API Torznab: capacidades XML validas, HTTP 200.
- DonTorrent: prueba interna de Jackett correcta.
- Busqueda manual de DonTorrent: devuelve resultados.
- Busqueda Torznab de "Nadie 2": HTTP 400, error 900.
- Diagnostico del registro: DonTorrent devolvio una pagina
  HTML con el aviso "Estamos saturados".
- Causa externa observada: saturacion temporal del sitio.
- Correccion en backend/app/jackett.py:
  deteccion de errores XML Torznab con HTTP 200 o 400.
- El cliente comunica el codigo Torznab sin exponer
  descripciones, HTML, claves ni trazas internas.
- Regresion: 85 pruebas superadas, 1 aviso no bloqueante.
- Ruff y git diff --check: correctos.
- No se modificaron la cola, el worker ni SQLite.
- No se iniciaron descargas.
- Pendiente: validar busquedas reales cuando el indexador
  vuelva a responder y revisar la politica de reintentos.

## Validacion de lectura de qBittorrent - 2026-11-18

- qBittorrent funciona de forma nativa en Windows.
- Conexion desde Docker: host.docker.internal:8080.
- Cliente VIEWTV: QBittorrentClient.
- Consulta real de version: correcta, v5.3.0.
- Consulta real de torrents con etiqueta de diagnostico:
  respuesta valida, cero elementos coincidentes.
- La configuracion y autenticacion existentes funcionan
  para las dos operaciones de lectura comprobadas.
- No se añadieron, modificaron ni eliminaron torrents.
- No se modificaron el worker ni SQLite.
- Pendiente: validar de forma controlada el envio de una
  descarga autorizada y su seguimiento por el worker.

## Consolidacion de solicitudes y descargas - 2026-11-18

- Modelos, cola durable, solicitudes y resultados de busqueda
  implementados en el arbol de trabajo local.
- Worker de busqueda y procesador de descargas disponibles.
- Migraciones encadenadas desde 0005 hasta 0008.
- Alembic reconoce 0008_solicitud_jellyfin_nullable como head.
- qBittorrent v5.3.0 y Web API 2.16.2 comprobados.
- Cliente qBittorrent actualizado para admitir stopped=True.
- Worker actualizado localmente para solicitar envios detenidos.
- La reconciliacion por etiqueta y el envio detenido tienen pruebas.
- Suite completa del backend: 132 pruebas superadas.
- Ruff y git diff --check correctos.
- Dos advertencias de deprecacion no bloqueantes.
- APScheduler no se utiliza en backend/app ni worker.
- El worker Docker activo aun no incorpora estos cambios locales.
- No se han iniciado descargas reales durante la validacion.
- Pendiente: consolidar los archivos en Git, desplegar de forma
  controlada y validar un envio autorizado y su seguimiento.
