# VIEWTV — Revisión técnica de la implementación

## 1. Propósito y alcance

Este documento conserva las revisiones técnicas realizadas sobre VIEWTV, sus comprobaciones y los resultados obtenidos en cada momento.

Su contenido debe interpretarse teniendo en cuenta el commit y el estado del proyecto sobre los que se realizó cada revisión.

**Importante:** el diagnóstico inicial de este documento es histórico. Se realizó sobre un estado anterior del repositorio y no debe utilizarse como descripción automática del estado actual.

Este documento:

- Conserva los resultados de inspecciones y pruebas anteriores.
- Registra las limitaciones conocidas de cada comprobación.
- Permite consultar la evolución técnica del proyecto.
- No sustituye el estado actual de `docs/ESTADO.md`.
- No sustituye el plan de trabajo de `docs/FASE-2.md`.
- No modifica las decisiones arquitectónicas recogidas en `docs/CONTEXTO.md` ni los ADR aceptados.

Las correcciones y nuevas comprobaciones deben realizarse en tareas separadas y quedar documentadas con su referencia de código correspondiente.

---

## 2. Diagnóstico técnico histórico

### 2.1. Referencia de la revisión

La revisión inicial se realizó sobre:

- Rama: `inventario-trabajo-local`.
- HEAD: `197e605` (`Integrar documentación actual de main`).

Fue una revisión estática y una ejecución parcial de comprobaciones.

No se realizó una validación completa de la instalación ni un arranque controlado de todos los servicios.

### 2.2. Estado general observado entonces

En aquel momento, la rama contenía una implementación considerable de backend, worker y frontend.

Las comprobaciones realizadas indicaban:

- La configuración de Docker Compose era válida sintácticamente.
- Las pruebas existentes del backend pasaban.
- Ruff terminaba correctamente en el alcance comprobado.
- La compilación Python encontraba un error de indentación en el worker.
- El frontend tenía un error de tipos que impedía completar el build.
- No se había validado el arranque completo de los servicios.
- La fase 1 todavía no se consideraba cerrada en aquella revisión.

Estas conclusiones corresponden exclusivamente al estado `197e605`. No deben trasladarse al estado actual sin repetir las comprobaciones.

### 2.3. Entorno comprobado

En aquella revisión se registraron los siguientes datos:

- Sistema: Windows 11 con WSL2 Ubuntu 24.04.
- Repositorio: `~/projects/viewtv`.
- Python: 3.12.3.
- Entorno virtual: `backend/.venv`.
- Docker: 29.9.2.
- Docker Compose: v5.6.1.
- `docker compose config --quiet`: resultado correcto.

No se realizó un arranque controlado de los servicios durante aquella inspección.

Los comandos Python utilizados empleaban `backend/.venv/bin/python`, y Ruff se ejecutaba mediante `backend/.venv/bin/ruff`.

### 2.4. Backend: pruebas y Ruff

Comando ejecutado:

```bash
backend/.venv/bin/python -m pytest -v
```

Resultado histórico:

- 40 pruebas recogidas.
- 40 pruebas superadas.
- 0 fallidas.
- Dos advertencias de deprecación procedentes de Starlette/httpx.

Las pruebas cubrían autenticación, copias de seguridad, Jellyfin, catálogo, imágenes, reproducción, modelos y cola.

También se ejecutó:

```bash
backend/.venv/bin/python -m ruff check backend/app backend/tests backend/scripts
```

Resultado: todas las comprobaciones superadas en el alcance indicado.

La revisión señaló que debía comprobarse la inclusión del worker en el alcance de CI y de Ruff.

Estos resultados no representan el número actual de pruebas ni sustituyen las validaciones posteriores.

### 2.5. Compilación Python

En la revisión inicial se ejecutó:

```bash
backend/.venv/bin/python -m compileall -q backend/app backend/scripts worker
```

