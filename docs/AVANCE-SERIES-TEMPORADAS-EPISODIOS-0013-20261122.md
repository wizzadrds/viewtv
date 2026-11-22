# VIEWTV — fichas de series con temporadas y episodios seleccionables

**Fecha:** 22/11/2026, Europe/Madrid
**Equipo autorizado:** `LAPTOP-V2QSMC01` · WSL Ubuntu 24.04
**Worktree:** `/home/viewtv/projects/viewtv-broker-0013-20261119`
**Rama:** `viewtv-seguimiento-descargas-0012`
**PR #2:** abierta y en borrador, sin fusionar.

## Objetivo de producto

Una serie debe representarse mediante **una sola ficha y carátula**
en los estantes de descubrimiento (no una tarjeta por capítulo).
Al entrar en ella el usuario debe poder navegar por **temporadas,
especiales y episodios**, consultar fotograma, sinopsis, estreno
y duración, y pedir **solo el capítulo elegido**.

Abrir fichas y temporadas nunca descarga vídeo. La acción
«Solicitar episodio» es una acción explícita distinta, que crea
**una solicitud, no un torrent**; la fuente debe elegirse en
«Buscar y pedir» según el circuito ya autorizado.

## Implementación efectuada

### API: temporadas verificadas de TMDB

`backend/app/tmdb.py` añade
`TMDBClient.season_details(tmdb_id, season_number)`.
Consulta exclusivamente el endpoint público de metadatos
`GET /3/tv/{series_id}/season/{season_number}`, con
IDs de serie y temporada validados, sin rutas arbitrarias
ni reproducción. Referencia oficial:
https://developer.themoviedb.org/reference/tv-season-details

`backend/app/descubrir.py` devuelve
`temporadas` en el detalle normal de una serie
`GET /descubrir/serie/{id}`. Incluye especiales
temporada 0 y temporadas numeradas, conteo de
episodios y portada de temporada validada.

Nuevo endpoint autenticado:
`GET /descubrir/serie/{id}/temporadas/{n}?pagina=p`.
Confirma que el proveedor reconoce **la serie y
esa temporada**, valida respuesta coincidente y
devuelve los episodios **40 por página**, hasta
40 páginas para cubrir temporadas extensas.
Cada episodio tiene número, título, sinopsis,
imagen `image.tmdb.org` validada, duración,
estreno y `solicitable`.

Los episodios con fecha futura no se pueden
solicitar; si TMDB no publica la fecha se muestra
«Estreno no confirmado», sin prometer disponibilidad.
No se crean registros en SQLite al consultar.

### API: solicitudes de episodio, nunca de serie completa

Nuevo endpoint autenticado, únicamente con POST:

`POST /descubrir/serie/{id}/temporadas/{n}/episodios/{e}/solicitar`.

El servidor vuelve a consultar metadatos de TMDB
y valida que la temporada pertenezca a la serie
y el capítulo exista y no esté marcado como futuro.
Genera **una sola solicitud** del modelo existente
con `tipo_medio=serie`, `anio=null` y título
normalizado **`Nombre de serie S01E02`**,
por ejemplo. El título del capítulo de TMDB solo
aparece como metadato de respuesta, no se utiliza
para construir rutas de disco.

Clics repetidos sobre una misma solicitud activa
devuelven 409, sin duplicación. Se permite pedir
otros capítulos de una serie presente en Jellyfin,
porque su presencia **no demuestra temporada completa**.

Se elimina la peligrosa solicitud ambigua de
**«descargar serie» sin capítulo** desde el endpoint
heredado `POST /descubrir/serie/{id}/solicitar`:
ahora responde 422 e invita a escoger temporada
y episodio. La solicitud de películas sigue igual.

### Coincidencia conservadora de fuentes

`backend/app/relevancia_resultado.py` valida
el código solicitado `SxxEyy` contra el título
de la fuente ofrecida, incluyendo temporadas
de tres cifras. Rechaza otro episodio,
otra temporada o anuncios con **dos códigos
de episodio** que pudieran ser packs ambiguos.
Esto conserva la comprobación existente para
películas y solicitudes históricas de series.

**Límite de seguridad explícito:** la coincidencia
de los títulos del proveedor no es todavía
verificación del nombre/contenido de cada archivo
`.torrent`. Esa verificación individual debe
completarse antes de habilitar publicación
automática de episodios en NTFS real.

### Interfaz: una carátula por serie

Se mantiene la ficha de serie única por ID de
TMDB en los carruseles; **no se añaden episodios
como entradas de catálogo ni al contador TMDB**.

Nuevo componente
`frontend/components/series-season-picker.tsx`:
selector horizontal de temporadas y especiales,
resumen de la temporada, episodios con miniatura
16:9, número, nombre, duración y fecha,
paginación «Ver más episodios»,
indicador «Próximamente» para episodios futuros,
botón individual «Solicitar episodio» y enlace
a solicitudes para elegir fuente autorizada.

El componente añade controles accesibles por
cruceta (`data-spatial`), estados de carga,
mensajes de error y respuesta, manejo de
peticiones canceladas al cambiar de temporada
y deshabilita el capítulo solicitado durante
la misma sesión.

`frontend/components/discover-panel.tsx` deja
de mostrar «Descargar» genérico para series,
integra el selector dentro de la ficha con
más altura y desplazamiento vertical,
y mantiene películas sin cambios.

Para una serie local identificada de manera
segura con TMDB, también permite abrir temporadas
y ofrece enlace separado a su biblioteca.
Advierte que todavía **no se han verificado
los episodios realmente almacenados**.
Si una serie local no está enlazada con TMDB,
se mantiene la navegación tradicional a
la biblioteca, sin inventar ID de serie.

