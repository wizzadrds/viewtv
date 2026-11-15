# Fase 2 — Primera descarga real controlada

## Objetivo

Conseguir que una solicitud de vídeo recorra el camino desde la API hasta una descarga real, utilizando la cola durable y los servicios existentes.

La fase se ejecuta por entregables independientes. Cada entregable se revisa, valida y confirma antes de empezar el siguiente.

## Alcance aprobado

1. Configuración de Jackett y qBittorrent.
2. Clientes HTTP independientes para ambos servicios.
3. Modelo `Descarga` y migración Alembic.
4. Endpoint autenticado para crear solicitudes.
5. Procesador de solicitudes en el worker.
6. Búsqueda, filtrado y selección de resultados.
7. Envío y seguimiento en qBittorrent.
8. Pruebas de errores, reintentos, duplicados y reinicios.

Quedan fuera de esta fase el chat, el descubrimiento automático, los cambios visuales, la reproducción progresiva completa y la expiración automática de caché.

## Diseño técnico acordado

Flujo previsto:

`API autenticada (Medio.id) → SQLite / cola durable → worker → Jackett/Torznab → filtros → qBittorrent → persistencia de hash, progreso y estado → comprobación de disponibilidad en Jellyfin`

Se mantienen separados tres conceptos:

- **Solicitud:** representa el trabajo pendiente y conserva el ciclo de vida de la cola.
- **Descarga:** representa la operación concreta enviada al cliente qBittorrent y conserva su hash, estado, progreso, tamaño y errores.
- **Medio:** representa la disponibilidad real en Jellyfin. No se considera disponible solo porque exista un torrent.

### Idempotencia y recuperación

- Antes de añadir un torrent, el worker debe consultar qBittorrent.
- La descarga debe identificarse mediante hash y una etiqueta/categoría propia de VIEWTV.
- Si qBittorrent acepta un torrent y el worker cae antes de guardar el resultado en SQLite, la recuperación debe reconciliar el torrent existente antes de volver a enviarlo.
- No se deben crear descargas duplicadas para el mismo hash.

### Búsqueda y selección

Los resultados Torznab se filtran por:

- Calidad, resolución y códec compatibles con el perfil.
- Audio castellano cuando los metadatos permitan verificarlo de forma fiable.
- Número mínimo de seeders.
- Límites de tamaño.
- Hash duplicado.

No se debe afirmar que un resultado tiene audio castellano si el dato no está disponible o no es fiable.

### Estados separados

La solicitud conserva sus estados propios.

La descarga utiliza los estados acordados:

`selected → submitted → downloading → paused → completed`

También puede terminar en `failed`.

La disponibilidad del medio se determina por separado mediante Jellyfin.

### Estados de Descarga implementados

El modelo `Descarga` utiliza los estados persistidos en español:

`seleccionada`, `enviada`, `descargando`, `pausada`, `completada` y `fallida`.

## Restricción de fuentes y uso autorizado

No utilizar DonTorrent ni otras fuentes cuya autorización no esté acreditada. La configuración local puede contener indexers, pero VIEWTV solo debe buscar y descargar contenido de fuentes que el usuario esté autorizado a utilizar.

No compartir claves API, tokens ni secretos. Las claves de Jackett y qBittorrent permanecen en la configuración privada del entorno y nunca se incorporan al repositorio.

## Entregable 1 — Configuración

**Estado: cerrado.**

Archivos modificados:

- `backend/app/config.py`
- `.env.example`
- `backend/tests/test_integrations_config.py`

Se añadieron parámetros de configuración para:

- URL base, clave API y timeout de Jackett.
- URL base, clave API y timeout de qBittorrent.

Los valores de ejemplo utilizan `host.docker.internal` para acceder desde Docker a servicios instalados en Windows.

Prowlarr queda reservado; la integración de búsqueda de este entregable utiliza Jackett.

Validaciones comunicadas:

