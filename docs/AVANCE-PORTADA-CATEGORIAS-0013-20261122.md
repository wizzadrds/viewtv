# VIEWTV — portada por categorías, catálogo remoto y biblioteca independiente

**Actualización posterior (22/11/2026, 02:04):** la clave
TMDB v3 ya fue configurada por el propietario y recargada
en la API. Las **nueve filas** se comprobaron con HTTP 200,
carátulas reales y sesión protegida. La situación
`TMDB_CONFIGURADA=False` descrita abajo corresponde al
primer despliegue y **ya no es el estado actual**.
Ver [activación real de TMDB](AVANCE-ACTIVACION-TMDB-CATEGORIAS-0013-20261122.md).

**22/11/2026 · rama `viewtv-seguimiento-descargas-0012` · PR #2 OPEN/DRAFT.**
Worktree autorizada: `/home/viewtv/projects/viewtv-broker-0013-20261119`.

## Objetivo de la etapa

El usuario solicitó una experiencia estilo Netflix: inicio con filas
horizontales de «Recién añadidas», películas de 2026, tendencias,
acción, terror, comedia, ciencia ficción y series; fichas con póster
y sinopsis, sin descargar vídeo al visualizar el catálogo; acción
explícita «Descargar» y futuro «Desinstalar».

Se siguió la especificación del repositorio,
`docs/especificacion-y-estado.md`, que separa metadatos de
archivos y contempla filas «Novedades, Tendencias y Por género»
y cuota de caché independiente. Se verificó en GitHub la
versión de la rama concreta, sin sustituirla por `main`.

## Implementación y archivos

1. `backend/app/tmdb.py`: `discover` solo de metadatos TMDB
   `discover/movie` y `discover/tv` con filtro de género
   allowlist, limitación de año hasta la fecha actual,
   `include_adult=false`, orden por popularidad. No usa
   Jackett, qBittorrent ni cola de descargas.
2. `backend/app/descubrir.py`: `GET /descubrir/filas`
   devuelve orden y descripción estable de las colecciones;
   `GET /descubrir/filas/{fila_id}` permite cargar cada
   fila individualmente para aislar fallos TMDB. Primero
   `recientes`, obtenido exclusivamente de `Medio` con
   `disponible_en_jellyfin=true`, ordenado por ID de alta
   descendente. **No ordenar por `actualizado_en`**, ya
   que la sincronización Jellyfin actualiza esa marca en
   cada ciclo de 5 minutos. Las restantes filas se conectan
   a TMDB: `peliculas-nuevas` (año actual 2026),
   `tendencias`, `accion` (28), `terror` (27),
   `comedia` (35), `ciencia-ficcion` (878),
   `series-tendencia` y `series-misterio` (9648).
   Permisos por perfil, límites de consulta, validación de
   imágenes y rechazo de contenido marcado como adulto.
3. `frontend/components/discovery-rows.tsx`: **cabecera
   hero**, fila con películas locales y estantes con
   desplazamiento horizontal, 2:3, skeletons y estados
   `Disponible` / `Sin descargar`. Carga solo dos
   estantes en paralelo para limitar consultas a TMDB.
   Cada tarjeta abre ficha de TMDB o ficha local.
4. `frontend/components/discover-panel.tsx`: integra portada
   con las fichas, búsqueda y acción de solicitud
   **expresa** (no descarga por navegar). Muestra aviso
   de falta de TMDB y no presenta resultados simulados.
   El botón `Desinstalar` permanece **deshabilitado**:
   no se ha implementado borrado en producción.
5. `frontend/components/viewtv-app.tsx`: después del PIN
   ahora entra en `Explorar`; `Biblioteca` se mantiene
   disponible para reproducir. Si la ficha está instalada,
   el usuario puede abrir su medio real.
6. `frontend/app/globals.css`: cabecera con degradado
   oscuro, tarjetas verticales, rail con scroll-snap,
   enfoque visible para mando, flex responsivo.
7. `frontend/public/tmdb-logo.svg`: **logo oficial original
   sin alteraciones**, recuperado de Wikimedia Commons
   (origen `Tmdb.new.logo.svg`, basado en asset de TMDB).
   SHA-256 del SVG exactamente
   `d537fb228cf3ded904ef09b136fe3fec72548ebc1fea3fbbd1ad9e36364db38b`,
   coincide con el hash del asset original de TMDB.
   Se añadió logo + texto de atribución; no se alteraron
   colores ni proporción.
8. Nuevos scripts y Compose controlado para canary y reversión:
   `scripts/Dockerfile.categorias-api-0013`,
   `deploy/compose.categorias-netflix-0013.yaml`,
   `scripts/viewtv_categorias_compose_0013.sh`,
   `scripts/viewtv_categorias_compose_verify_0013.py`.

## Pruebas

- **32/32** pruebas focales de categorías PASS, incluyendo
  biblioteca local sin clave, autenticación, orden de
  filas, géneros y series, año actual, ausencia de
  `Solicitud`/`Descarga` al navegar.
- **928/928** pruebas de backend PASS, 2 warnings conocidos;
  Ruff PASS.
- Frontend TypeScript `tsc --noEmit` PASS y ESLint PASS.
- Compilación `next build` de la nueva imagen PASS.
- Imagen API construida desde **la imagen productiva
  `viewtv:auto-publicador-api-0013`**, copiando solo
  `tmdb.py`, `descubrir.py` y `main.py`; no actualiza
  dependencias ni toca `worker.organization_windows_cli`.
  SHA-256 del código en imagen y repositorio iguales.
