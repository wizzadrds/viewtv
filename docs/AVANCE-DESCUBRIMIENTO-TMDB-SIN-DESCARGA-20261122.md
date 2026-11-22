# VIEWTV — catálogo de descubrimiento sin descargar vídeo (primera etapa)

**Fecha:** 22/11/2026. **Rama autorizada:**
`viewtv-seguimiento-descargas-0012`.
**PR:** #2, conservar OPEN/DRAFT, sin merge.
**Árbol:** `/home/viewtv/projects/viewtv-broker-0013-20261119`.

## Petición

El usuario quiere que la plataforma tenga automáticamente fichas
de películas y series, con carátulas, sinopsis, etc., **sin que
la mera presencia de una ficha descargue el vídeo al PC**.
Cuando elija una ficha, quiere poder descargarla o desinstalarla
(si está almacenada). Solicita basarse en el repositorio GitHub.

La especificación original
`docs/especificacion-y-estado.md` ya contempla catálogo persistente
desacoplado de archivos, tendencias, cuota de 80 GiB, descarga
a demanda y borrado de caché solo después de verificar que no
se usa el contenido. README aclara que TMDB es proveedor de
**metadatos**, no de archivos multimedia. El actual modelo
`Medio` identifica solo títulos disponibles en Jellyfin;
no debe falsificarse un `jellyfin_id` para mostrar títulos remotos.

## Hallazgo de configuración

Comprobación **sin revelar secretos** en la API productiva:
`TMDB_CONFIGURADA=False` y `TMDB_IDIOMA=es-ES`.
No existe ahora una credencial TMDB efectiva que permita
obtener tendencias en tiempo real. No se ha creado clave ni
consultado contenido de `.env`. La clave la debe obtener y
configurar localmente el propietario. No solicitarla en chat.

TMDB requiere API key y atribución visible con logo aprobado.
Guía oficial:
https://developer.themoviedb.org/docs/getting-started
https://developer.themoviedb.org/docs/faq
https://www.themoviedb.org/about/logos-attribution

Antes de activar visualización real con TMDB, instalar el
**logo oficial aprobado sin modificaciones** en la sección
de créditos de la interfaz; el prototipo muestra el aviso de
atribución y enlace, pero aún no incorpora el logo. No publicar
una pantalla de créditos incompleta afirmando cumplir sus normas.

## Entregable de código (primera etapa, candidata)

- `backend/app/tmdb.py`: añade métodos de metadatos
  `trending(tipo,pagina)` (`trending/movie/week` o
  `trending/tv/week`) y `search_page`; restringe
  tipo/paginación, `include_adult=false`, idioma
  `es-ES` (configuración existente), sin iniciar descargas.
- `backend/app/descubrir.py`: router autenticado:
  - `GET /descubrir/estado`: devuelve solo booleano,
    nunca credenciales.
  - `GET /descubrir/tendencias?tipo=pelicula|serie&pagina=1`
  - `GET /descubrir/buscar?tipo=...&titulo=...&pagina=1`
  - `GET /descubrir/pelicula/{tmdb_id}` y
    `GET /descubrir/serie/{tmdb_id}`
  - `POST /descubrir/{tipo}/{tmdb_id}/solicitar`:
    reconsulta la ficha a TMDB en servidor y crea
    **solo una solicitud** mediante la cola actual.
    El usuario sigue eligiendo expresamente una
    fuente autorizada en «Buscar y pedir»; la primera
    pulsación NO inicia un torrent ni crea `Descarga`.
- Salidas no incluyen clave/URL de torrent ni metainfo. Se
  descartan filas TMDB adultas o IDs/títulos inválidos,
  se validan las rutas de imágenes contra un patrón seguro,
  se limitan páginas y búsqueda. La disponibilidad de cada
  ficha se determina mediante ID TMDB ya ligado o
  coincidencia inequívoca de título/año exactos con
  `Medio` disponible en Jellyfin. No se considera
  instalada una película por aparecer en tendencias.
- `frontend/components/discover-panel.tsx`: sección
  «Explorar» con dos géneros de títulos (películas y
  series), tendencias, búsqueda, paginación, pósteres
  verticales, fondo, sinopsis, año, géneros y estado
  «Sin descargar»/«En tu biblioteca».
  Si hay una película local, guía a Mi biblioteca.
  Si no está, permite **solicitar la descarga**, y luego
  pasar a seleccionar fuente manualmente. Si TMDB no
  está configurada, muestra una explicación clara
  sin romper el catálogo Jellyfin.
- `frontend/components/viewtv-app.tsx`: enlace de
  navegación «Explorar» separado de «Biblioteca».
- `frontend/app/globals.css`: tarjetas 2:3 y navegación
  adaptable a móvil/televisión.
