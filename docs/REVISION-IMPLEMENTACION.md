# Revisión técnica de la implementación VIEWTV

## Alcance y referencia

Revisión estática y ejecución parcial de comprobaciones realizada sobre la rama
`inventario-trabajo-local`, con HEAD `197e605` (`Integrar documentación actual de main`).

Este documento complementa el inventario histórico de `docs/ESTADO.md`.
No sustituye las decisiones de `docs/CONTEXTO.md` ni los ADR aceptados.

La revisión no autoriza adelantar fases ni modificar decisiones arquitectónicas.

## Estado general

La rama contiene una implementación considerable de backend, worker y frontend.
La configuración de Docker Compose es válida sintácticamente y las pruebas
existentes del backend pasan.

Todavía no se considera verificada la instalación completa ni cerrada la fase 1.

## Entorno de desarrollo comprobado

- Sistema: Windows 11 con WSL2 Ubuntu 24.04.
- Repositorio: `~/projects/viewtv`.
- Python del entorno: 3.12.3.
- Entorno virtual: `backend/.venv`.
- Docker: 29.9.2.
- Docker Compose: v5.6.1.
- `docker compose config --quiet`: termina correctamente.
- No se ha realizado un arranque controlado de los servicios durante esta revisión.

El entorno virtual está dentro de `backend/`, no en la raíz del repositorio.
Los comandos Python deben utilizar `backend/.venv/bin/python` y Ruff
`backend/.venv/bin/ruff`.

## Backend

### Pruebas

Comando ejecutado:

    backend/.venv/bin/python -m pytest -v

Resultado:

- 40 pruebas recogidas.
- 40 pruebas superadas.
- 0 fallidas.
- Dos advertencias de deprecación procedentes de Starlette/httpx.

Las pruebas cubren autenticación, copias de seguridad, Jellyfin, catálogo,
imágenes, reproducción, modelos y cola.

### Ruff

Comando ejecutado:

    backend/.venv/bin/python -m ruff check backend/app backend/tests backend/scripts

Resultado: todas las comprobaciones superadas.

Nota: el workflow CI también debe revisarse para asegurar que incluye los
archivos del worker cuando corresponda.

### Compilación Python

Comando ejecutado:

    backend/.venv/bin/python -m compileall -q backend/app backend/scripts worker

Resultado: falla en `worker/tmdb_enrichment.py`, línea 103, por
`IndentationError: unexpected indent`.

La inspección del fragmento identifica dos líneas con indentación excesiva:

- `session.add(media)`
- `session.commit()`

Ambas pertenecen al caso en que el identificador TMDB no es válido.
Corrección pendiente de aplicar y verificar.

### Cola SQLite

La implementación revisada utiliza `BEGIN IMMEDIATE`, leases de 120 segundos,
heartbeat y renovación prevista cada 30 segundos, con control de propietario
y recuperación de leases caducados.

Los tests existentes validan exclusividad secuencial, recuperación de leases,
renovación, finalización, backoff y recuentos.

Pendiente: prueba de concurrencia real entre dos procesos o conexiones
independientes. Los tests actuales no acreditan por sí solos ese criterio.

## Frontend

### TypeScript

`npm run typecheck` falla en:

    frontend/components/viewtv-app.tsx:333

El valor pasado a `apiPath()` tiene tipo `string | null`, pero la función
requiere `string`.

El JSX comprueba previamente que exista `imagen_fondo` o `imagen_portada`,
pero TypeScript no conserva esa garantía al evaluar la expresión de `src`.

Corrección pendiente: estrechar el tipo sin alterar el comportamiento
ni introducir una URL vacía como solución funcional.

### ESLint

Comando ejecutado:

    npm run lint

Resultado: correcto.

### Build

`npm run build` compila inicialmente, pero falla en la fase de comprobación
de tipos por el mismo error de TypeScript descrito arriba.

También aparecen advertencias de Autoprefixer en `frontend/app/globals.css`
relativas al valor `end` en propiedades de alineación. No son la causa
del fallo del build y no se deben convertir en retoques visuales ajenos
al alcance.

## Docker y configuración

- `docker compose config --quiet` termina correctamente.
- Docker y Docker Compose están disponibles.
- Se identificó una imagen `viewtv:local` para la API.
- La salida de `docker compose images` mostró una entrada del worker sin
  repositorio ni tamaño identificable; no se considera verificada su imagen.
- No se ha probado el arranque completo ni el endpoint `/health`.

### Caché

La configuración permite `CACHE_DIR` y define una cuota de 80 GB.
Sin embargo, el volumen de Compose revisado monta una ruta host fija
`/mnt/c/VIEWTV/cache` en `/cache`.

Esto debe resolverse para respetar la ruta configurable y el entorno WSL,
sin cambiar la decisión arquitectónica de caché de 80 GB, TTL 48 horas
y política LRU.

## Modelos y migraciones

La revisión estática identificó modelos SQLModel y migraciones Alembic
ordenadas:

- `0001_initial`
- `0002_medio_disponible_en_jellyfin`
- `0003_metadatos_tmdb`

La estructura parece corresponder a los modelos actuales, pero todavía
no se ha validado mediante una base de datos temporal y `alembic upgrade head`.

No se ha ejecutado ninguna migración contra datos de usuario o producción.

## Worker

El worker actual programa un informe de estado de cola cada 30 segundos.
No reclama solicitudes ni ejecuta el ciclo operativo de heartbeat.

El archivo `worker/tmdb_enrichment.py` contiene el error de indentación
descrito anteriormente.

La integración del enriquecimiento TMDB con el ciclo del worker no debe
activarse como parte de esta corrección: es trabajo funcional distinto
y no debe adelantarse sin autorización y revisión de fase.

