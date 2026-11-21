# VIEWTV — segunda película: publicación real limitada a descarga #3

**Ejecución:** noche del 21 al 22/11/2026 (Europe/Madrid).
**Rama:** `viewtv-seguimiento-descargas-0012`.
**Worktree:** `/home/viewtv/projects/viewtv-broker-0013-20261119`.
**PR #2:** conservar OPEN/DRAFT, sin merge.

## Incidencia original

El usuario descargó una segunda película desde ViewTV, pero no entró
automáticamente en la biblioteca. La explicación comprobada es que la
publicación Windows seguía **desactivada por diseño** después de pasar
API y worker a 0013; el servicio publicador permanente todavía no
existía. Por lo tanto, este hito resuelve la incorporación de la #3
**mediante una ejecución individual supervisada**, no la automatización
general ni la ejecución desatendida de las próximas películas.

## Identidad y preflight sin escritura

- La SQLite real 0013 mostró
  `ID=3 DESCARGA=completada PROGRESO=100.0%
  VERIFICACION=verificada PUBLICACION=pendiente`.
- `scripts/viewtv_inspeccion_fuente_0013_solo_lectura.py` se pasó
  por STDIN a la API 0013 ya configurada, **sin modificar la imagen**.
  Exigió que la descarga fuese completa, verificada, propiedad
  exclusiva del torrent qBittorrent con etiqueta ViewTV y ruta staging
  exacta. Resultado: `TIPO_SOLICITUD=pelicula`,
  `ORIGEN_QBITTORRENT_VALIDO=SI`, 3 ficheros de origen,
  `PLAN_BIBLIOTECA_VALIDO=SI`, un único vídeo publicable,
  **6.795.899.016 bytes**, `DESTINO_EXISTENTE=False`.
  Los dos ficheros auxiliares no se publicaron.
- Windows: `C:\VIEWTV\publicador` no existía; carpeta Peliculas
  y staging existían en NTFS, sin reparse; espacio libre suficiente.
  La ejecución de PowerShell del conector tenía rol Administrador.

## Respaldo antes de cualquier mutación

La copia online de la SQLite fue generada con volumen productivo
`viewtv_viewtv_data:/data:ro` dentro de un contenedor efímero
sin red, mediante la API `sqlite3.backup()`. Se comprobaron
`PRAGMA integrity_check=ok` y `foreign_key_check=0`.

- SQLite:
  `/home/viewtv/viewtv-backups/api-resultados-predeploy-20261121-235826.db`
  SHA-256:
  `69b153e46a9280049d9157e8346fe735edc1d6cb917d152c472884c8b607e7b1`.
- Archivo para recuperación y código previo:
  `/home/viewtv/viewtv-backups/publicacion-id3-pre-20261121-235826.tar.gz`
  SHA-256:
  `e9b9b9d738b0a84adcfae1600043b0daba0583926fe037f6554dcee55d39262f`.
  Contiene la SQLite copiada, los overrides, el publicador y
  los documentos de planificación; `tar -tzf` pasó.

**Importante:** el verificador antiguo
`viewtv_release_0013_sqlite_verify_readonly.py` rechazó esta copia
porque estaba diseñado para el despliegue **sin ninguna descarga
nueva**. No informó de corrupción: esa precondición ya no era cierta.
Nuevo verificador `scripts/viewtv_backup_id3_verifica_0013.py`,
sin escritura y con reglas para la fase ID3, comprobó:
`SQLITE_0013_INTEGRIDAD_OK=SI`,
`SQLITE_CLAVES_FORANEAS_OK=SI`,
`DESCARGAS_HISTORICAS_EXCLUIDAS=2`,
`DESCARGA_3_PENDIENTE_Y_SIN_LEASE=SI`.
Sin lease previo ni trabajos 0013 alterados.

## Acción individual autorizada y sus resultados

1. `scripts/viewtv_api_single_id3_compose_0013.sh` reconstruyó
   el orden Compose desde las labels del contenedor actual, excluyendo
   duplicados del override temporal. `check` PASS y `summary`
   confirmó que **solo API** pasaría a modo `single`,
   `after_id=2`, `allowed_download_id=3` (ID de entorno).
   Worker quedó `VIEWTV_WINDOWS_PUBLICATION_MODE=disabled` y
   `VIEWTV_ENABLE_ORGANIZATION=false`.
2. `scripts/viewtv_preparar_publicador_id3_sin_servicio_0013.ps1`
   verificó hash + listado tar antes de modificar Windows. Creó
   `C:\VIEWTV\publicador` con ACL privadas para administrador actual,
   SYSTEM y grupo Administradores, más `bin`, `journal`,
   copia del publicador y `aprobacion.json` restringido **solo ID3**.
   **NO instaló un Windows Service ni se creó usuario o cuenta nueva**.
