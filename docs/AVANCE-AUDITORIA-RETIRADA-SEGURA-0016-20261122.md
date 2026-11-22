# VIEWTV 0016 — Auditoría de retirada física y compatibilidad del publicador Windows

**Fecha:** 22/11/2026, zona Europe/Madrid.
**Rama:** `viewtv-seguimiento-descargas-0012`; PR #2 debe continuar OPEN/DRAFT.
**Prioridad solicitada:** acabar gestión de espacio/caché y películas vistas **antes** de app Samsung; «VIEWTV Momentos» después.
**Estado:** diagnóstico real de solo lectura y ensayo destructivo exclusivamente en un sandbox nuevo. **Borrado real de películas NO habilitado.**

## Hallazgo bloqueante descubierto y corregido

Tras las migraciones SQLite 0014 (identidad de carátula) y 0015 (vistas/retiradas),
`python -m worker.organization_windows_cli status` devolvía
`{"estado":"rechazada","motivo":"validacion_o_servicio"}` en la API activa:
`_schema_0013()` exigía exactamente `0013_cola_organizacion` y, por tanto,
también podía bloquear el comando `sync` de la tarea Windows.
**Los contenedores saludables no detectaban ese problema.**

- Ahora `_schema_0013()` acepta **solo** las revisiones explícitamente
  compatibles `0013_cola_organizacion`, `0014_identidad_tmdb_solicitud` y
  `0015_gestion_espacio_vistas`, comprobando además las columnas obligatorias
  de las tablas de solicitudes, descargas y medios antes de permitir publicar.
  Las versiones desconocidas siguen rechazadas. No se cambió la semántica
  del lease ni las operaciones de publicación.
- Test de regresión con esquema real SQLite temporal: revisiones 0013/0014/0015
  aceptadas; revisión desconocida y tabla incompleta rechazadas.
- Imagen API `viewtv:publicador-compatible-api-0016` construida sobre
  `viewtv:gestion-espacio-api-0015`, únicamente con ese CLI corregido.
  Overlay `deploy/compose.publicador-compatible-api-0016.yaml`.
- Tras validar el stack anterior y mantener las banderas de descarga/organización,
  se recreó **solo** `viewtv-api-1`. Worker 0015, frontend 0015,
  catálogo, Jellyfin, medios y tarea Windows quedaron intactos.
- **Confirmado en producción:** `status` devuelve
  `{"estado":"listo","modo":"general","after_id":3,"allowed_download_id":null}`.
  El script Windows de publicación, ejecutado con `-Mode Preflight`
  exclusivamente, devuelve **`PREFLIGHT_PUBLICADOR_WINDOWS_0013_OK`**.
  API healthy y smoke GET **10/10 PASS**.
- No se llamó a `claim`, `sync`, `prepare`, `confirm` ni se creó
  ningún torrent. Se restauró capacidad de preflight, no se afirma
  publicación nueva realizada.

## Auditoría real de propiedad: la biblioteca tiene hardlinks NTFS

Los vídeos están publicados mediante `CreateHardLinkW`, no mediante
copia separada. Ocupación previa: biblioteca de películas **24,31 GiB**
y originales **24,31 GiB**. Estas dos cifras pueden contar
**los mismos bloques**, por lo que no son 48,62 GiB recuperables.

**Auditoría Windows nativa, solo lectura**
`scripts/viewtv_windows_retirada_auditoria_0016.ps1 -Mode Audit`:

- **2 diarios** de publicación detectados; **2 diarios válidos**,
  huella SHA-256 del manifiesto idéntica a la del publicador 0013;
  **2 archivos físicos** cuyo origen y destino comparten identificador
  de archivo y volumen NTFS, con tamaño y contador de enlaces concordantes.
- **0 diarios rechazados** y **1 diario** de ID histórica ≤3.
- **1 carpeta de película sin diario válido**: se considera de
  titularidad **no demostrada** y queda excluida de retirada.
- La auditoría comprueba rutas relativas estrictas, padres sin
  reparse/junction, archivo regular, nombre NTFS, estructura de
  publicación, un vídeo único, ausencia de ficheros adicionales,
  hash del manifiesto y vínculo de archivo real. Nunca interpreta
  un título como prueba de identidad. No divulga nombres, rutas ni hashes.
