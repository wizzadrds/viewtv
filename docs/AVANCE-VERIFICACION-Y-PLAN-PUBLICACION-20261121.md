# VIEWTV — descarga terminada, verificación recuperada y plan de Películas

**Fecha:** 21/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
**Plan:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Objetivo del usuario

El usuario observa que «Nadie 2» ya se descargó, pero **no aparece
automáticamente en la categoría Películas de Jellyfin con carátula,
sinopsis y metadatos**. El objetivo completo requiere:
descarga terminada → verificación de archivos → copia/publicación
segura en `C:\VIEWTV\media\Peliculas` → escaneo Jellyfin →
sincronización de catálogo VIEWTV.

**No dar por instalado el organizador** mientras la publicación real
no exista. La cola de descargas automáticas (envío/inicio) está
habilitada, pero es una etapa distinta.

## Diagnóstico real (solo lectura)

- Descarga VIEWTV **ID 2** de solicitud **#7 «Nadie 2»**:
  estado `completada`, progreso 1.0, torrent etiquetado
  `viewtv-descarga-2` en qBittorrent, estado `uploading`,
  origen en `C:\VIEWTV\media\descargas_temporales`.
- Contenido del .torrent, comprobado desde qBittorrent y en
  filesystem: **un MKV de 16,47 GiB** y **un archivo .url
  promocional**, ambos completos. El .url nunca se debe
  ejecutar, copiar a Películas ni publicar como metadato.
- El verificador de archivos de VIEWTV en modalidad **solo
  lectura** pasó su revisión de ambos archivos (tamaños,
  rutas dentro de staging, finalización y archivos regulares).
  Pero `estado_verificacion` permanecía `pendiente`
  porque la función `finish_claimed_verification()`
  del código del worker intentaba actualizar los campos
  `organizacion_estado` y `organizacion_disponible_desde`
  que **no existen en la release SQLite 0012 ni en su modelo
  SQLModel 0012**. Log productivo:
  `sqlalchemy.exc.CompileError: Unconsumed column names`.
- La base de producción es Alembic `0012_inicio_torrent`.
  La cola y el planificador de organización **0013**
  son ensayos/candidatos, **sin ejecutor de publicación
  Windows confinado para medios reales**.
- Jellyfin tiene biblioteca «Películas» apuntando a la
  carpeta apropiada; en su configuración las fuentes de
  metadatos e imágenes para Movie incluyen **TheMovieDb**
  y **The Open Movie Database**. Hay otra película en
  catálogo con carátula. Al publicarse un vídeo legible
  con nombre reconocible y completarse el escaneo,
  Jellyfin puede obtener carátula y sinopsis. **No se
  garantiza la identificación correcta ni que exista
  cobertura para un título sin cotejo posterior**.
- La solicitud #7 es de tipo `pelicula` pero tiene
  año `None`; el archivo del torrent contiene `(2025)`
  en su nombre, útil para que Jellyfin lo identifique.

## Corrección desplegada: verificación automática 0012

- `backend/app/queue.py`: `finish_claimed_verification`
  ahora construye los valores de actualización de forma
  compatible con **ambos modelos**: graba siempre el
  resultado de verificación y **solo** escribe estado de
  organización si el modelo incluye esos campos 0013.
  No crea columnas ni intenta publicar medios en 0012.
  Conserva transacción `BEGIN IMMEDIATE`, lease e
  identidad de descarga.
- `deploy/Dockerfile.verificacion-compatible-0012`,
  `deploy/compose.verificacion-compatible-0012.yaml` y
  `scripts/viewtv_compose_verificacion_compatible_0012.sh`:
  imagen `viewtv:verificacion-compatible-worker-0012`
  desplegada **solo en worker** con
  `docker compose up --no-deps --no-build --force-recreate`.
  La API, PWA, Jellyfin, qBittorrent y media no se recrearon.
  Config efectiva:
  `VIEWTV_ENABLE_DOWNLOAD_VERIFICATION=true`,
  `VIEWTV_ENABLE_AUTO_DOWNLOAD=true`,
  `VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1`,
  flags manuales envío/inicio `false` e ID vacía.