Resultado: error de indentación en `worker/tmdb_enrichment.py`, línea 103.

La inspección identificó indentación excesiva en:

- `session.add(media)`
- `session.commit()`

Ambas instrucciones pertenecían al caso en que el identificador TMDB no era válido.

La revisión registró la corrección como pendiente en aquel momento.

Este documento no acredita si esa incidencia se corrigió posteriormente. Para conocer el estado actual debe repetirse la compilación.

### 2.6. Cola SQLite

La revisión inicial identificó una implementación basada en:

- `BEGIN IMMEDIATE`.
- Leases de 120 segundos.
- Heartbeat.
- Renovación prevista cada 30 segundos.
- Control de propietario.
- Recuperación de leases caducados.

Los tests existentes validaban exclusividad secuencial, recuperación de leases, renovación, finalización, backoff y recuentos.

En aquella primera inspección se señaló la ausencia de una prueba de concurrencia real entre procesos o conexiones independientes.

Posteriormente se añadió una validación específica de reclamación concurrente, documentada en el apartado 4.

### 2.7. Frontend

En la revisión inicial, `npm run typecheck` fallaba en:

`frontend/components/viewtv-app.tsx:333`

El problema era el paso de un valor `string | null` a una función que requería `string`.

Se observó que la comprobación previa de `imagen_fondo` o `imagen_portada` no garantizaba el estrechamiento de tipo en la expresión de `src`.

También se registró:

- `npm run lint`: correcto.
- `npm run build`: fallaba en la comprobación de tipos por el mismo problema.

Aparecían advertencias de Autoprefixer en `frontend/app/globals.css`, relativas al valor `end` en propiedades de alineación.

Se indicó que esas advertencias no justificaban retoques visuales ajenos al alcance de la corrección.

Estas observaciones son históricas. No deben considerarse incidencias actuales sin repetir typecheck, lint y build.

### 2.8. Docker y configuración

La revisión inicial comprobó:

- `docker compose config --quiet`: correcto.
- Docker y Docker Compose disponibles.
- Existencia de una imagen `viewtv:local` para la API.
- Una entrada de worker sin repositorio ni tamaño identificable en la salida de `docker compose images`.

No se probó el arranque completo ni el endpoint `/health`.

#### Caché

En aquella revisión se observó que la configuración permitía `CACHE_DIR` y definía una cuota de 80 GB, pero el volumen de Compose montaba una ruta host fija:

`/mnt/c/VIEWTV/cache`

Se señaló la necesidad de revisar ese montaje para respetar la ruta configurable y el entorno WSL.

La observación no autorizaba a cambiar las decisiones de arquitectura de caché que estuvieran aprobadas.

No se afirma que esta incidencia continúe vigente. Debe comprobarse en la configuración actual antes de plantear cambios.

### 2.9. Modelos y migraciones

En la revisión inicial se identificaron estas migraciones:

- `0001_initial`
- `0002_medio_disponible_en_jellyfin`
- `0003_metadatos_tmdb`

La revisión estática no había validado todavía su aplicación mediante una base de datos temporal.

Posteriormente se realizó una validación real, documentada en el apartado 3.

### 2.10. Worker

En el estado inicial revisado, el worker programaba un informe de estado de cola cada 30 segundos.

No reclamaba solicitudes ni ejecutaba el ciclo operativo de heartbeat descrito en aquella revisión.

También se identificó el error de indentación de `worker/tmdb_enrichment.py`.

Se indicó que la integración del enriquecimiento TMDB con el ciclo operativo del worker debía mantenerse separada de aquella corrección técnica.

Esta descripción corresponde al estado histórico inspeccionado. El estado actual del worker debe determinarse mediante una inspección del código antes de diseñar el entregable 5 de fase 2.

### 2.11. CI y herramientas

En la inspección inicial se registró:

