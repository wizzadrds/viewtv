# VIEWTV — Cohesión entre carátula TMDB y fuente de Jackett (0014)

**Fecha:** 22/11/2026, Europe/Madrid
**Rama única:** `viewtv-seguimiento-descargas-0012`; PR #2 debe permanecer OPEN/DRAFT.
**Prioridad:** segunda tarea, tras confirmar el propietario que `/tv.html` arranca en su televisión.
**Alcance:** búsqueda, validación de resultados y preservación de la identidad de la carátula. No modifica reproductor, torrents, medios, interfaz TV ni organizador Windows.

## Problema reproducido

El sistema anterior recuperaba variantes oficiales de una película desde TMDB, pero
`coincide_con_solicitud()` exigía que la publicación de Jackett **empezara con los
mismos tokens, en el mismo orden**, que la ficha o uno de sus alias. Esto
descartaba publicaciones correctas con las palabras reordenadas y no
conservaba el ID de TMDB al crear una solicitud desde `/descubrir/*/solicitar`.
Sin ID persistente, una película con nombre de remake podía quedar ambigua.

Se hizo un GET real read-only anterior a cambios:
- Ficha «Vengadores: Doomsday» 2026, TMDB ID 1003596, 6 alias oficiales.
- 4 búsquedas de Jackett; tres largas devolvieron cero, la búsqueda
  «Doomsday» dio 10 publicaciones, **0 coincidencias seguras**.
- Jackett respondía. No existía evidencia de fuente válida; no se
  crearon solicitudes, descargas ni se obtuvieron metadatos .torrent.

## Cambios implementados

### Persistencia de identidad exacta

- `backend/migrations/versions/0014_identidad_tmdb_solicitud.py` agrega
  `solicitud.tmdb_id` opcional e índice, sin borrar ni modificar las
  solicitudes antiguas. Alembic `0013 -> 0014`.
- `backend/app/models.py` incorpora ese campo.
- `backend/app/descubrir.py` pasa al servidor el ID exacto de la carátula
  tras el clic explícito en película o episodio. El identificador **no
  proviene de un campo libre enviado por el navegador**.
- `backend/app/solicitudes.py` usa el atributo privado Pydantic
  `_tmdb_id`, no inyectable por POST JSON, y guarda la identidad TMDB
  dentro de la operación transaccional de creación.
- En el worker se lee `tmdb_id` desde la cola. API y worker consultan
  las mismas variantes oficiales validadas para ese ID.

### Búsqueda de variantes y normalización

- `backend/app/titulo_cohesion.py` obtiene desde TMDB título en
  español, título original, traducciones ES/EN y títulos alternativos
  de mercados ES/US/GB/MX/AR, deduplicados, máximo 24 alias.
- Solicitud manual sin ID requiere una identidad TMDB **única**
  compatible con título/año; en remakes sin año, no se inventa alias.
- Máximo **6** consultas por película: título español con año,
  original con año, español sin año, original sin año,
  tercera variante y búsqueda corta del subtítulo. Las consultas
  sin año mejoran *descubrimiento*, no autorizan un candidato por sí solas.
- Los alias y títulos se normalizan a minúsculas sin tildes,
  puntuación ni artículos iniciales; `:` es separador de palabras.
- `backend/app/relevancia_resultado.py` compara conjuntos de tokens
  significativos, no un prefijo. Con 2 tokens exige 2; con 3 exige
  al menos 2; con 4 o más exige el 75 % (mínimo 3).
  **No acepta palabras sustantivas extra** fuera del alias oficial.
  Excluye etiquetas técnicas, tráileres y episodios ajenos.
- Año de película: cuando la ficha incluye año, el nombre ofrecido debe
  incluir **un solo año explícito y compatible ±1**. Sin año en fuente
  se falla cerrado, aunque eso descarte algunas publicaciones legítimas.
- Una solicitud de episodio exige coincidencia exacta de serie,
  temporada y episodio. Se rechazan S01E01 frente a S01E02,
  capítulos encadenados, packs y una serie ofrecida como película.
- Solicitud manual sin año con varios ID TMDB coincidentes:
  worker deja cero seleccionables y la API rechaza la elección
  con 409. Debe usarse la carátula o especificar un año inequívoco.
