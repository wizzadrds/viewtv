# VIEWTV 0018 — Preflight unificado de retirada y ensayo de liberación NTFS

**Fecha:** jueves 26 de noviembre de 2026 (Europe/Madrid).
**Rama:** `viewtv-seguimiento-descargas-0012`.
**PR:** #2, abierto, en borrador y **sin fusionar**.
**Prioridad solicitada:** gestión de espacio, retirada de películas vistas y caché **antes** de crear la app Samsung instalable. «VIEWTV Momentos» después.

## Resultado y alcance

**Se ha construido y ejecutado en el equipo real un preflight integrado de SOLO LECTURA** que correlaciona las evidencias de biblioteca, publicación y torrents por identidad. También se ha probado un procedimiento de eliminación de **ambos enlaces de un archivo ficticio en un sandbox nuevo de Windows**, con recuperación ante interrupción.

**No existe todavía permiso ni ejecutor de borrado de producción. No se ha retirado ninguna película real.** El preflight no es una transacción atómica con qBittorrent, Jellyfin o Windows: las comprobaciones se repetirán bajo inmovilización/exclusión del ejecutor futuro.

## Comprobaciones realizadas

1. **SQLite de ViewTV en API**, leído mediante `docker exec -i viewtv-api-1 python -`:
   - Medios tipo película que siguen disponibles en Jellyfin;
   - descargas con `organizacion_estado=organizada`, su ID, solicitud y estados de verificación;
   - perfiles activos, marcas manuales de «vista» y solicitudes de retirada **pendientes**;
   - no se consulta ni modifica ningún PIN; no se hace INSERT/UPDATE/DELETE.
2. **Jellyfin solo GET**, con páginas de hasta 100 y total acotado: exige que cada película tenga un ID único del catálogo y una ruta de vídeo única de tipo Movie.
3. **qBittorrent solo GET**: `torrents/info` y `torrents/files`, sin inicio, pausa, borrado o cambio de estado. Se exige identidad hash exacta, etiqueta exclusiva `viewtv-descarga-{id}`, carpeta de origen autorizada, descarga verificada y torrent detenido; archivos y tamaños deben estar completos y no tener entradas ajenas o ambiguas.
4. **Windows nativo/NTFS solo lectura**: reutiliza la auditoría 0016, comprueba el SHA-256 del diario, la huella de la intención, el mismo inodo/volumen NTFS, exactamente **dos hardlinks**, ausencia de staging, rutas sin junction/reparse, carpetas y archivos completos. Emite una prueba por ID de descarga sin rutas privadas, títulos ni hashes de torrent.
5. **Cruce**: compara diario de Windows con el mismo archivo leído por WSL usando el SHA-256 de sus bytes, une `descarga.id` con `medio.jellyfin_id` por **ruta exacta** (nunca solo por título o TMDB), verifica estado del torrent y evita IDs/diarios repetidos.
6. **Seguridad compartida**: si falta un perfil activo que haya marcado «vista», no hay solicitud pendiente válida, la descarga o publicación no se demuestra propia o cualquier fuente falla, se bloquea. **Además siempre se exige una autorización diferenciada de administrador, que aún NO existe y no puede falsificarse marcando «vista».**
7. Se reejecuta el inventario Windows **antes y después** de consultar SQL/Jellyfin/qBit; si las evidencias cambian, el preflight aborta. Esto mejora la detección de carreras pero **no sustituye** el bloqueo atómico necesario para borrar físicamente.

### Herramientas de solo lectura y código revisado

- `worker/retirement_preflight_0018.py`: evaluador puro, sin acceso a red ni disco y **sin ninguna función de borrar**.
- `scripts/viewtv_retirada_snapshot_api_0018.py`: lectura SQL/Jellyfin/qBit desde la API existente.
- `scripts/viewtv_windows_retirada_inventario_0018.ps1`: prueba nativa NTFS de Windows.
- `scripts/viewtv_retirada_preflight_0018.py`: coordinador local WSL, reúne las tres fuentes, compara la huella de cada diario, emite solo recuentos y motivos de denegación y **no recibe parámetros de película que puedan activar una operación**.