- Workflow de CI para backend y frontend.
- Backend CI con pytest y Ruff.
- Frontend CI con typecheck, lint y build.
- Trigger de push que incluía `main` y `feature/**`.
- PR hacia `main` contemplados.
- La rama `inventario-trabajo-local` no estaba incluida en el trigger de push revisado.
- El alcance de Ruff no incluía `worker`.
- No se encontró Makefile.
- No se encontró archivo LICENSE.

También se registró como pendiente incorporar MIT según el alcance de fase 1.

Estas observaciones no deben utilizarse como inventario actual sin revisar los workflows y archivos existentes.

### 2.12. Archivos auxiliares y secretos

En la revisión inicial se identificaron cuatro archivos `.bak` versionados:

- `frontend/app/globals.css.antes-ficha-horizontal.bak`
- `frontend/app/globals.css.antes-horizontal.bak`
- `frontend/components/viewtv-app.tsx.antes-ficha-horizontal.bak`
- `frontend/components/viewtv-app.tsx.antes-horizontal.bak`

No se eliminaron durante aquella revisión. Se dejó pendiente decidir su destino después de revisar sus diferencias y referencias.

También se observó que `.env.example` contenía variables de credenciales con valores vacíos o placeholders.

No se identificó `.env` entre los archivos versionados inspeccionados. Esto no equivalía a una auditoría exhaustiva de secretos de todo el historial Git.

No se debe eliminar ni modificar ningún archivo auxiliar sin revisar previamente su contenido, historial y posibles referencias.

---

## 3. Validación histórica de migraciones Alembic

Posteriormente se ejecutó una validación real de las migraciones sobre una base de datos SQLite temporal, aislada de los datos de la aplicación.

### Procedimiento

- Se creó un directorio temporal bajo `/tmp`.
- Se exportó `DATABASE_URL` apuntando explícitamente a la base temporal para evitar utilizar la URL predeterminada `/data/viewtv.db`.
- Se ejecutó `alembic heads`.
- Se identificó `0003_metadatos_tmdb` como revisión principal.
- Se ejecutó `alembic upgrade head`.
- Se aplicaron correctamente `0001_initial`, `0002_medio_disponible_en_jellyfin` y `0003_metadatos_tmdb`.
- Se ejecutó `alembic current`.
- Se confirmó la revisión `0003_metadatos_tmdb`.
- Se inspeccionó el esquema SQLite.

Se encontraron las tablas `perfil`, `medio`, `solicitud` y `alembic_version`.

También se comprobaron columnas de las tablas de aplicación, incluidos los campos de disponibilidad Jellyfin, metadatos TMDB y gestión de leases de la cola.

### Resultado

La validación fue correcta: las tres migraciones se aplicaron sin errores y el esquema resultante contenía las tablas y columnas esperadas.

El directorio temporal se configuró para eliminarse automáticamente al finalizar el procedimiento.

No se modificó la base de datos de producción ni ningún archivo de datos de VIEWTV.

### Limitaciones

Esta prueba valida la cadena de migraciones sobre una base nueva.

No demuestra:

- Compatibilidad con todas las bases de datos preexistentes.
- Seguridad de una migración sobre datos reales.
- Ausencia de problemas en cualquier escenario de actualización.
- El estado de las migraciones incorporadas posteriormente.

En particular, esta validación histórica terminó en `0003_metadatos_tmdb`. Posteriormente se incorporó la migración `0004` correspondiente al modelo de descargas. No debe confundirse esta prueba con una validación de toda la cadena actual.

---

## 4. Validación histórica de reclamación concurrente de la cola

Se añadió una prueba de integración para comprobar la reclamación simultánea de una misma solicitud por dos procesos independientes.

### Procedimiento

- Se creó una base de datos SQLite temporal mediante `tmp_path`.
- Se insertó una única solicitud disponible.
- Se iniciaron dos procesos independientes mediante el contexto `spawn` de `multiprocessing`.
- Ambos procesos utilizaron conexiones y sesiones SQLite independientes.
- Una barrera sincronizó los procesos antes de llamar a `claim_next_request`.
- Se comprobaron los resultados devueltos por ambos procesos.