- Jackett puede proporcionar un mismo torrent por varios enlaces:
  `worker/processor.py` unifica infohash hexadecimal y base32
  de enlaces magnet, deduplicando antes del guardado.
- La API aplica el filtro de nuevo al **listar, verificar y
  seleccionar**; no delega la autorización solo en la búsqueda.

Los controles ya existentes de metainfo, propiedad y modo de
publicación no se han relajado ni habilitado. No se activan
descargas por explorar la carátula.

### Casos de regresión obligatorios

En `backend/tests/test_relevancia_resultado.py`,
`test_titulo_cohesion.py` y `test_cohesion_caratula_0014.py`:
- «Vengadores: Doomsday» ES y «Avengers: Doomsday» EN, incluso
  reordenado `Doomsday.Avengers`; **rechaza** «Doomsday» solo.
- Título con artículo inicial: «El padrino» y «The Thing».
- Título con dos puntos: «Capitán América: Civil War».
- Remake homónimo con distinto año: «The Thing» 1982 y 2011,
  rechazo de obra con fecha incompatible y de solicitud ambigua sin año.
- Secuela exacta «Toy Story 3» no confunde «Toy Story 2».
- Película vs episodio y S02E03 vs S02E02/packs.
- Duplicados de magnet/infohash; no guardar el mismo hash dos veces.
- Clic desde carátula guarda ID 1003596; el usuario no puede
  inyectarlo por JSON.
- Migración aditiva y reversible sin identidades vinculadas,
  con negativa explícita a quitar la columna si ya hay vínculos.

## Copias previas verificadas

1. Código y documentos:
   `/home/viewtv/viewtv-backups/cohesion-caratula-pre-20261122-220940.tar.gz`
   SHA-256 `8466086387539a4981e731298ef276d1f2005402b3079cc87ea70b746553ea59`.
   `tar -tzf`: **PASS**, incluye los archivos que ya existían antes
   de modificar, las migraciones 0001–0013, pruebas y BACKLOG.
2. SQLite producción, backup online consistente **anterior al despliegue**:
   `/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-222154.db`.
   SHA-256 `d2d8c409a94a269cdb8677e79534c4387fb954984565794fd1596ea1ad087117`.
   `SQLITE_BACKUP=OK`, `SQLITE_INTEGRITY=OK`, `SQLITE_FK=OK`;
   permisos 0600 root, no se imprimieron títulos ni perfiles.
3. Clon temporal de dicha copia, en Docker sin red:
   Alembic **0013 → 0014 → 0013 → 0014**, integridad y FK PASS
   antes y después, sin migrar la base real durante el ensayo.

## Pruebas y despliegue

- Tests focales búsqueda/API/solicitudes: **171/171 PASS**.
- Suite backend completa **1006/1006 PASS** con 2 advertencias
  de depreciación externas. Sin red ni SQLite/Jackett productivos.
- `ruff check --no-cache` de archivos afectados: **PASS**.
- Docker build offline de las dos imágenes 0014: **PASS**;
  Alembic `heads=0014_identidad_tmdb_solicitud` en ambas.
- El backup y el hash se verificaron de nuevo en el
  preflight `scripts/viewtv_cohesion_deploy_0014.sh check`.
  Compose JSON validado sin mostrar `TMDB_API_KEY`; iguales
  versiones de API y worker y banderas de envío/inicio globales `false`.
- Antes del cambio, SQLite `0013_cola_organizacion`, integridad/FK
  correctas, **0 solicitudes pendientes/procesándose y 0 descargas activas**.
- Despliegue limitado: solamente
  `docker compose up -d --no-deps --no-build --force-recreate api`
  y luego `worker`, con overlays actuales y `deploy/compose.cohesion-caratula-0014.yaml`.
  API migró de 0013 a **0014** antes de recrear worker.
- Imágenes resultantes:
  `viewtv:cohesion-caratula-api-0014` y
  `viewtv:cohesion-caratula-worker-0014`.
- Contenedores API/worker arrancados; API healthy.
  Frontend `viewtv-frontend:samsung-busqueda-0013` SIN recrear.
  Catalogador/Jellyfin/FlareSolverr/Windows y medios intactos.
