# VIEWTV — catálogo amplio y persistente, sin descargar vídeos

**Actualización 22/11/2026, noche:** el límite histórico de
50.000 fichas que figura más abajo fue ampliado a **250.000**,
configurable hasta 1.000.000, con caducidad de metadatos TMDB
a los 150 días y nuevas fuentes de películas y series. Ver
[AVANCE-CATALOGO-ESCALABLE-250K-20261122.md](AVANCE-CATALOGO-ESCALABLE-250K-20261122.md).

**Fecha de la intervención:** 22/11/2026, Europe/Madrid.
**Rama autorizada:** `viewtv-seguimiento-descargas-0012`.
**PR #2:** OPEN/DRAFT, no fusionada.
**Worktree:** `/home/viewtv/projects/viewtv-broker-0013-20261119`.

## Motivación

El usuario quiere una biblioteca de **fichas de películas y series**
tan amplia como sea posible, aspirando a más títulos que Netflix,
sin descargar miles de archivos a su ordenador. El servicio
TMDB permite descubrir y enriquecer **metadatos**, pero
**no proporciona los vídeos ni garantiza derechos de reproducción**.
Netflix varía según región y fecha, por lo que no se asegura
una cifra superior a su catálogo en una región sin comparación
homogénea. El objetivo técnico de VIEWTV es un almacén de
**hasta 50.000 fichas únicas** de TMDB, por incorporación gradual,
no 50.000 películas descargadas.

Documentación oficial consultada:

- https://developer.themoviedb.org/docs/faq
- https://developer.themoviedb.org/docs/rate-limiting
- https://developer.themoviedb.org/docs/finding-data
- https://developer.themoviedb.org/docs/errors

TMDB exige atribución y limita peticiones abusivas;
la UI ya conserva su logotipo original y aviso de atribución.
El importador evita peticiones masivas y detiene el ciclo
ante errores de TMDB, incluyendo limitación temporal 429.

## Diseño implementado

### Persistencia completamente separada

Nuevo archivo `backend/app/catalogo_cache.py`: base SQLite
`/catalogo/metadatos.db` con esquema propio `user_version=1`.
**No agrega tablas a `/data/viewtv.db`**, no toca Alembic
0013, no mueve vídeos y no escribe torrents.

Tabla `ficha`, llave primaria **(tipo,tmdb_id)**,
campos de texto de la ficha, sinopsis, año, IDs de género,
rutas de póster/fondo validadas, popularidad y fecha de
actualización. Guarda rutas de imágenes de TMDB, **no
descarga los archivos de carátula al disco**.
Tablas `cursor_ingesta` y `estado_ingesta` registran
página siguiente por fuente y últimas ejecuciones.

La API abre SQLite **solo lectura**, mientras el
catalogador autónomo es el único escritor. Consultas
SQL parametrizadas, paginación de máximo 20 por fila,
filtro JSON de géneros, límites de títulos,
exclusión de `adult=true`, validación de rutas de imágenes.
Límite duro **50.000 fichas únicas**; los duplicados de
películas entre terror/acción etc. actualizan una sola ficha.

### Catalogador automático independiente

Nuevo `backend/app/catalogador_cli.py`, servicio Docker
`viewtv-catalogador-1`: refresca al iniciar y
después **cada seis horas** (mientras Docker Desktop
esté encendido). En una pasada realiza hasta
**48 páginas × 20 fichas potenciales = 960 registros
brutos**, de 16 corrientes de popularidad, cine,
series, géneros (acción, terror, comedia, ciencia
ficción, misterio y drama) y años de estreno (incluido
el año actual 2026). Deduplica y conserva páginas
ya procesadas. Entre consultas espera **650 ms**;
en errores de TMDB aborta el ciclo para reintento
posterior. Bloqueo `flock` para evitar dos escritores.

La ventana de 6h y el límite de 50k frenan la
importación: **no se promete alcanzar 50k en una fecha**,
y algunas fuentes se solapan entre sí.

Su contenedor se ejecuta como UID/GID **1000:1000**,
raíz del filesystem **read-only**, sin privilegios
adicionales, `cap_drop: ALL`, `no-new-privileges`,
sin puertos publicados ni montajes de `/data` o
`/media`; **solo puede escribir en un volumen
separado `viewtv_viewtv_catalogo_data`**. Recibe
solo `TMDB_API_KEY` y tres variables inocuas,
sin cargar credenciales Jellyfin/qBit/JWT.
No existe una ruta de código para descargar vídeo.

### API y navegación por más de 20 títulos

`GET /descubrir/catalogo/estado` autenticado:
`total`, `peliculas`, `series`,
`ultima_actualizacion`, `solo_metadatos=true`
y límite 50k.

`GET /descubrir/filas/catalogo?pagina=N`
retorna el catálogo mixto completo en grupos de 20.
Filas de género y año intentan primero consultar
la **base local persistente** con paginación y,
si no hay contenido todavía, utilizan el TMDB real
como alternativa. Tendencias semanales siguen usando
TMDB directamente para no confundir popularidad
histórica con tendencia actual. Biblioteca local
`recientes` sigue usando `Medio` de Jellyfin.

La interfaz añade una fila **«Todo el catálogo»**,
indicador de fichas **únicas** y el botón
**«Ver 20 títulos más»** en cada fila paginada.
Evita carga inicial de miles de carteles;
requiere acción explícita para páginas siguientes.
Las tarjetas dicen «Sin descargar» o «Disponible».
La acción «Descargar» conserva el flujo anterior:
crea solicitud explícita y requiere seleccionar
una fuente autorizada; navegar no crea torrents.
«Desinstalar» **continúa deshabilitado** para evitar
borrar hardlinks o fuentes ajenas.

