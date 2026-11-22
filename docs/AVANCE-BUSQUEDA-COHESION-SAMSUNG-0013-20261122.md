# VIEWTV — cohesión de búsquedas con TMDB y modo compatible Samsung

**Fecha:** 22 de noviembre de 2026 · Europe/Madrid
**Equipo autorizado:** LAPTOP-V2QSMC01 · Windows 11 / WSL Ubuntu 24.04 / Docker Desktop
**Árbol de desarrollo:** `/home/viewtv/projects/viewtv-broker-0013-20261119`
**Rama exclusiva:** `viewtv-seguimiento-descargas-0012`
**PR #2:** abierta y en borrador; no fusionada.

## Solicitud del propietario

1. Los títulos de fichas TMDB (por ejemplo,
   **«Vengadores: Doomsday»**) no daban resultados
   porque Jackett indexa con títulos originales,
   nombres traducidos distintos y etiquetas de publicación.
   Buscar solo «Doomsday» mostraba resultados genéricos;
   **no se debe asociar otro largometraje a esa carátula**.
2. En el navegador **Samsung Smart TV** la ruta
   `http://192.168.1.138:3000` mostraba
   «Iniciando VIEWTV…» indefinidamente.
   El propio usuario verificó un PowerShell HTTP 200
   tras habilitar portproxy/firewall de Wi-Fi privada.
3. Mantener actualizaciones de TV y PC desde el
   servidor común, sin descargar ni reiniciar media.

## Diagnóstico: Jackett y TMDB

- Los tres indexadores configurados son
  `divxtotal`, `dontorrent` y `mejortorrent`.
  Sus capacidades Torznab admiten búsqueda de
  películas y series (validado en el hito anterior).
- Se comprobó que el proceso **API** tenía
  `TMDB_CONFIGURADA=True`, pero el **worker**
  todavía informaba `WORKER_TMDB_CONFIGURADA=False`
  porque llevaba ejecutándose desde antes de
  que el usuario editara `.env`.
  La configuración Docker nueva recrea el worker
  con `TMDB_API_KEY` del fichero privado.
  Después: **`WORKER_TMDB_CARGADA=True`**,
  verificado únicamente como booleano.
- La IP Wi-Fi `192.168.1.138:3000` ya funciona
  tras el comando del usuario:
  `GET /` HTTP 200,
  `GET /api/viewtv/auth/profiles` HTTP 200,
  `GET /api/viewtv/auth/me` HTTP 401 sin
  iniciar sesión (correcto),
  `GET /api/app-version` HTTP 200.
  **No se atribuye el bloqueo a la red**;
  parece un problema de arranque/hidratación
  React o compatibilidad JavaScript del navegador
  Samsung, pero la causa exacta **no se pudo
  demostrar sin acceso físico a la televisión**.

### Prueba real del caso «Vengadores: Doomsday»

Solo se consultaron **metadatos**, sin descargar
ningún torrent o vídeo ni crear solicitudes:

- `TMDB search/movie` resolvió la película
  con **ID 1003596**, estreno de **2026**.
- TMDB devolvió **6 títulos oficiales**,
  incluyendo las versiones «Vengadores» y
  «Avengers»; no se inventó el ID.
- El nuevo worker calculó **4 consultas
  controladas** a Jackett, incluyendo los
  nombres oficiales y la búsqueda breve
  `Doomsday`.
- Los resultados brutos de las tres
  búsquedas largas fueron **0**. La búsqueda
  breve ofreció **10 resultados**; ninguno
  coincidió con el filme por título oficial
  y fecha. Resultado final **0 coincidencias
  válidas**, evitando ofrecer otra película.
- Se verificó que el worker **no inició
  descargas** ni guardó torrents en esta prueba.

**Interpretación:** ya no se pierden títulos por
usar solo el nombre traducido, pero el sistema
no puede garantizar una fuente de vídeo que
los indexadores no tengan o no identifiquen.
Es una mejora de búsqueda, no un bypass de
licencias ni de derechos de reproducción.

## Nueva búsqueda conservadora y multilingüe

### `backend/app/titulo_cohesion.py`

1. Identifica el título solicitado mediante
   `TMDBClient.search(tipo,titulo)`; para
   episodios separa el código `S01E02`
   al buscar la serie matriz.
2. Acepta **una única identidad TMDB**
   cuando el nombre local/original coincide
   exactamente después de normalizar
   tildes, signos y espacios, y el año
   declarado coincide con el conocido.
   No enlaza fichas ambiguas o adultas.