- `-Mode Audit` carece de instrucciones de borrar archivos.

**Cruce Jellyfin y SQLite, también solo lectura**:

- SQLite tiene **2 descargas organizadas** y no conserva una relación
  directa única de sus solicitudes con `medio.jellyfin_id` o `medio.tmdb_id`
  (0 relaciones estructuradas directas). No se han creado esas relaciones
  retrospectivamente por coincidencia de nombre.
- Jellyfin devuelve **4 películas locales con ID y ruta** consultando
  `GET /Items?Recursive=true&IncludeItemTypes=Movie&Fields=Path`.
  La consulta individual `GET /Items/{id}` no funcionaba para este
  servidor, por lo que el script utiliza la lista paginada de ítems.
- Comparación estricta de ruta de vídeo del manifiesto protegido frente
  a la ruta del ítem de Jellyfin y la identidad de su `Medio`:
  **2 coincidencias únicas** de película y publicación; cero ambiguas
  entre las dos publicaciones con diario. Los datos privados
  se manejan en memoria local y **no se imprimen**.
- Un programa de eliminación futuro deberá repetir este cruce
  en el momento exacto de autorizar; los tres sondeos independientes
  **NO forman una transacción atómica ni una autorización de borrado**.

**qBittorrent GET únicamente**:

- Las dos descargas organizadas siguen presentes y tienen hash,
  etiqueta de propiedad `viewtv-descarga-{id}` y carpeta original
  compatibles con ViewTV; sin errores de comunicación.
- **2 torrents EN USO** en esa lectura, **0 detenidos**.
- Por tanto, la retirada se **bloquea**: no parar, borrar ni retirar
  torrents activos. Tampoco es posible afirmar que eliminar un
  hardlink publicado libere espacio mientras exista el original.
- Se añadió `worker/retirement_guards.py`, un evaluador puro y
  conservador que rechaza torrents ajenos, ambiguos, sin etiqueta
  exclusiva, con carpeta distinta, incompletos, descargando,
  comprobando, compartiendo/seeding o con estado desconocido.
  Incluso para `pausedUP` o `stoppedUP`, solo devuelve
  `apto_parcialmente`: aún se requieren todas las demás pruebas.

## Ensayo de eliminación con datos ficticios, NO producción

`powershell.exe -File scripts/viewtv_windows_retirada_auditoria_0016.ps1
-Mode Sandbox`:

1. Crea **un directorio nuevo con GUID** bajo el temporal de la
   propia sesión Windows.
2. Crea un archivo de texto ficticio y su hardlink mediante
   `CreateHardLinkW`.
3. Compara identificadores NTFS y exige **exactamente 2 enlaces**.
4. Mantiene un descriptor abierto exclusivo y demuestra que la
   operación de inspección no puede aprobarse mientras esté ocupado.
5. Cierra el descriptor y retira **solo el hardlink ficticio**.
   Comprueba que el original permanece idéntico, con 1 enlace.
6. Limpia únicamente los archivos ficticios propios del directorio
   recién creado. Nunca hace operaciones de borrado sobre
   `C:\VIEWTV\media`, qBittorrent, Jellyfin ni sus diarios.

Resultado: **`ENSAYO_SANDBOX_NTFS_BORRADO_SOLO_COPIA=PASS`**,
`ORIGINAL_SANDBOX_CONSERVADO=SI`, `BORRADOS_PRODUCCION=0`.
El borrado del hardlink de biblioteca **no significa** liberar los
bytes del original, ni certifica la prevención de TOCTOU para
una operación de producción futura.

## Batería de comprobaciones

- Pruebas específicas de compatibilidad del publicador, estados del
  servicio y rechazo qBit: **32/32 PASS**. Suite backend completa
  **1042/1042 PASS**, con 2 advertencias de deprecación externas.
  Ejecutada sobre código de la rama con red deshabilitada.
- Ruff de código y sondas Python: PASS.
- Real: publicador `status` listo, preflight de PowerShell PASS,
  smoke de solo lectura **10/10**, API healthy.