- `make backend-test`: 42 pruebas superadas.
- `make backend-lint`: correcto.
- `git diff --check`: correcto.

Commit local:

`e3b4676 Configurar servicios de descarga`

## Entregable 2 — Clientes HTTP independientes

**Estado: cerrado.**

Archivos añadidos:

- `backend/app/jackett.py`
- `backend/app/qbittorrent.py`
- `backend/tests/test_jackett.py`
- `backend/tests/test_qbittorrent.py`

### Cliente Jackett

Se implementó `JackettClient`, con:

- Errores propios mediante `JackettError`.
- Resultado tipado mediante `JackettResult`.
- Búsqueda Torznab agregada.
- Soporte de búsqueda general, series y películas.
- Parseo XML RSS independiente de los namespaces.
- Extracción de título, URL de descarga, magnet, infohash, seeders, peers, tamaño, categorías, indexer y fecha cuando están disponibles.
- Transporte HTTP inyectable para pruebas.

No se incorporó `get_indexers()` porque la forma de su respuesta no se había validado contra una instancia real de Jackett.

### Cliente qBittorrent

Se implementó `QBittorrentClient`, con:

- Autenticación Bearer.
- Consulta de versión.
- Consulta de torrents y filtrado por hashes.
- Envío de torrents mediante formulario multipart.
- Parámetros opcionales de ruta, categoría, etiquetas y pausa.
- Validación de la respuesta de confirmación.
- Errores HTTP saneados para no filtrar secretos.

La operación de alta utiliza los campos multipart esperados por la API, no un formulario URL-encoded.

### Contratos de API verificados

Entorno de referencia comunicado:

- Jackett `v0.24.3065`.
- qBittorrent `v5.3.0`.

Rutas utilizadas:

- Jackett: `/api/v2.0/indexers/all/results/torznab/api`
- qBittorrent: `/api/v2/app/version`
- qBittorrent: `/api/v2/torrents/info`
- qBittorrent: `/api/v2/torrents/add`

La API de alta de qBittorrent no devuelve el hash del torrent. La implementación posterior deberá reconciliar el resultado consultando la lista de torrents por hash y etiqueta/categoría.

La clave de Jackett se envía como parámetro de consulta por diseño de su API. Los errores deben sanearse para evitar que esa clave aparezca en logs o excepciones.

### Pruebas

Se cubrieron:

- Parseo Torznab.
- Configuración ausente.
- Errores HTTP sin filtrado de secretos.
- XML mal formado.
- Autenticación qBittorrent.
- Consulta de torrents y filtrado por hash.
- Campos multipart de alta.
- URL inválida.
- Respuesta de confirmación inesperada.

Validaciones comunicadas:

- `make backend-test`: 56 pruebas superadas.
- `make backend-lint`: correcto.
- `git diff --check`: correcto.
- Árbol de trabajo limpio tras el commit.

Commit local:

`c51f3b7 Añadir clientes HTTP de Jackett y qBittorrent`

## Entregable 3 — Modelo Descarga y migración

**Estado: cerrado.**

Archivos modificados:

- `backend/app/models.py`
- `backend/migrations/versions/0004_descarga.py`
- `backend/tests/test_models.py`

Se añadió el modelo SQLModel `Descarga`, relacionado mediante clave foránea con `Solicitud`.

Campos persistidos:

- Identificador y solicitud asociada.
- Hash del resultado y hash asignado por qBittorrent.
- Título e indexador.
- Estado de descarga.
- Progreso entre 0 y 1.
- Tamaño en bytes.
- Último error.
- Fechas de creación y actualización.

Restricciones e índices:

- Estados limitados a `seleccionada`, `enviada`, `descargando`, `pausada`, `completada` y `fallida`.
- Progreso entre 0 y 1.
- Tamaño no negativo cuando está informado.
- Índices por solicitud y estado.
- Índice único parcial para `info_hash` no nulo.