## CI y herramientas de proyecto

- Existe workflow de CI para backend y frontend.
- Backend CI ejecuta pytest y Ruff.
- Frontend CI ejecuta typecheck, lint y build.
- El trigger de push revisado incluye `main` y `feature/**`; los PR hacia
  `main` también están contemplados.
- La rama `inventario-trabajo-local` no está incluida en el trigger de push.
- El alcance de Ruff revisado no incluía `worker`.
- No existe Makefile.
- No existe archivo LICENSE; está pendiente incorporar MIT según el alcance
  de fase 1.

## Archivos auxiliares y secretos

Se identificaron cuatro archivos `.bak` versionados:

- `frontend/app/globals.css.antes-ficha-horizontal.bak`
- `frontend/app/globals.css.antes-horizontal.bak`
- `frontend/components/viewtv-app.tsx.antes-ficha-horizontal.bak`
- `frontend/components/viewtv-app.tsx.antes-horizontal.bak`

No se eliminan en esta revisión: su contenido es histórico y debe decidirse
su destino después de revisar diferencias y referencias.

`.env.example` contiene variables de credenciales con valores vacíos o
placeholders. No se identificó `.env` entre los archivos versionados
en la inspección realizada. Esto no equivale a una auditoría exhaustiva
de secretos de todo el historial Git.

## Decisiones de interfaz ya aceptadas

El ADR 0001 está aceptado: póster vertical 2:3 en todas las filas del catálogo.
La implementación está pendiente.

No se deben introducir cambios visuales para aplicar ese ADR dentro de esta
corrección técnica, ni modificar el diseño de detalle por inferencia.

## Lista de pendientes

1. Corregir indentación de `worker/tmdb_enrichment.py`.
2. Corregir el estrechamiento de tipo en `frontend/components/viewtv-app.tsx`.
3. Repetir compilación Python, pytest y Ruff.
4. Repetir typecheck, lint y build del frontend.
5. Validar migraciones en una base de datos temporal.
6. Probar reclamación concurrente de cola con procesos/conexiones independientes.
7. Revisar y corregir el montaje configurable de caché en Compose.
8. Verificar arranque de servicios y endpoint `/health`.
9. Revisar inclusión de worker en CI y cobertura de Ruff.
10. Incorporar Makefile y LICENSE MIT según el alcance de fase 1.
11. Revisar el destino de los cuatro `.bak`.
12. Completar la sección de fuentes de `docs/arquitectura.md`.

## Límite de esta revisión

No se han realizado cambios de código, migraciones, arranque de servicios,
instalaciones de dependencias ni commits como parte de la inspección.

Las correcciones se realizarán en entregables separados, con sus respectivas
comprobaciones y commits en la rama de trabajo. No se hará push ni merge a
`main` sin autorización expresa.

## Validación de migraciones Alembic

Se ha ejecutado una validación real de las migraciones sobre una base SQLite temporal, aislada de los datos de la aplicación.

**Procedimiento:**
- Se creó un directorio temporal bajo `/tmp`.
- Se exportó `DATABASE_URL` apuntando explícitamente a la base temporal. Esto evita utilizar la URL predeterminada `/data/viewtv.db`.
- Se ejecutó `alembic heads`, que identificó `0003_metadatos_tmdb` como revisión principal.
- Se ejecutó `alembic upgrade head` y se aplicaron correctamente las revisiones `0001_initial`, `0002_medio_disponible_en_jellyfin` y `0003_metadatos_tmdb`.
- Se ejecutó `alembic current` y se confirmó la revisión `0003_metadatos_tmdb`.
- Se inspeccionó el esquema SQLite y se encontraron las tablas `perfil`, `medio`, `solicitud` y `alembic_version`.
- Se comprobaron las columnas de las tres tablas de aplicación, incluidos los campos de disponibilidad Jellyfin, metadatos TMDB y gestión de leases de la cola.

**Resultado:** validación correcta. Las tres migraciones se aplicaron sin errores y el esquema resultante contiene las tablas y columnas esperadas.

El directorio temporal se configuró para eliminarse automáticamente al finalizar el procedimiento. No se modificó la base de datos de producción ni ningún archivo de datos de VIEWTV.

**Alcance:** esta prueba valida la cadena de migraciones sobre una base nueva. No demuestra todavía la compatibilidad con una base de datos preexistente ni la concurrencia real de la cola.

## Validación de reclamación concurrente de la cola

Se ha añadido una prueba de integración que comprueba la reclamación simultánea de una misma solicitud por dos procesos independientes.

**Procedimiento:**
- Se creó una base de datos SQLite temporal mediante `tmp_path`, aislada de la base de datos de la aplicación.
- Se insertó una única solicitud disponible.
- Se iniciaron dos procesos independientes mediante el contexto `spawn` de `multiprocessing`.
- Ambos procesos utilizaron conexiones y sesiones SQLite independientes.
- Una barrera sincronizó los procesos antes de llamar a `claim_next_request`.
- Se comprobaron los resultados devueltos por ambos procesos.

**Resultado:** la prueba `test_two_processes_cannot_claim_the_same_request` pasó. Exactamente uno de los procesos obtuvo el identificador de la solicitud y el otro obtuvo `None`. No se produjo una doble reclamación.

**Verificaciones:** las ocho pruebas de `tests/test_queue.py` pasaron; la suite completa pasó con 41 pruebas y Ruff terminó sin errores.

**Alcance:** esta prueba valida la exclusividad ante una reclamación simultánea concreta entre dos procesos sobre SQLite. No demuestra por sí sola la ausencia de cualquier otra condición de carrera ni sustituye pruebas adicionales de carga, recuperación o ejecución prolongada de workers. No se modificó la implementación de la cola.