- Postdespliegue: SQLite `0014_identidad_tmdb_solicitud`,
  integridad `ok`, FK `OK`, **0 solicitudes pendientes y
  0 descargas activas**. API `alembic current=0014`;
  worker `alembic heads=0014`.
- Smoke de producción solo GET: **10/10 PASS**, incluyendo
  permisos 401 y proxies. Un servicio sano NO equivale a
  comprobación funcional de todas las búsquedas.
- Prueba real de proveedores 0014: se documenta a continuación.

## Verificación real de Jackett con el worker 0014

El script `scripts/viewtv_cohesion_live_readonly_0014.py`
solo hace GET públicos al Jackett ya configurado. Nunca imprime
títulos de resultados, URLs, claves ni hashes, y nunca escribe SQLite.

**«Vengadores: Doomsday» (2026, TMDB 1003596):**
6 alias oficiales, 6 búsquedas, **10 resultados brutos**,
**0 coincidencias textuales con identidad/año**, **0 errores**.
La carátula **no ofrece otra película «Doomsday»**.
No es prueba de que la película solicitada esté disponible.

**«Ocho apellidos vascos» (2014):**
3 alias oficiales, 2 consultas GET al proveedor, **173 registros brutos**
y solo **3 coincidencias de nombre, tipo y año**; **0 errores**.
Esta contraprueba comprueba que el nuevo filtro no rechaza todas las
películas: recupera candidatos con una coincidencia de título/año,
pero **no confirma enlaces .torrent, derechos, identidad de vídeo ni
una descarga correcta**. No se guardó ni seleccionó ningún resultado.

## Plan de reversión

Se construyeron además imágenes `viewtv:cohesion-rollback-api-0014`
y `viewtv:cohesion-rollback-worker-0014` sobre las implementaciones
anteriores, pero **manteniendo el esquema 0014**. Así se puede revertir
la lógica sin borrar la columna `tmdb_id` ni perder nuevas solicitudes.

Preflight del rollback: `bash scripts/viewtv_cohesion_deploy_0014.sh check-rollback`
**PASS**, verifica el stack y permisos/servicios esperados.

Si el usuario comunica regresión crítica, ejecutar en la misma rama:
`bash scripts/viewtv_cohesion_deploy_0014.sh rollback`;
recrea **solo worker y API** con imágenes anteriores
compatibles con el esquema 0014. **No se ha ejecutado el rollback**
en producción; únicamente se ha comprobado su Compose. No usar
`git reset --hard`, `docker compose down -v` ni restaurar SQLite
salvo incidencia justificada y respaldo comprobado.

## Qué se hizo, qué se supuso, qué queda

**Hecho:** se enlaza la carátula con su identidad TMDB en nuevas
solicitudes, se amplían consultas y se cotejan tokens/temporada/año,
con protección contra ambigüedad. Código, pruebas y migración
desplegados; validación GET, metadatos y copia verificable.

**Supuestos y límites:** TMDB y Jackett pueden no tener datos
completos o una fuente identificable. El año del archivo publicado
es una señal textual, no un certificado del contenido. Los alias
oficiales y la verificación de metainfo restringen errores,
**no garantizan al 100 % correspondencia del vídeo ni que todas las
películas estén disponibles**. Los resultados sin año, aunque
parezcan legítimos, se descartan para carátulas con año. No se
inicia ninguna descarga para demostrar la búsqueda.

**Pendiente:** prueba funcional del propietario desde la PWA:
elegir una carátula distinta, pulsar «Descargar/Solicitar», comprobar
que «Buscar y pedir» solo ofrece fuentes correctas, revisar
metainfo de forma individual y no descargar títulos sin derecho
a obtenerlos. Si no hay fuente validada, informar que el proveedor
no la encontró sin mostrar resultados engañosos.

El propietario confirmó que el enlace Samsung `/tv.html` funciona,
pero desea una app instalable y un acabado profesional con carátulas
a color. Esa **siguiente tarea expresamente autorizada** se anotó
en `docs/BACKLOG.md`, sin tocar su implementación en este hito.