- No se añadieron endpoints destructivos, escritura sobre multimedia,
  lectura de `.env` mostrada ni migración SQLite nueva.

## Copia previa

`/home/viewtv/viewtv-backups/retirada-ntfs-compatibilidad-pre-20261122-230050.tar.gz`
SHA-256:
`a7956ddf51895883d8448b0a90082ba5c602eebe09e4b3016fcf570fa1890b53`.
Comprobados `sha256sum` y `tar -tzf` **antes de editar**. La
copia incluye CLI original, auditoría/planes anteriores, scripts Windows
y documentos, sin `.env`, `.bak`, imágenes ni torrents.
Se conserva el respaldo previo de SQLite de 0015; esta tarea
no ha ejecutado migraciones ni escrito SQLite.

## Lo que falta para liberar películas de verdad

**Estado actual: BLOQUEADO de forma segura.** Ninguna película real
ha sido borrada ni seleccionada por el asistente. Las dos
publicaciones verificadas aún tienen torrents en uso; la carpeta
sin diario tampoco es elegible. El botón de ViewTV sigue llamándose
**«Solicitar retirada»** y no promete liberar espacio.

Para cerrar esta prioridad **antes** de la app Samsung, queda implementar
y verificar conjuntamente:

1. **Autorización diferenciada de administrador de biblioteca**:
   el PIN de un perfil que la marca como vista no le da autoridad
   para borrarla a los demás perfiles. Confirmar ID exacto, título,
   destino, tamaño y repercusión en torrents y Jellyfin.
2. **Un único preflight atómico en el host Windows**, que correlacione
   `medio.id`, ruta Jellyfin, manifiesto publicado, descarga SQLite
   organizada y qBit, incluidos casos sin ID directo; verificar que
   no existen lectores/streams abiertos ni enlaces ajenos y que no
   hay cambios de estado mientras se decide.
3. **Política de seeding y qBittorrent**: los torrents en uso no se
   pueden retirar. Para liberar bloques físicos, habría que
   autorizar **por separado** detener y retirar únicamente
   torrents propios, conservar o liberar sus archivos originales
   solo tras comprobar unicidad de enlaces/propiedad y la relación
   de cada archivo con una sola película. No borrar torrents ajenos.
4. **Diario durable de retirada Windows y reconciliación**:
   exclusión de carreras con publicador/escaneo,
   estados planificado → inmovilizado → verificado → retirado,
   reintentos de solo lectura ante fallos, nunca repetir borrados
   ambiguos ni realizar un `Remove-Item -Recurse` indiscriminado.
5. **Medición real** de espacio libre antes y después de retirada
   aprobada, aceptando diferencias por asignación/otros procesos;
   no usar tamaños de hardlinks como estimación garantizada.
6. **Pruebas NTFS aisladas ampliadas**: múltiples hardlinks,
   ejecución concurrente con Jellyfin/qBit, archivos abiertos,
   reparse/junction, fallo entre fases, recuperación y revocación
   de aprobación, confirmación de otro perfil.
7. **Cuota real de temporales** si aparecen escritores propios;
   la caché ViewTV continúa vacía y su configuración de 80 GiB
   sigue siendo solo un ajuste, no una política aplicada a Jellyfin.

**Orden actualizado:** cerrar este sistema sin perder datos →
app Samsung instalable/profesional a color → «VIEWTV Momentos».

## Reversión y seguimiento

La API 0016 deriva únicamente de la imagen 0015, y los overlays
anteriores permanecen disponibles. Para revertir la **corrección de
compatibilidad de código** sería suficiente recomponer la API con
la imagen `viewtv:gestion-espacio-api-0015`; **no se recomienda**
porque reproduce el rechazo del publicador contra SQLite 0015.
No hacer downgrade SQLite ni restaurar la base sin un incidente real.
El despliegue probado está preparado mediante
`scripts/viewtv_publicador_compat_deploy_0016.sh check/deploy`.

Hecho: auditoría real, sandbox y recuperación de preflight.
Supuesto a validar: la titularidad física de cada original y
la ausencia de terceros/otros enlaces antes de cualquier eliminación.
Pendiente: ejecutor seguro y autorización del administrador.