El preflight se ejecuta manualmente desde el worktree autorizado:

```bash
python3 scripts/viewtv_retirada_preflight_0018.py
```

No se ha añadido un endpoint web con permisos de eliminar ni se ha desplegado una imagen de API nueva. La versión productiva sigue siendo la **0017** con la caché privada y las publicaciones existentes.

## Resultado observado en la biblioteca real (26/11/2026)

| Condición | Resultado |
| --- | ---: |
| Películas inspeccionadas en ViewTV | **4** |
| Diarios de publicación con identidad NTFS confirmada | **2** |
| Películas con publicación única ausente | **2** |
| Torrents aún activos o incompletos | **2** |
| Inventarios de archivos de torrent no verificables íntegramente para retirada | **2** |
| Archivos incluidos en los dos torrents qBit | **6** |
| Archivos contemplados por los diarios de publicación | **2** |
| Archivos qBit no contemplados por los diarios | **4** |
| Películas con todos los perfiles marcados como «vista» | **0** |
| Solicitudes de retirada pendientes y válidas | **0** |
| Autorizaciones específicas de administrador | **0 (mecanismo deshabilitado)** |
| Películas bloqueadas para eliminación | **4 de 4** |
| Películas originales eliminadas | **0** |
| Torrents modificados | **0** |

El diagnóstico complementario, siempre **solo GET/lectura**, detectó **6 archivos de torrent** frente a **2 archivos incluidos en los diarios de publicación**, con **4 archivos extra no publicados** (dos descargas afectadas). Todos los seis archivos qBit tenían tamaños positivos, `progress=1`, prioridad permitida y nombres no vacíos; **dos nombres no cumplen las normas estrictas actuales de normalización**. Esto **no demuestra corrupción ni que esos archivos sean ajenos**, sino que no existe autorización para retirarlos físicamente junto a las películas sin probar su titularidad y relación exactas.

Herramientas sin rutas/nombres expuestos:
`scripts/viewtv_retirada_diagnostico_qbit_0018.py` y
`scripts/viewtv_retirada_diagnostico_mapeo_0018.py`.
**Nunca se han borrado ni pausado torrents.**

La ausencia de marcas «vista» y solicitudes pendientes no concede permiso al sistema para adivinar qué películas deseaba retirar el usuario. Las carpetas sin diario siguen protegidas. Los tamaños de biblioteca y descargas pueden corresponder a **los mismos bloques por hardlinks**; no sumar ni prometer gigabytes que se vayan a recuperar.

## Laboratorio Windows aislado: los DOS enlaces físicos

Nuevo `scripts/viewtv_windows_retirada_sandbox_0018.ps1`, con **único modo de ensayo**, sin parámetros para operar en la biblioteca.

- Crea un directorio nuevo y aleatorio con GUID **bajo la carpeta temporal de la sesión Windows**.
- Escribe un vídeo/archivo **ficticio** de 1 MiB, crea su hardlink publicado y comprueba que son el mismo objeto NTFS con contador exactamente dos.
- Abre un lector exclusivo y demuestra que la verificación se bloquea cuando hay un archivo en uso.
- Crea deliberadamente un **tercer hardlink ficticio** y demuestra que la regla de exclusividad lo rechaza. Lo retira y exige dos enlaces de nuevo.
- Simula un diario con fases `preparado → copia_retirada`, elimina **solo el link ficticio publicado** y comprueba que el original todavía está presente con un enlace.
- Simula una interrupción y recupera la publicación original **recreando su hardlink ficticio**, sin dañar el origen. Verifica de nuevo que existen dos enlaces.
- Simula después la operación final: retira la publicación ficticia, comprueba un único enlace y retira el archivo **ficticio original**. Comprueba que ambos nombres han desaparecido.
- Limpia exclusivamente sus propios archivos y el directorio GUID recién creado, sin `Remove-Item -Recurse`, acceso de escritura a `C:\VIEWTV\media` ni cambios de torrent.