### Resultado

La prueba `test_two_processes_cannot_claim_the_same_request` pasó.

Exactamente uno de los procesos obtuvo el identificador de la solicitud y el otro obtuvo `None`.

No se produjo una doble reclamación.

### Verificaciones registradas

- Las ocho pruebas de `tests/test_queue.py` pasaron.
- La suite completa pasó con 41 pruebas.
- Ruff terminó sin errores.

### Limitaciones

La prueba valida la exclusividad ante una reclamación simultánea concreta entre dos procesos sobre SQLite.

No demuestra por sí sola:

- La ausencia de cualquier otra condición de carrera.
- El comportamiento bajo carga prolongada.
- La recuperación de todos los escenarios de fallo.
- La correcta ejecución de un ciclo completo de workers.

La validación no modificó la implementación de la cola.

---

## 5. Relación con el estado actual del proyecto

Las revisiones anteriores describen estados históricos del repositorio.

Para conocer el estado vigente deben consultarse las fuentes actuales:

- `docs/ESTADO.md`: situación de la rama, entregables cerrados y siguiente trabajo.
- `docs/FASE-2.md`: planificación y seguimiento de los entregables de fase 2.
- `docs/CONTEXTO.md`: decisiones, arquitectura aprobada y criterios de trabajo.
- `docs/arquitectura.md`: estructura y relaciones entre componentes.
- Los ADR aceptados: decisiones técnicas formalizadas.

A fecha de la actualización documental del 15 de noviembre de 2026, la fase 1 está cerrada y la fase 2 tiene cerrados sus cuatro primeros entregables.

Los entregables cerrados de fase 2 son:

1. Configuración de servicios de descarga.
2. Clientes HTTP de Jackett y qBittorrent.
3. Modelo de descarga y migración.
4. Endpoint autenticado de solicitudes.

El siguiente trabajo es el entregable 5: procesador de solicitudes en el worker.

La existencia de clientes HTTP, modelos y endpoint no significa que el flujo completo de búsqueda, selección, envío y seguimiento de descargas esté terminado.

Antes de implementar el procesador se debe inspeccionar el worker actual, revisar la persistencia y acordar el diseño técnico.

---

## 6. Criterios para futuras revisiones

Toda revisión nueva debe identificar claramente:

1. Fecha de realización.
2. Rama revisada.
3. Commit exacto.
4. Alcance de la inspección.
5. Comandos ejecutados.
6. Resultado de cada comprobación.
7. Incidencias encontradas.
8. Limitaciones de las pruebas.
9. Archivos modificados, si los hubiera.

No se debe presentar como actual un resultado obtenido sobre un commit antiguo.

No se debe afirmar que una incidencia está corregida sin una comprobación posterior que lo demuestre.

Las pruebas sobre bases temporales deben identificar expresamente la base utilizada y evitar cualquier conexión accidental con datos reales.

Las pruebas de integración y concurrencia deben indicar qué escenario concreto validan y qué escenarios quedan fuera de su alcance.

---

## 7. Límites y precauciones

Las revisiones técnicas no autorizan por sí mismas:

- Adelantar entregables o fases.
- Modificar decisiones arquitectónicas aceptadas.
- Alterar estilos, portadas o componentes visuales.
- Eliminar archivos auxiliares sin revisar su contenido.
- Ejecutar migraciones sobre datos reales sin autorización y procedimiento aprobado.
- Publicar secretos, credenciales, archivos `.env` o bases de datos locales.
- Cambiar de rama, hacer push, crear PR o fusionar a `main`.

Cada corrección debe realizarse en un entregable separado, con comprobaciones adecuadas y documentación coherente.

No se hará push ni merge a `main` sin autorización expresa.
