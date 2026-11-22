# VIEWTV — crecimiento del catálogo por encima de 50.000 fichas

**Fecha:** 22/11/2026 (tarde, hora Europe/Madrid)
**Rama exclusiva:** `viewtv-seguimiento-descargas-0012`
**PR #2:** OPEN/DRAFT; no fusionar sin autorización
**Árbol autorizado:** `/home/viewtv/projects/viewtv-broker-0013-20261119`

## Pregunta del propietario

¿ViewTV se quedará limitado a 50.000 carátulas si quiere superar
el catálogo de Netflix? **No.** Las 50.000 eran una cuota local
defensiva de la primera versión, no un límite del catálogo TMDB.

Netflix tiene un número distinto de títulos reproducibles por
país y fecha; **una ficha TMDB no concede acceso a la película**.
Esta mejora amplía la capacidad de **fichas de descubrimiento**,
no las licencias ni los vídeos de la biblioteca. Se mantiene la
descarga individual y explícita de fuentes autorizadas.

## Implementación entregada

- **250.000 fichas únicas** por defecto en un volumen propio
  `viewtv_viewtv_catalogo_data`. El código valida la variable
  `VIEWTV_CATALOG_MAX_ITEMS` entre 20.000 y **1.000.000**:
  a futuro la cuota puede elevarse mediante variable privada
  de Docker Compose sin editar esquema ni código. No es
  almacenamiento ilimitado; se controla el tamaño.
- Límite de consulta y paginación de la tabla local:
  **50.000 páginas** de 20 fichas para manejar incluso el
  máximo configurable de un millón de registros.
  Las peticiones TMDB externas conservan su límite de
  **500 páginas**, por separado.
- Deduplicación `PRIMARY KEY(tipo,tmdb_id)`: una película
  en cinco géneros sigue contando **una sola vez**.
- Se añaden fuentes de años anteriores y más géneros:
  comedia/crimen/serie, drama/animación/película,
  cine de 1950, 1960, 1970, 1980, 1990, 2000,
  2005, 2010, 2015, 2018 y años recientes.
  Máximo **96 peticiones TMDB cada seis horas**;
  intervalo entre ellas **650 milisegundos**.
  No aumenta sin límite las llamadas al proveedor,
  y se conserva la detención ante errores/rate limit.
- La retención de metadatos pasa a un máximo de **150 días
  desde su última actualización** (más conservador que
  los seis meses indicados para TMDB). Las consultas GET
  nunca muestran entradas caducadas aunque el catalogador
  esté detenido, y el escritor elimina solo las fichas
  caducadas cada ciclo. **Jamás se borran vídeos, Jellyfin,
  torrents ni el SQLite principal con esta operación**.
- Nuevo índice `idx_ficha_actualizado_en`, aplicado solo
  a `metadatos.db` con `CREATE INDEX IF NOT EXISTS`.
  El esquema se mantiene en `user_version=1` y
  ninguna migración toca `/data/viewtv.db`.
- Aunque se alcance la cuota, el catalogador podrá
  seguir revisando y renovando fichas conocidas;
  las nuevas solo entran cuando haya capacidad.
- No se modifican la interfaz ni la navegación
  ya instaladas: «Todo el catálogo», contador de
  fichas únicas y «Ver 20 títulos más» siguen funcionando.

## Verificaciones antes y después del cambio

Antes de intervenir el equipo fue identificado Online como
`LAPTOP-V2QSMC01`; la rama estaba limpia y sincronizada en
`734fca6`. El catalogador real contenía **1.428 fichas**
(1.168 películas, 260 series), sin nuevos archivos de vídeo
en este hito.

Copia de seguridad verificada del volumen de catálogo,
consistente por `sqlite3.backup` con origen solo lectura:

`/home/viewtv/viewtv-backups/metadatos-pre-ampliacion-20261122-200700.db`

SHA-256:
`e4311b97f97535b6e116150c5270e4b96d83a589ff991308f1ab4f257a343d3c`.
Integridad `ok`, **1.428 fichas**.

Backup online de la base PRINCIPAL, por precaución ante
la recreación de API (aunque no hubo migración):

`/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-201500.db`

SHA-256:
`8869c84def886d511d3aba3aa6876d9af3af1ff43522388292403862b2d0d25f`.
`integrity_check=ok`, `foreign_key_check=ok`,
Alembic `0013_cola_organizacion`, 4 descargas, 5 medios.

Respaldo previo de solo código/docs implicados,
`tar -tzf` verificado:

`/home/viewtv/viewtv-backups/catalogo-superior-50k-pre-20261122-200700.tar.gz`

SHA-256:
`b9aa7efbeb0301892444b112c998af5b1af26d760c1eb3aa97b6fd64ee4a1e8e`.

### Pruebas y API

- Pruebas focales de catálogo y descubrimiento:
  **50/50 PASS** (cuotas hasta 1M, valores inválidos,
  limpieza y ocultación de fichas caducadas,
  renovación con cuota alcanzada, máximo de 96
  peticiones, índice persistente, autenticación,
  ausencia de nuevas descargas al navegar).
- Suite backend completa: **946/946 PASS** tras
  añadir todas las pruebas de esta fase; solo dos
  avisos deprecados conocidos.
- Ruff **PASS** y construcción de imagen candidata
  `viewtv:catalogo-escalable-api-0013` **PASS**.
- Compose de ampliación validado antes de aplicar,
  sin imprimir la clave TMDB. Se mantienen worker
  `viewtv:release-0013-worker-candidate` y
  frontend `viewtv-frontend:catalogo-amplio-0013`.
- Se pausó temporalmente `VIEWTV - Publicador
  automatico 0013` (nivel `Limited`, modo interactivo
  y resultado previo 0); se recrearon **exclusivamente
  API y catalogador** y se reactivó la tarea limitada
  tras comprobar la política `general after_id=3`.
- Producción API `viewtv:catalogo-escalable-api-0013`
  **healthy**; web existente healthy, Jellyfin healthy,
  worker no recreado.
- Smoke de producción heredado **10/10 PASS**:
  frontend 200, proxy API 200, sesiones 401, Jellyfin 200.
- Nuevo smoke **`CATALOGO_ESCALABLE_SMOKE=PASS`**:
  API anuncia **250.000**, `MAX_PAGE=50000`,
  `MAX_CACHE_DAYS=150`, presupuesto 96,
  base `user_version=1`, índice presente, HTTP
  401 sin sesión, contador 200, páginas 1 y 2
  sin solapamiento, página 50001 rechazada (422).
  Conserva **1.428** registros (1.168 + 260) en el
  momento de la comprobación.

## Archivos de esta fase

- `backend/app/catalogo_cache.py`
- `backend/app/catalogador_cli.py`
- `backend/app/descubrir.py`
- `backend/tests/test_catalogo_cache.py`
- `backend/tests/test_descubrir.py`
- `deploy/compose.catalogo-escalable-0013.yaml`
- `scripts/viewtv_catalogo_escalable_deploy_0013.sh`
- `scripts/viewtv_catalogo_escalable_verify_0013.py`
- `scripts/viewtv_catalogo_escalable_live_readonly_0013.py`
- `scripts/viewtv_catalogo_backup_solo_lectura_0013.py`

No hay archivos de secretos versionados, no se imprime
el valor de `TMDB_API_KEY`, no se toca la worktree
de producción `/home/viewtv/projects/viewtv`.

## Reversión

Si la versión ampliada falla:

1. Pausar temporalmente la tarea de Windows con
   controles de identidad/estado.
2. Desde la rama exclusiva ejecutar
   `bash scripts/viewtv_catalogo_escalable_deploy_0013.sh rollback`.
   Vuelve **solo API y catalogador** a imagen
   `viewtv:catalogo-amplio-api-0013`; deja web,
   worker, Jellyfin, archivos y volumen intactos.
3. Verificar salud, smoke y tarea, y reactivarla.

Las bases respaldadas no deben restaurarse salvo
corrupción confirmada; **no usar `docker compose down -v`**.

## Notas del proveedor y siguientes etapas

La API de TMDB es gratuita para uso no comercial con
atribución y está sujeta a condiciones de caché:
https://developer.themoviedb.org/docs/faq
https://developer.themoviedb.org/docs/rate-limiting

Para una incorporación de decenas o cientos de miles
sin aumentar el rastreo por `/discover` descontroladamente,
la mejora posterior óptima será estudiar las **Daily ID Exports**
oficiales y las APIs de seguimiento de cambios, con
filtrado de adultos, actualización progresiva y consulta
de detalles en lotes limitados:
https://developer.themoviedb.org/docs/daily-id-exports
https://developer.themoviedb.org/docs/tracking-content-changes

No se garantiza llegar al objetivo de 250.000 fichas
ni que todas tengan póster: dependerá del conjunto
de datos y de las condiciones de TMDB. El catálogo
es **informativo**, no un catálogo de licencias
para reproducir contenido de terceros.