- `backend/tests/test_descubrir.py`: casos unitarios
  sin red y base efímera; tendencias, películas, series,
  búsqueda, rechazo de contenido adulto, imágenes
  validadas, límites, coincidencia local,
  autenticación, configuración ausente, creación explícita
  de `Solicitud`, deduplicación y **cero Descarga**.

**No se ha añadido una migración a producción ni tocado
la base real**, y no se han desplegado esta API ni el
frontend candidatos. El sistema actual de descargas,
publicador NTFS y reproducción sigue activo.

## No implementado todavía (no exagerar)

- **Alimentación persistente y periódica de una tabla de
  metadatos**: el prototipo realiza consultas automáticas
  a TMDB al abrir «Explorar» y no descarga medios.
  Todavía no guarda una copia duradera de fichas externas
  en SQLite para navegar sin Internet. Requiere tabla
  independiente `contenido_catalogo`, migración
  ensayada y programador de ingestión sujeto a presupuesto,
  cuotas, deduplicación, auditoría y licencia TMDB.
- **Descarga con un solo clic desde la ficha**: actualmente
  `POST /solicitar` crea una solicitud, luego el usuario
  selecciona una fuente desde «Buscar y pedir» por
  diseño existente. No se debe afirmar que ese POST
  inicia automáticamente una descarga de vídeo.
- **«Desinstalar» real**: botón visible pero
  intencionadamente **deshabilitado**. Jamás llamar
  `unlink`, `Remove-Item -Recurse` ni qBittorrent
  `deleteFiles` basándose en título o ruta del navegador.
  Requiere autoridad Windows aparte, comprobación fuerte
  del journal, hash, lease, titularidad local, estado de
  reproducción/seeding, confirmación en dos pasos y
  semántica explícita para el origen y su hardlink.
  Después se solicita escaneo Jellyfin, pero la ficha
  remota permanece en catálogo para volver a descargar.
- **Clave TMDB y logo autorizado**: faltan ahora mismo.
  No crear secretos, usuarios ni cuentas externas de oficio.
- **Despliegue**: pendiente hasta resolver la clave,
  logo/atribución, pruebas en staging y proceso de
  reversión si se despliega.

## Respaldos previos y reversibilidad

Antes de editar los archivos existentes se creó:

`/home/viewtv/viewtv-backups/descubrimiento-sin-video-pre-20261122-012100.tar.gz`

SHA-256:
`dace9c9d3559bbc6f133910fcded190bde67457fc7ed36345649122f9fea5447`.

Validado con `tar -tzf`; comprende
`backend/app/main.py`,
`backend/app/tmdb.py`,
`backend/app/solicitudes.py`,
`frontend/components/viewtv-app.tsx`,
`frontend/lib/api.ts`,
`frontend/app/globals.css`,
`docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`,
`docs/BACKLOG.md`.
`app/descubrir.py`, `test_descubrir.py`,
`discover-panel.tsx` y el presente informe son nuevos.

Sin despliegue, basta continuar usando los servicios actuales:
no se requiere rollback de SQLite, Docker ni archivos NTFS.

## Próxima etapa

1. Configurar clave TMDB **privadamente** y logo oficial.
2. Ensayar consulta real de tendencias y portadas sin que se
   cree ningún `Descarga` en un entorno aislado y habilitar
   el apartado «Explorar» sin alterar los vídeos existentes.
3. Después incorporar ingesta persistente de metadatos
   programada y **borrado selectivo** con broker de
   mínimos privilegios, pruebas de hardlinks y qBit en
   sandbox; no borrar ninguna película existente en la
   etapa de desarrollo.


## Validación ejecutada en entorno aislado

- Backend: **913/913 PASS**, dos avisos deprecados ya conocidos,
  desde la imagen efímera de pruebas con el repositorio montado
  **solo lectura** y Docker `--network none`. Incluye
  **17/17** casos de `tests/test_descubrir.py`.
- `ruff check --no-cache` de `app/descubrir.py`,
  `app/tmdb.py`, `app/main.py` y el test: **PASS**.
- TypeScript `tsc --noEmit --incremental false`: **PASS**;
  ESLint del panel y vista PWA: **PASS**, ambos en
  `node:22-bookworm-slim` efímero sin red y con código
  **solo lectura**.
- Imagen de frontend creada **solo como candidata local**:
  `viewtv-frontend:discover-tmdb-candidate`, Next.js 15
  `npm run build` **PASS**, prerender de 5 páginas.
  **No se ha recreado ni desplegado el frontend en producción.**
- Todos los endpoints de TMDB en las pruebas usan stubs
  y una SQLite temporal efímera; no se consumió TMDB real
  ni Jackett, qBittorrent o vídeos del usuario.