- **Resultado real postdespliegue:** descarga #2
  `estado_verificacion=verificada`, `verificada_en`
  registrado, sin errores ni lease de verificación.
  Progreso 100%, qBittorrent conserva etiqueta propia,
  antigua #1 permanece fallida. No hubo movimiento
  a Películas, borrado de torrents ni alteración de la
  biblioteca. Smoke solo lectura **10/10 PASS**,
  API/PWA healthy y worker running.

## Planificador 0013 preparado, NO desplegado

- `worker/organization_planner.py` (solo función de
  planificación; no publica) valida las rutas primero y
  **omite archivos `.url`** en el plan final, dejando
  en staging sus bytes intactos y excluyéndolos de la
  biblioteca. Mantiene rechazo de `.exe` y cualquier
  otra extensión no admitida, symlinks, duplicados y
  múltiples vídeos.
- Para solicitud manual sin año, usa un año inequívoco
  `(2025)` encontrado en el nombre del vídeo,
  conservando prioridad al año explícito. Si aparecen
  dos años distintos **no infiere ninguno**.
- Prueba de planificación con vídeo ficticio «Nadie 2»
  y `.url` demuestra único destino:
  `Peliculas/Nadie 2 (2025)/Nadie 2 (2025).mkv`,
  sin publicar `.url`, sin crear directorios ni tocar
  la fuente. Contrapruebas de año ambiguo y año
  explícito; **98/98 pruebas focales** de organización,
  puente y verificación aprobadas.
- Ensayo **solo lectura** con el torrent real, antes
  de actualizar el planificador de desarrollo, ya
  confirmó una única entrada MKV tras excluir el
  .url; la carpeta destino no existe. No se publicó
  ni modificó ningún archivo real.

## Ensayo de migración sobre copia real (nunca producción)

- Copia online SQLite verificada **después** de marcar
  la descarga #2 verificada (2 descargas, 7 solicitudes,
  69 resultados, 2 perfiles y 2 medios).
- En un sandbox separado montado como `/data` solo
  dentro de contenedor efímero sin red y con UID 1000,
  `alembic upgrade 0013_cola_organizacion` → verificación
  de 6 columnas y ausencia de organizaciones activadas
  → `alembic downgrade 0012_inicio_torrent`.
  **Ambos OK**: integridad SQLite y claves foráneas,
  recuentos idénticos, origen tar.gz SHA-256 sin cambios.
  `ensayo-0013-descarga-real-maNBHS` contiene solo
  el clon; no hubo DDL sobre producción.
- Esto demuestra compatibilidad de datos, **NO habilita
  publicación a Windows ni autoriza migrar producción**.

## Pruebas y respaldos

- Pruebas focales de verificador, leases, worker y cola:
  **70/70 PASS**. Ensayo con SQLite 0012 real clonada
  en memoria y nueva imagen worker: **3/3 PASS**,
  verificación registrada sin columnas 0013 ni
  alteración de la descarga antigua.
- Backend completo después de mejoras de planificador:
  **865/865 PASS** (solo 2 avisos de deprecación
  preexistentes). Focales de organización y verificación
  **98/98 PASS**, prueba de planner en rama, no en worker
  productivo. Smoke de producción **10/10 PASS**.
- Código verificación anterior:
  `~/viewtv-backups/verificacion-compat-0012-pre-20261121-023110.tar.gz`;
  SHA256 `81c69c2bc4bc51cf5db707380d3dced482a92e8bfa92b0a012839a3994f0998e`.
- Código planificador anterior:
  `~/viewtv-backups/organizador-ignorar-url-pre-20261121-023451.tar.gz`;
  SHA256 `3fa438b661bd82435ca2f39088772e18e99fe10f1f7fbf635d84d1469c14791b`.