- TestClient con SQLite productiva **montada solo lectura**,
  red externa desactivada: `/descubrir/filas` y
  `/filas/recientes` dieron 401 sin sesión, 200 con
  dependencia de perfil sustituida únicamente en el
  proceso de prueba; exactamente **4 elementos locales**
  recuperados. No se consultaron títulos ni se creó
  descarga.
- Compose nuevo y anterior validados por separado:
  API `general after_id=3`, worker `disabled`,
  organización `false`, montaje de medios `/media:ro`,
  workers y Jellyfin excluidos del despliegue.

## Despliegue REAL

Se detuvo temporalmente la tarea `VIEWTV - Publicador automatico 0013`
tras comprobar `RunLevel=Limited`, `State=Ready`,
`LastTaskResult=0`. Luego se recrearon **solo API y frontend**
con `docker compose up -d --no-deps --no-build --force-recreate`
sobre override aprobado.

Imágenes en producción:
- `viewtv-api-1`: `viewtv:categorias-0013-api-conservative`
  (healthy).
- `viewtv-frontend-1`: `viewtv-frontend:categorias-0013-candidate`
  (healthy).
- `viewtv-worker-1`: `viewtv:release-0013-worker-candidate`
  **sin cambio**.
- `viewtv-jellyfin` y FlareSolverr: sanos, sin recreación.

Comprobaciones:
- Smoke producción **10/10 PASS**: HTML 200, endpoints
  API/proxy 200, sesiones protegidas 401, Jellyfin 200.
- Logo oficial servido en `http://localhost:3000/tmdb-logo.svg`:
  **HTTP 200**; página **HTTP 200**.
- API: `{"estado":"listo","modo":"general","after_id":3,
  "allowed_download_id":null}`, conservando límite de
  publicación futura.
- Tarea Windows reactivada con identidad `Limited`,
  `LastTaskResult=0` en ejecución posterior
  a la actualización, `publicacion=sin_trabajos`,
  `catalogo=sincronizado`.
- No se modificaron archivos del usuario ni torrents;
  no se ejecutó `docker compose down -v`.
- La interacción humana con mando/imagen y sonido
  tras desplegar esta portada aún debe ser confirmada.

## Dependencia TMDB actual

**TMDB_CONFIGURADA=False** en la API real, comprobado sin
leer ni revelar el contenido de `.env` ni claves.
La portada **sí muestra la primera fila local** y el
diseño de estantes; películas de 2026/Terror/Acción/Series
remotas no se llenan hasta que el propietario registre
su clave `TMDB_API_KEY` de forma privada en el archivo
`.env` del host y se recree solamente la API con el
Compose aprobado. **No compartir la clave por chat**.

Esta versión consulta TMDB al entrar en la portada; **no
hace ingesta en segundo plano ni caché persistente de todas
las fichas remotas**. Mostrar títulos externos nunca
inicia la descarga de vídeos.

**Descarga a demanda:** botón de solicitud explícita y
selección adicional de fuente autorizada en `Buscar y pedir`,
como en la rama anterior; no es descarga directa con un clic.

**Desinstalar:** **no activo**. Con publicaciones por
hardlinks NTFS, quitar la entrada de Jellyfin **no libera
necesariamente espacio** si el original qBittorrent
sigue enlazado. Hace falta diseñar mecanismo con
propiedad fuerte y confirmación explícita, sin borrar
torrents ajenos ni medios en uso. No se introduce un
`unlink` indiscriminado.

## Respaldos y reversión

- Fuente/docs previa:
  `/home/viewtv/viewtv-backups/filas-netflix-pre-20261122-020300.tar.gz`,
  SHA-256
  `b736199fe4a4ee90cd4531a2ff26ddd1b36f746751dc0423a61d6d137162eefc`.
  `tar -tzf` verificado.
- Respaldo de script de despliegue antes de ajustar ruta:
  `/home/viewtv/viewtv-backups/filas-netflix-deploy-script-pre-20261122-014730.tar.gz`,
  SHA-256
  `8dc9baab058627bdcbd7a8166e06f9434ff89f3d64e872301a0dcca94f305638`.
- SQLite online backup:
  `/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-014729.db`,
  SHA-256
  `57aed7aca78bdc82261ddc0207cdcb4563807ca195e14223ca5e269a69e99d83`.
  Integridad y claves foráneas OK, Alembic 0013,
  4 descargas y 5 medios. Se realizó desde contenedor
  efímero sin red y volumen SQLite **solo lectura**.

Si la nueva UI falla:
1. Pausar tarea Windows solo con `RunLevel=Limited`
   y sin trabajos activos.
2. Desde worktree autorizada:
   `bash scripts/viewtv_categorias_compose_0013.sh rollback`.
   El script exige imágenes candidatas actuales y recrea
   únicamente frontend y API anteriores, manteniendo el
   publisher en `general after_id=3`.
3. Confirmar los cinco servicios saludables, smoke 10/10,
   y reanudar la tarea Windows limitada.

No restaurar SQLite salvo corrupción verificada; no hay
migración nueva. PR #2 queda **OPEN/DRAFT**. No
tocar árbol `/home/viewtv/projects/viewtv` ni `.bak`.