3. Consulta la ficha oficial con
   `append_to_response=translations,alternative_titles`
   en **una petición adicional** (se conservan
   únicamente traducciones español/inglés
   y títulos alternativos de mercados
   controlados).
   Referencia oficial:
   https://developer.themoviedb.org/docs/append-to-response
4. Genera un máximo de **4 búsquedas de Jackett**
   por solicitud: título local, título original,
   otros equivalentes y, si es relevante,
   una búsqueda breve por subtítulo.
   Reserva una consulta para esta última
   **aunque haya muchas traducciones**.
   El subtítulo sirve solo para **descubrir
   candidatos**, jamás como evidencia suficiente
   para seleccionar.
5. Si TMDB falla, no inventa traducciones:
   busca únicamente el título inicial.
   `lru_cache` limita a 512 resoluciones en
   memoria por proceso para evitar sobrecargar
   TMDB en las lecturas de resultados.

### `backend/app/relevancia_resultado.py`

- `coincide_con_solicitud(..., aliases=())`
  conserva el filtro anterior y acepta las
  variantes oficiales validadas.
- Sigue comprobando el **año** cuando
  aparece en el nombre del resultado.
- Rechaza películas distintas que
  empiezan por las mismas palabras:
  «El secreto de otros» no corresponde a
  «El secreto».
- Tras el título solo admite un año
  o etiquetas típicas de resolución,
  códec, idioma/edición, y rechaza
  trailers, teasers o samples.
- Sigue impidiendo confundir episodios
  `S01E01` y `S01E02`, o confundir
  un pack con una solicitud individual.
- Mantiene soporte para solicitudes
  **históricas** de serie sin episodio
  concreto, sin modificar las autorizaciones
  de publicación NTFS.

### Worker y API

- `worker/processor.py` realiza las búsquedas
  acotadas, deduplica por identidad de
  resultado y solo guarda las que pasan
  el filtro final por alias/año/episodio.
  No inicia descargas por buscar.
- La API `backend/app/solicitudes.py`
  verifica **las mismas variantes oficiales**
  cuando lista resultados, consulta la
  verificación y acepta una selección.
  Obtiene los alias **antes de bloquear SQLite**
  con `BEGIN IMMEDIATE`; conserva
  comprobación contra cambios del resultado
  y validación del metainfo.
- El identificador TMDB se resuelve
  dinámicamente por título y año:
  **no se añadió aún una columna
  permanente `solicitud.tmdb_id`**.
  Una fase futura podrá fijar el ID en
  solicitudes nuevas con migración
  controlada. No se modificó Alembic.

## Samsung TV: solución compatible sin React

Samsung documenta capacidades Web diferentes
según su generación de Tizen y navegador:
https://developer.samsung.com/smarttv/develop/specifications/web-engine-specifications.html

### Ruta alternativa desplegada

**`http://192.168.1.138:3000/tv.html`**

- `frontend/public/tv.html`: página
  autónoma HTML/JavaScript ES5 con
  **`XMLHttpRequest`**, sin React, promesas,
  `fetch`, imports ni código JavaScript moderno.
- Usa **el mismo servidor**, API y cookies
  que el ViewTV del ordenador; nunca copia
  una base de datos ni almacena claves localmente.
- Login con perfiles y PIN, explorar
  categorías y carátulas, abrir fichas de
  películas/series, elegir temporadas y
  consultar capítulos sin crear solicitudes
  por accidente.
- Navegación con teclas del mando
  (flechas, selección, Escape/Back donde
  se interpreten); diseño de alto
  contraste y texto grande.
- «Biblioteca» y **reproducción de un
  medio local** mediante fuente directa
  o HLS ofrecida por Jellyfin. No incluye
  `hls.js`: depende del códec y soporte
  nativo del navegador Samsung. No se
  ha comprobado aún imagen/sonido con TV real.
- Consulta `/api/app-version` cada minuto;
  permite recarga al pulsar «Actualizar
  ahora» y sin interrumpir reproducción.
- La portada moderna `frontend/components/viewtv-app.tsx`
  muestra un enlace estático «Abrir
  versión compatible con Samsung» en
  su pantalla de carga y otro en errores
  de login. También utiliza un timeout
  de **10 segundos** en las comprobaciones
  iniciales de sesión y perfiles para evitar
  una pantalla de carga infinita si la
  petición queda bloqueada.
- Se mantiene ViewTV completo con React/Next
  para PC y navegadores Samsung compatibles.
  La ruta `/tv.html` es alternativa, no
  reemplaza la PWA principal.
- El modo compatible, por seguridad, no
  incluye botones de descarga/selección
  de torrents; las solicitudes se hacen
  desde la PWA completa en PC/móvil.