- Respaldo íntegro antes de desplegar worker:
  `~/viewtv-backups/api-resultados-predeploy-20261121-023140.db.tar.gz`;
  SHA256 `7d334b58b630153e54263e454ef46c6e1649cfa3aeb73688dd3b2dc982129ab1`.
- Respaldo online ya verificada:
  `~/viewtv-backups/api-resultados-predeploy-20261121-024027.db.tar.gz`;
  SHA256 `7bed9f617a2629a83b5c90af14228fcc8f1575ff5c06e7f6216704ce3d230064`.
  Todos `tar.gz` verificados con `tar -tzf`, copias
  SQLite con `integrity_check` y `foreign_key_check`.
  No se restauró ningún archivo.

## Resultado posterior: película visible y automatización futura pendiente

**Actualización del mismo día:** la película #2 YA se ha publicado
de manera puntual en Películas, Jellyfin ya la reconoció con
carátula y sinopsis, y VIEWTV la incorporó a su catálogo.
La **organización automática general de futuras películas**
todavía no está conectada al worker de producción.

Para que ocurra **automáticamente con futuras descargas**, sin
colocar un torrent equivocado, sobrescribir bibliotecas ni publicar
accesos directos, siguen haciendo falta:

1. Una autoridad de publicación Windows operativa,
   separada del worker y confinada a `C:\VIEWTV\media`,
   con lease/ID verificada, identidad torrent y ACL
   demostradas antes de tocar medios reales.
2. Migrar conjuntamente API y worker a modelo
   0013 sobre la base real con respaldo y rollback
   controlados, activando únicamente trabajos verificables
   y nuevos, sin reactivar históricos.
3. Para cada descarga futura, confirmar publicación solo de
   vídeo/subtítulos aceptados, con destino nuevo y sin
   sobrescritura, y reconciliarla durablemente con SQLite.
4. Automatizar escaneo `POST /Library/Refresh` y **cotejar**
   identificación, imagen y catálogo después de completarlo.
   Estas operaciones ya funcionaron **puntualmente para #2**,
   pero no constituyen una cola general.

El organizador de laboratorio **no tiene hoy autorización
ni controles completos para copiar a la biblioteca real**;
no sustituirlo por un movimiento directo del worker.

**Rollback de este hito desplegado:**
`bash scripts/viewtv_compose_verificacion_compatible_0012.sh rollback`.
El rollback del worker no deshace la verificación ya registrada
ni crea/borrará archivos, y no cambia el modo automático.
PR #2 sigue en borrador y no debe fusionarse automáticamente.


## Publicación puntual real #2 (después del diagnóstico inicial)

**Acción realizada solo para la descarga #2 «Nadie 2», NO para la cola
entera.** La verificación automática ya marcaba esta descarga
`completada` / `verificada` y qBittorrent presentaba exactamente
el torrent con la etiqueta propia `viewtv-descarga-2`.

- Preflight Windows: origen
  `C:\VIEWTV\media\descargas_temporales\Nadie 2 (Nobody 2) (2025) [4k 2160p][Esp]\Nadie 2 (Nobody 2) (2025) [4k 2160p][Esp].mkv`;
  tamaño comprobado **17.686.540.799 bytes**; unidad C: NTFS,
  origen, padres y destino sin enlaces de reanálisis, carpeta
  final inexistente, espacio libre >717 GiB, mismo volumen.
  El torrent también contenía `Canal Telegram Oficial.url`
  de 112 bytes, **que no se publicó**.
- Script acotado `scripts/viewtv_publicar_nadie2_puntual_20261121.ps1`:
  solo acepta las rutas literales fijas y el tamaño conocido,
  crea un **enlace duro NTFS** en carpeta temporal aleatoria
  del propio directorio Películas (sin duplicar 16,47 GiB),
  comprueba una sola entrada MKV y usa `Directory.Move`
  nativo de Windows a **destino nuevo sin sobreescritura**.
  No mueve, borra ni renombra el original de qBittorrent.