Resultados:

```text
LECTOR_EXCLUSIVO_BLOQUEA=PASS
TERCER_HARDLINK_EXCLUIDO=PASS
RECUPERACION_TRAS_INTERRUPCION=PASS
RETIRADA_AMBAS_REFERENCIAS_SANDBOX=PASS
FICHEROS_REALES_ELIMINADOS=0
TORRENTS_REALES_MODIFICADOS=0
```

**Limitación:** es una simulación de recuperación usando un diario ficticio, no un journal durable con garantías de atomicidad frente a apagón real; tampoco se ha medido como recuperado un número de bytes del disco en producción.

## Validación y respaldo

- **55/55 pruebas unitarias nuevas** del preflight: propiedad, hash, marcas por perfil, peticiones, documentos repetidos, archivos extra, rutas traversal, nombres reservados de Windows, torrents activos, SQL inconsistente, comprobaciones de ruta Jellyfin y permisos.
- Ruff PASS en el código Python de esta fase.
- **Suite completa backend 1109/1109 PASS** (2 advertencias deprecadas de dependencias externas), ejecutada en contenedor de pruebas sin red.
- Preflight real solo lectura `PREFLIGHT_0018=REALIZADO_SOLO_LECTURA`, con cuatro películas bloqueadas y cero escrituras.
- Laboratorio NTFS Windows PASS, sin medios reales modificados.
- **Respaldo previo verificado:** `/home/viewtv/viewtv-backups/preflight-retirada-0018-pre-20261126-201604.tar.gz`; SHA-256
  `a6af7ba87b9ef9151cb9c6a0004ff98dd8a4d05b0da5f099887c28954441fa3e`; se comprobó `tar -tzf`.
  No incluye PINs, `.env`, bases de datos, archivos de películas ni torrents.
- Se mantiene el respaldo y rollback del hito 0017. No hubo migración SQLite ni cambio de imágenes/volúmenes productivos en este hito.

## Requisitos exactos para el siguiente hito: retirada verdadera

**NO habilitar un botón «Eliminar» antes de cumplirlo todo:**

1. Crear **una identidad de administrador de biblioteca separada de los PINs de los perfiles**, autenticada en el host Windows o con secreto propio y controles antiabuso; nunca escribir un PIN en scripts, GitHub o salida del asistente.
2. Obtener aprobación explícita para **una película exacta**, indicando qué perfiles dejarían de tenerla, si el torrent está sembrando, las rutas afectadas, el espacio lógicamente ocupado y los límites de espacio recuperable.
3. Congelar/reservar de forma exclusiva la publicación y el estado qBit durante la operación (sincronizar con publicador y worker); comprobar todas las referencias de torrents, streams de Jellyfin y enlaces ajenos.
4. Exigir que el torrent propio esté realmente detenido y que su **lista completa de archivos** sea exactamente la que se va a liberar. Si existen extras, rutas compartidas, enlaces adicionales o lectores, impedir el borrado.
5. Implementar el ejecutor de Windows con **diario durable de fases**, operaciones idempotentes, recuperación segura tras corte real y pruebas de errores parciales, restauración o retirada conservadora.
6. Medir espacio libre del volumen Windows antes/después y distinguir bytes lógicos de bytes realmente liberados. No prometer liberación si otro enlace permanece.
7. Ejecutar los ensayos de múltiples películas/perfiles/torrents exclusivamente en sandboxes. Solo entonces valorar una retirada real, película por película y **con autorización concreta**.

**Orden inalterado:** cerrar eliminación y espacio → app Samsung Tizen profesional → «VIEWTV Momentos».

La app Samsung queda **pendiente**; no debe confundirse la existencia de `/tv.html` y de la PWA con una aplicación Tizen instalable ya probada.