`frontend/app/globals.css` añade la presentación
cinematográfica de temporadas y capítulos
con diseño adaptable a móvil y pantalla de TV,
tipografía, foco y `prefers-reduced-motion`.

## Límite funcional que NO se ha cambiado

`worker/organization_planner.py` ya conoce
las rutas de serie y temporada
(`Series/<Serie>/Temporada XX`), pero
**`worker/organization_windows_authority.py`
limita explícitamente el publicador real a
`library == "Peliculas"`**. Por seguridad, la
autorización de publicación automática de series
sobre los archivos NTFS no se ha ampliado aquí.

Consecuencia: la **navegación y creación de
solicitudes individuales están operativas**,
pero esta intervención **NO garantiza** que,
tras elegir una fuente de episodio,
el publicador Windows inserte automáticamente
ese capítulo en Jellyfin. El sistema tampoco
conoce aún con precisión qué capítulos de una
serie local están ya descargados ni ofrece
reproducción por episodio desde la nueva ficha.

El siguiente desarrollo deberá probar el broker
de publicación de capítulos **solo en sandbox**,
validar nombres reales dentro del torrent,
propiedad/hardlinks, destinos por serie/temporada,
no sobrescritura y reproducción en Jellyfin.
**No se ha tocado `C:\VIEWTV\media` ni
se han creado torrents en este hito.**
El botón «Desinstalar» sigue deshabilitado.

## Pruebas ejecutadas y resultados

- Tests focales de descubrimiento, TMDB y
  relevancia de resultados: **75/75 PASS**.
  Incluyen capítulos futuros, temporadas inválidas,
  paginación, deduplicación de solicitudes, serie
  con medios locales, show adulto, y fuente
  `S01E02` distinta de `S01E01`.
- Suite backend completa **970/970 PASS**,
  2 avisos antiguos deprecados.
- Ruff **PASS**, TypeScript **PASS**, ESLint
  **PASS**, Next.js Docker `npm run build`
  **PASS** con Next 15.5.
- Consulta pública real de TMDB de solo metadatos
  en contenedor existente: serie de prueba pública
  (ID 1396) con **6 temporadas** y **7 episodios
  en temporada 1**; sin POST ni descarga.
- Validación de Compose nuevo y anterior:
  **PASS**. API y frontend nuevos:
  `viewtv:series-episodios-api-0013`
  y `viewtv-frontend:series-episodios-0013`.
  Se recrearon **solo API y frontend**.
  `viewtv-worker-1`,
  `viewtv-catalogador-1`,
  Jellyfin y FlareSolverr intactos.
- Prueba de lectura en API real, TestClient en
  proceso aislado sin alterar autenticación
  del servidor: ficha con temporadas HTTP 200,
  temporada y episodios reales HTTP 200,
  acceso sin sesión 401, páginas de temporada
  hasta 40, página 41 rechazada 422,
  carrusel de series HTTP 200,
  protección por código de episodio verificada.
- Smoke general de producción **10/10 PASS**;
  frontend, API y Jellyfin healthy.
- Catálogo de fichas TMDB persistentes intacto
  durante la prueba: **1.428 fichas** (cifra
  observada, cambia tras nuevas tandas).
- La tarea Windows «VIEWTV - Publicador
  automatico 0013» se pausó temporalmente
  durante cada recreación de API,
  conservó nivel **Limited**, `general after_id=3`,
  se reactivó y se comprobó nuevamente.
- No se modificó esquema Alembic ni contenido
  de la biblioteca SQLite de producción.

### Copias previas verificadas

Código y documentación previa:
`/home/viewtv/viewtv-backups/viewtv-series-temporadas-pre-20261122-203500.tar.gz`
SHA-256:
`bb35adad9accf33b7940a29e35639f0c2d9e8e90410198dfc7d72b8de239ae8b`.
Contenido comprobado por `tar -tzf`.

SQLite principal (backup online, integridad y
claves foráneas OK, Alembic `0013_cola_organizacion`,
4 descargas y 5 medios):
`/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-203946.db`
SHA-256:
`de8acb6a226395b94bac70fdbc0bf4df846438203ff681f6f9ee191a30b4d5da`.

SQLite de metadatos TMDB, backup online
integridad y `user_version=1` verificados:
`/home/viewtv/viewtv-backups/metadatos-series-predeploy-20261122-203946.db`
SHA-256:
`a969302d694ab861eea1ce33ec37ea0afaf9e34ca3d3763be02778a6bd4ee677`.
Conserva las 1.428 fichas previas.

## Reversión

Con la tarea de Windows pausada y tras verificar
copias, ejecutar la opción `rollback` de
`scripts/viewtv_series_compose_0013.sh`,
que devuelve **solo API y frontend** a sus
imágenes previas. No elimina volumen de metadatos,
no reinicia Jellyfin ni worker y no toca torrents.
Tras comprobar salud y smoke, reactivar tarea
Windows limitada. No ejecutar `down -v`,
`git reset --hard` ni fusión de PR #2.

## Comprobación de uso pendiente

El usuario debe abrir
`http://localhost:3000`, pulsar Ctrl+F5,
entrar en «Explorar», abrir una serie con
temporadas y probar visualmente el cambio
de temporada, la lectura de episodios,
y las tarjetas en pantalla/TV.
La prueba de pulsación real en TV y audio/vídeo
de un episodio sigue pendiente.

**No hay que pulsar «Solicitar episodio» durante
la prueba de navegación si no se desea crear
una solicitud.**