- Primer intento `New-Item -ItemType HardLink` no llegó a
  publicar: PowerShell interpretó `[4k ...]` como comodines.
  Se inspeccionó la única carpeta temporal creada, se
  confirmó vacía y se retiró únicamente esa carpeta.
  La instrucción se sustituyó por **`CreateHardLinkW`**
  Win32 con rutas Unicode literales. Sintaxis PowerShell
  verificada; ensayo de enlace con vídeo ficticio
  `demo [Esp].mkv` bajo `$env:TEMP` **PASS**, con limpieza
  del sandbox. Segundo intento real **PASS**.
- Destino resultante:
  `C:\VIEWTV\media\Peliculas\Nadie 2 (2025)\Nadie 2 (2025).mkv`.
  Auditoría posterior: origen y destino ambos **17.686.540.799
  bytes**, fuente todavía presente, carpeta publicada con
  exactamente **un archivo**, y **cero carpetas temporales
  huérfanas**. El torrent sigue apareciendo con su etiqueta
  y qBittorrent continúa conservando el archivo.
- Se solicitó al Jellyfin real un escaneo mediante
  `POST /Library/Refresh` autenticado, respuesta **HTTP 204**.
  La API `JellyfinClient` de producción 0012 aún no incorpora
  el método `request_library_scan()` de la rama de desarrollo;
  se invocó la misma ruta HTTP directamente con `httpx.Client`.
  Una consulta posterior a Jellyfin confirmó **Nadie 2** como
  **Movie, año 2025, carátula Primary y sinopsis Overview**;
  Jellyfin ve el MKV publicado y **no** el archivo `.url`.
- El sincronizador interno de VIEWTV ejecuta normalmente cada
  30 min; tras hacer copia consistente de SQLite se ejecutó
  `worker.catalog_sync._sync_in_database()` **una sola vez**.
  `synchronize_catalog` completó correctamente; ahora hay
  **3 medios** en VIEWTV y un `Medio` «Nadie 2» tipo
  `pelicula`, año 2025, `disponible_en_jellyfin=true`,
  `jellyfin_id`, `imagen_portada`, `imagen_fondo`
  y `sinopsis` presentes. No se probó la reproducción
  completa del vídeo y la coincidencia de metadatos no
  certifica por sí misma la identidad de todo su contenido.
- Después: smoke API/PWA/Jellyfin **10/10 PASS**,
  worker ejecutándose, descarga #2 completada/verificada,
  SQLite de producción sigue **0012**, qBittorrent original
  intacto. No se creó un programador de publicaciones
  generales ni se habilitó la migración 0013.
- Respaldos adicionales verificados:
  `~/viewtv-backups/publicacion-hardlink-pre-20261121-024524.tar.gz`
  SHA-256 `a057c56d2fda47483cad96511f87936c2324e4438b5012d1127c44c26f5b4cd4`;
  `~/viewtv-backups/publicacion-puntual-docs-pre-20261121-024907.tar.gz`
  SHA-256 `7b08e61560f09f0118a34e551c5af828b0770a7362bcd8aef79f4f1dc917f7e5`;
  `~/viewtv-backups/api-resultados-predeploy-20261121-024759.db.tar.gz`
  SHA-256 `68253b5c50399260acac48c1ae09c033244d8d17a0fce82895576b82c8720ae9`,
  online íntegra, FK OK, inmediatamente antes de la
  sincronización de catálogo.

**Límite fundamental:** este script era una acción **manual y
puntual para #2** y contiene rutas fijas de esa película.
El procesamiento automático de futuras descargas todavía
solo llega a descargar y verificar; para organizar, reconciliar
y publicar cada nueva película sigue pendiente el broker
Windows operativo y la cola 0013. No afirmar que el éxito
puntual sea una automatización de publicación terminada.