No se añadió una relación directa con `Medio`: la disponibilidad sigue dependiendo de Jellyfin. Se permiten varias filas de descarga asociadas a una solicitud a lo largo del tiempo.

La migración `0004_descarga` depende de `0003_metadatos_tmdb`. Se aplicó durante el arranque de la API. Se verificaron la tabla, sus restricciones, índices y clave foránea en la base SQLite del contenedor.

### Pruebas y validaciones

- `make backend-test`: 64 pruebas superadas.
- `make backend-lint`: correcto.
- `git diff --check`: correcto.
- Alembic: `0004_descarga (head)`.
- API: arranque correcto y `/health` respondió `200 OK`.
- Worker: iniciado correctamente.

Se observaron dos advertencias de deprecación de Starlette que no provocaron fallos.

Commit local:

`dfb00f7 Añadir modelo y migración de descargas`

## Estado de la fase

| Entregable | Estado |
|---|---|
| 1. Configuración | Cerrado |
| 2. Clientes HTTP | Cerrado |
| 3. Modelo Descarga y migración | Cerrado |
| 4. Endpoint autenticado | Pendiente |
| 5. Procesador del worker | Pendiente |
| 6. Búsqueda y selección | Pendiente |
| 7. Envío y seguimiento qBittorrent | Pendiente |
| 8. Pruebas de resiliencia | Pendiente |

## Siguiente entregable

Diseñar e implementar el endpoint autenticado para crear solicitudes de descarga.

Antes de modificar código:

1. Inspeccionar los endpoints existentes y sus convenciones.
2. Revisar autenticación, autorización y resolución del perfil autenticado.
3. Revisar los modelos `Medio`, `Solicitud` y `Descarga`.
4. Revisar cómo se inserta trabajo en la cola durable y cómo se asignan prioridades.
5. Verificar las firmas reales de dependencias y funciones que intervengan.
6. Proponer el contrato HTTP, validaciones, respuestas y transacciones.
7. Presentar el diseño técnico para aprobación antes de modificar código.

No se debe empezar el procesador del worker ni adelantar los entregables posteriores.

## Límites de trabajo

- Trabajar en `inventario-trabajo-local`.
- No hacer push, PR ni merge a `main` sin autorización expresa.
- Un commit por entregable.
- Documentación, logs y mensajes de commit en español de España.
- No incorporar secretos ni archivos `.env`.
- No reabrir decisiones cerradas sin un ADR.

## Entregable 4 — Endpoint autenticado para crear solicitudes

**Estado: implementación y pruebas cerradas.**

Se implementó `POST /solicitudes`, que recibe `medio_id` (identificador interno de `Medio`) y exige un perfil autenticado.

Comportamiento:
- Devuelve 422 para identificadores inválidos.
- Devuelve 404 si el medio no existe o no está disponible en Jellyfin.
- Asocia la solicitud al perfil autenticado, sin permitir que el cliente elija el perfil.
- Persiste el identificador de Jellyfin y el título del medio.
- Mantiene los valores predeterminados del modelo: estado `pendiente`, prioridad 50, intentos 0 y máximo de intentos 5.
- No expone `jellyfin_item_id` en la respuesta.
- Devuelve 409 si ya existe una solicitud activa del mismo perfil para ese medio.
- Permite volver a solicitar medios con solicitudes fallidas y permite solicitudes de perfiles distintos.
- Serializa la comprobación e inserción mediante `BEGIN IMMEDIATE` en SQLite.

Archivos añadidos:
- `backend/app/solicitudes.py`
- `backend/tests/test_solicitudes.py`

Archivo modificado:
- `backend/app/main.py`

Validación:
- `make backend-lint`: correcto.
- `make backend-test`: 73 pruebas superadas.
- `git diff --check`: correcto.

Las pruebas cubren duplicados secuenciales; no se ha añadido una prueba específica de concurrencia HTTP.

**Siguiente entregable:** procesador del worker. Requiere acordar su diseño antes de implementarlo.

No se ha realizado push, PR ni merge a `main`.