- Toda actualización de código debe
  **construirse y desplegarse** en el
  servidor; hacer únicamente `git push`
  no cambia lo que ve la televisión.

### Estado real de la LAN

- `GET http://192.168.1.138:3000/tv.html`
  HTTP **200** con documento Samsung esperado.
- `GET /api/app-version` HTTP **200**;
  `GET /api/viewtv/auth/profiles` HTTP **200**.
- El puerto está accesible por la IP Wi-Fi
  privada tras la configuración del propietario;
  **no se modificaron el firewall ni el router**
  durante este hito.
- Todavía **no** se ha probado físicamente
  el navegador Samsung real ni su códec.
  El propietario debe probar esa URL en
  su televisor y decir en qué pantalla
  progresa. Para diagnóstico exhaustivo
  indicar modelo/año de Samsung y versión Tizen.

## Pruebas, cambios en producción y protección

- Suite completa backend definitiva: **978/978 PASS**,
  incluidos seis alias con una búsqueda reservada
  para «Doomsday» y pruebas de flujo API-worker.
  Solo dos avisos de depreciación conocidos.
  Los casos focales de búsqueda y worker:
  **48/48 PASS** antes de la última prueba
  adicional; repetidos tras el ajuste.
- Ruff **PASS** para archivos cambiados.
- TypeScript + ESLint frontend **PASS**.
- `docker build` para API, worker y
  frontend **PASS**, compilación Next.js
  de producción completada.
- `scripts/viewtv_tv_samsung_static_validate_0013.py`
  comprobó HTML, API base, sintaxis
  JavaScript con `node --check`, y
  ausencia de `fetch`, React y promesas
  en el modo compatible: **PASS**.
- Compose nuevo y anterior verificados
  por `scripts/viewtv_busqueda_samsung_compose_verify_0013.py`.
  **TMDB_API_KEY presente en API y worker**
  de forma privada y con la misma longitud
  esperada (32 hex); jamás se imprimió.
- Se pausó momentáneamente la tarea
  Windows `VIEWTV - Publicador automatico 0013`
  tras verificar nivel **Limited**,
  sesión **Interactive**, resultado 0
  y política `general after_id=3`.
  Después se reactivó y arrancó
  nuevamente, conservando la política.
- Solo se recrearon **API, worker y
  frontend**. Jellyfin, FlareSolverr
  y catalogador TMDB permanecieron
  intactos. Las imágenes resultantes son:
  `viewtv:busqueda-tmdb-api-0013`,
  `viewtv:busqueda-tmdb-worker-0013`,
  `viewtv-frontend:samsung-busqueda-0013`.
- Smoke HTTP de producción **10/10 PASS**
  tras despliegue, con sesiones
  protegidas 401 y Jellyfin healthy.
- No se inició descarga, ni se modificaron
  datos de los torrents, SQLite de
  producción, Alembic o `C:\VIEWTV\media`.
  Botón «Desinstalar» sigue deshabilitado.

### Backups previos verificados

Código y documentación:
`/home/viewtv/viewtv-backups/busqueda-tv-samsung-pre-20261122-212900.tar.gz`,
SHA-256:
`cc59447a78b671f5b8721481251fe7828602bf6445e5b129302d95cdf7b8a721`.
Hash comprobado de nuevo por `sha256sum`
antes de documentarlo.

Base SQLite principal, copia online íntegra:
`/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-214500.db`,
SHA-256:
`0a14cb50800b8fc99a0b10711192b8ae9e31db4c3a63e8a6c8cf2951f8279c5a`,
integrity `ok`, FKs `ok`.
**No se restauró ni modificó la base.**

## Reversión y pendientes

Antes de revertir, pausar la tarea Windows
con los mismos controles de identidad y
política. Ejecutar
`bash scripts/viewtv_busqueda_samsung_deploy_0013.sh rollback`
para volver a **las tres imágenes previas**,
sin borrar volúmenes ni SQLite. Comprobar
los servicios y reactivar la tarea limitada.
No usar `docker compose down -v`.

Pendientes de validación por el propietario:

1. En Samsung abrir directamente
   `http://192.168.1.138:3000/tv.html`,
   elegir perfil e introducir PIN.
2. Probar cruceta del mando, abrir
   series/temporadas y biblioteca;
   comprobar reproducción de una
   película local con derechos,
   imagen, sonido, pausa y vuelta.
3. Indicar **modelo/año Samsung**
   y, si falla, pantalla exacta.
4. Futuro: vincular ID TMDB
   de forma persistente con solicitud,
   añadir diagnóstico y ordenar
   fuentes verificadas con más detalle;
   probar en sandbox antes de autorizar
   publicación automática de episodios
   o escrituras NTFS.