## Pruebas realizadas

- **44/44** casos focales del catálogo y descubrimiento
  (datos falsos sin red): formato de metadatos, rechazo
  de adultos, límites, filtro género/año, SQL seguro,
  paginación disjunta, deduplicación, contador real,
  control de peticiones/cursores y ausencia de
  descarga al navegar.
- Suite completa backend **940/940 PASS**, solo
  dos avisos deprecados conocidos.
- `ruff check` PASS. TypeScript y ESLint del
  frontend PASS. `next build` de la imagen
  `viewtv-frontend:catalogo-amplio-0013` PASS.
- Compose nuevo y anterior: ambos validados,
  sin imprimir el secreto TMDB; worker igual y
  política Windows `general after_id=3` intacta.
- Deploy nuevo vía
  `scripts/viewtv_catalogo_amplio_compose_0013.sh`
  con aprobación Windows pausada durante la
  recreación de **solo** API/frontend y creación
  del servicio catalogador.
- API `viewtv:catalogo-amplio-api-0013` y
  frontend `viewtv-frontend:catalogo-amplio-0013`
  **healthy**. Worker/Jellyfin/FlareSolverr
  no fueron recreados.
- Verificación de `docker inspect`: catalogador
  `USER=1000:1000 READONLY=true PRIVILEGED=false`;
  único montaje `/catalogo:rw`. API: `/media:ro`
  y `/catalogo:ro`.
- Importador terminó su primera pasada
  `CATALOGADOR_ESTADO=correcto PETICIONES=48
  FICHAS_UNICAS=728`: **599 películas + 129 series**
  distintas al terminar la intervención.
- El script
  `scripts/viewtv_catalogo_amplio_live_readonly_0013.py`
  consultó endpoints reales: acceso sin sesión
  **401**, contador **200**, páginas 1 y 2
  **20+20 fichas sin solapamiento**, categorías
  «Recién añadidas», estrenos, terror, acción,
  comedia, ciencia ficción y series misterio
  **HTTP 200**. Límite de páginas **422**.
  No se modificó sesión del servidor productivo;
  solo se usa TestClient en proceso aislado.
- Smoke de producción `scripts/viewtv_release_smoke_0012_readonly.py`:
  **10/10 PASS**, reproducción existente sin
  modificaciones.
- Tarea Windows de publicación `Limited`
  reactivada; `Ready` y `LastTaskResult=0`
  tras el despliegue, `VIEWTV_WINDOWS_PUBLICATION_MODE=general`
  y `after_id=3`.

**No se ha comprobado visualmente en el navegador
del propietario** la nueva página; requiere Ctrl+F5
en `http://localhost:3000` y entrar en «Explorar».
Los 728 son registros de metadatos, no vídeos
reproducibles desde TMDB.

## Respaldo previo y recuperación

Tar con archivos de fuente previos:
`/home/viewtv/viewtv-backups/catalogo-amplio-pre-20261122-021700.tar.gz`
SHA-256:
`04061b399e0877e16e76ac763fc8d1013e543c90a5dddd16346906987250c9b8`,
inspeccionado con `tar -tzf`.

Backup SQLite productivo consistente previo:
`/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-021820.db`,
SHA-256:
`8e066c0c0ba08d6d5b376c0854f62891cfb5d3d0c77d27bf2da93c54722b3ff9`.
Integridad `ok`, FKs `ok`, esquema Alembic
0013, 4 descargas y 5 medios (son recuentos de
tablas de la base principal, no vídeos nuevos).

Tar documental previo:
`/home/viewtv/viewtv-backups/catalogo-amplio-docs-pre-20261122-022150.tar.gz`,
SHA-256:
`747b61d566133a487075a8206192006be8d01b6056596c75280235d26bc04ce9`,
`tar -tzf` validado.

Reversión controlada:
1. Pausar tarea Windows `VIEWTV - Publicador automatico 0013`
   comprobando identidad limitada y estado.
2. Usar `bash scripts/viewtv_catalogo_amplio_compose_0013.sh rollback`:
   detiene catalogador y vuelve únicamente a API
   `viewtv:categorias-0013-api-conservative` y
   web `viewtv-frontend:categorias-0013-candidate`.
3. Comprobar servicios, smoke 10/10 y reactivar
   el publicador limitado.

La reversión **no borra el volumen de metadatos** ni
la base principal; mantiene las fichas para una
posterior reactivación. No ejecutar `docker compose down -v`.
PR #2 se conserva OPEN/DRAFT, sin fusionar.

## Límites y próximos pasos

- El catálogo crecerá automáticamente mientras Docker
  esté funcionando; la fecha exacta para llegar a
  miles/decenas de miles depende de resultados,
  duplicados, límites TMDB y disponibilidad del equipo.
- No equivale a derechos de reproducción Netflix ni
  ofrece películas de pago gratuitamente.
- Confirmar en navegador contador «728 fichas únicas»,
  carrusel «Todo el catálogo» y «Ver 20 títulos más».
  Si ya se importó más después de la prueba, la cifra
  crecerá en nuevas pasadas.
- Futuro: flujo **«Desinstalar»** verificado con
  propiedad real de los hardlinks/torrents,
  confirmación y un broker de mínimos privilegios;
  no se activa ahora.