3. Se recreó únicamente API con
   `docker compose up -d --no-deps --no-build --force-recreate api`.
   CLI status real: `{"estado":"listo","modo":"single",
   "after_id":2,"allowed_download_id":3}`.
   Windows `-Mode Preflight`:
   `PREFLIGHT_PUBLICADOR_WINDOWS_0013_OK`, exit 0.
4. Se ejecutó el publicador Windows **una sola vez**
   `-Mode Once` desde la identidad administrativa autorizada:
   devolvió **`publicada`** y `PUBLICACION_ID3_EXIT=0`.
   Escribió un journal privado, creó enlace duro NTFS
   sin duplicar el vídeo, movió atómicamente la carpeta staged,
   obtuvo confirmación de organización de SQLite y solicitó
   el escaneo Jellyfin, con recibo en journal.
5. Verificación **independiente** posterior:
   `scripts/viewtv_verificar_publicacion_id3_ntfs_0013.ps1`
   pasa sin escritura, coteja journal/manifest, origen intacto,
   destino y tamaño, `fsutil hardlink list` con al menos dos
   enlaces, recibo del escaneo y ausencia de staging:
   `ORIGEN_CONSERVADO=SI`,
   `VIDEO_PUBLICADO_EN_NTFS=SI`,
   `ENLACE_DURO_NTFS_VERIFICADO=SI`,
   `DIARIO_Y_RECIBO_SCAN=SI`,
   `STAGING_RESIDUAL=NO`.
   No se ha borrado ni renombrado el torrent.
6. SQLite real: ID3 pasó de `pendiente` a **`organizada`**.
   El escaneo solicitado no garantiza por sí solo catálogo listo;
   se consultó Jellyfin de manera independiente:
   una película coincidente con carátula, 3 elementos en total.
   Inicialmente el catálogo ViewTV aún tenía 0 coincidencias.
7. `scripts/viewtv_sincronizar_catalogo_id3_0013.py` validó
   la presencia en Jellyfin y ejecutó **una vez** la función
   existente `synchronize_catalog` en transacción SQLite
   para reflejar la biblioteca actual. Resultado:
   `SINCRONIZACION_JELLYFIN_ELEMENTOS=3`,
   `PELICULA_ID3_EN_VIEWTV=SI`,
   `CARATULA_ID3_EN_VIEWTV=SI`.
8. Se recreó únicamente la API **sin** el override temporal,
   volviendo a `VIEWTV_WINDOWS_PUBLICATION_MODE=disabled`.
   CLI status `{"estado":"deshabilitado"}`, worker también
   `disabled` y organización `false`. No hay servicio
   `ViewtvPublicador0013` registrado. El permiso local ID3
   y journal privados se conservan para auditoría, pero la
   autoridad API actual falla cerrado.
9. Pruebas después del cierre: API healthy, worker 0013 activo,
   frontend y Jellyfin sin recrear; smoke de lectura
   **10/10 PASS**; ID3 `organizada`; Jellyfin y ViewTV
   **1 coincidencia y portada true**. Los resultados son
   datos de backend; reproducción visual de la segunda película
   todavía requiere comprobación del usuario.

## Riesgos y límites reales

- El objetivo inmediato, agregar la segunda película sin alterar
  las anteriores, se ha conseguido. **No hay publicación automática
  permanente**: el publicador se ejecutó bajo control administrativo,
  no como servicio restringido. No dar por resuelta la automatización
  general ni habilitar `general` a partir de esta única ejecución.
- Faltan servicio Windows con identidad/SID separado y privilegios
  mínimos, canal autenticado con autoridad Docker/API,
  validación de separación de ACL real, pruebas de apagado/
  reintento y reconciliación tras fallos, y sincronización de catálogo
  al finalizar el escaneo (sin intervención).
- No afirmar reproducción HLS de esta segunda película hasta
  que el usuario la pruebe. `Nadie 2` ya se había reproducido bien.
- Smart App Control fue desactivado por decisión del usuario; no
  se ha vuelto a cambiar esa protección.
- No se tocaron torrents ajenos, media de #2, ni .env/credenciales
  ni otra rama. PR #2 permanece OPEN/DRAFT.

## Recuperación

La SQLite anterior a la publicación está respaldada y verificada.
**No restaurarla ciegamente** sobre una SQLite con la descarga #3
ya organizada. Si Jellyfin/VIEWTV necesitaran recuperación, primero
comprobar journal e identidad de enlace duro, ejecutar una
reconciliación idempotente y mantener origen/destino intactos.
No borrar `.bak`, journal, bibliotecas ni ejecutar
`docker compose down -v`. Para desactivar la publicación:
la API ya está en `disabled`; no queda servicio SCM que detener.
Los scripts de preparación y prueba son reproducibles únicamente
para esta ID y este respaldo y no deben reutilizarse para otra película.

**Próximo paso de producto:** convertir 0013 en publicación
persistente y restringida para futuras películas, con seguridad
de SID/ACL y sincronización Jellyfin comprobadas; no reabrir
Jackett 404 ni cosmética como prioridad.
