# VIEWTV 0025 — Doble instantánea de SQLite, Jellyfin, qBit y NTFS antes de revisar una retirada

**Fecha:** 27 de noviembre de 2026 (Europa/Madrid).
**Repositorio:** `wizzadrds/viewtv` · rama `viewtv-seguimiento-descargas-0012` · PR #2 **OPEN/DRAFT**, sin fusionar.
**Estado:** control local de coherencia de fuentes de solo lectura, sin autoridad destructiva y sin despliegue en la API.

## Problema que se resuelve

La revisión por película 0024 contrastaba el detalle de las solicitudes y marcas de perfiles **dos veces**, y hacía dos auditorías Windows/NTFS, pero recuperaba **una única fotografía conjunta** de descargas SQLite, rutas/identidades Jellyfin y estados/listas de archivos qBittorrent. Por tanto, un cambio durante la propia consulta podía no ser observado por el preflight.

La fase 0025 toma **dos fotografías independientes completas** de las mismas fuentes, lee **dos veces todos los diarios Windows**, y compara **dos auditorías NTFS**. Cualquier discrepancia, fuente ambigua, respuesta imposible de serializar o cambio incluso en una película no seleccionada hace que la revisión **no certifique coherencia**.

**Dos snapshots iguales NO bloquean Jellyfin ni qBittorrent**: si el torrent cambia después del último GET, o cambia y vuelve al estado anterior entre dos GET, no se puede garantizar ausencia de carreras. Esta fase solo detecta discrepancias observables y **no convierte una petición en permiso de borrado.**

## Implementación

### Motor puro

`worker/retirement_evidence_stability_0025.py`:

- Verifica que ambos snapshots tengan las estructuras esperadas: películas, perfiles activos, descargas, Jellyfin con paginación completa `estado=ok` y datos de qBit.
- Compara las fotografías serializadas canónicamente con claves ordenadas, rechazando valores no JSON, NaN, respuestas gigantes y cualquier diferencia en estado, progreso, propiedad, rutas, tipos, identificación, tamaños y prioridades de archivos.
- Verifica que cada diario esté identificado por un ID positivo único, tenga un registro con el mismo `download_id` y SHA-256 de 64 caracteres hexadecimales. Se comparan registros y SHA de **todas** las descargas observadas.
- Comprueba las pruebas NTFS por ID de descarga, SHA del diario, `ntfs_verified` booleano y número de archivos; rechaza duplicados y datos incompletos. No imprime la evidencia ni su huella.
- Solo devuelve totales y `habilita_borrado_fisico=false`, `inmovilizacion_qbit_y_jellyfin=false`.

### Integración con el caso de solicitud real

El script local `scripts/viewtv_retirada_revision_solicitud_0024.py` pasa a consultar, en orden:

1. **Primera** auditoría Windows NTFS de los hardlinks.
2. **Primer** detalle SQL privado de la película exacta y año.
3. **Primer** snapshot conjunto SQL/Jellyfin/qBit.
4. **Primera** lectura privada de todos los diarios.
5. **Segundo** snapshot completo SQL/Jellyfin/qBit.
6. **Segunda** lectura de todos los diarios.
7. **Segundo** detalle privado de la película.
8. **Segunda** auditoría Windows NTFS.

Si cualquier par no coincide, devuelve `BLOQUEADA_DATOS_NO_CONFIABLES` sin imprimir perfiles, título, rutas ni hashes. Solo si coincide todo aplica **el preflight fail-closed 0018** y el evaluador de perfiles/solicitud 0024. Se conserva exactamente el contrato anterior de excepción `RevisionNoConfiable` para los consumidores del script.

**No se ha añadido endpoint web de autorización, parada de torrent, escritura SQL, operación de Windows ni eliminación de hardlinks**. El usuario sigue controlando su marca «vista» y puede cancelar su petición desde la interfaz existente.

## Auditoría real de solo lectura

El caso de película con una petición válida seguía en el mismo estado:

```text
REVISION_SOLICITUD_0024=SOLO_LECTURA
ESTADO=PENDIENTE_REVISION_BLOQUEADA
DOBLE_SNAPSHOT_SQL_JELLYFIN_QBIT=COINCIDENTE
DOBLE_INVENTARIO_DIARIOS_NTFS=COINCIDENTE
EXCLUSION_TRANSACCIONAL_QBIT_JELLYFIN=NO
PERFILES_ACTIVOS=2
PERFILES_CON_VISTO=1
PERFILES_SIN_VISTO=1
SOLICITUDES_PENDIENTES=1
SOLICITUD_VALIDA_REGISTRADA=SI
VISTA_EN_TODOS_LOS_PERFILES=NO
BLOQUEO_FALTA_AUTORIZACION_ADMINISTRADOR=SI
BLOQUEO_HAY_PERFILES_SIN_MARCAR_VISTA=SI
BLOQUEO_TORRENT_ACTIVO_O_INCOMPLETO=SI
BLOQUEO_TORRENT_ARCHIVOS_NO_VERIFICABLES=SI
APROBACION_ADMINISTRATIVA_EMITIDA=NO
PERMISO_BORRADO_FISICO=NO
ARCHIVOS_ELIMINADOS=0
TORRENTS_MODIFICADOS=0
```

Además:
- Las **cuatro** películas de la biblioteca continúan sometidas a los bloqueos 0018.
- Probe Jellyfin `/Sessions` GET/GET (0021): **0 sesiones reportadas y 0 reproducciones en ese instante**, **sin bloqueo transaccional**. No se deduce garantía de no reproducción futura.
- Inventario qBit 0020: **6 archivos** en dos descargas, **2 publicados exactamente**, **4 metadatos extras protegidos**, 488 bytes lógicos, 2 rutas no normalizables por la política estricta. No se ha detenido torrent alguno.
- Smoke de producción 0012: **10/10 PASS**. No hay migraciones ni reinicios de API/frontend/worker/Jellyfin.

## Pruebas, respaldo y seguridad

`backend/tests/test_retirada_estabilidad_0025.py` prueba cambios de estado/progreso del torrent, etiquetas, hash, directorio, resultados de consulta qBit, archivos y prioridades, rutas/IDs Jellyfin, descargas, marcas por perfil, solicitudes, nuevos perfiles y modificaciones de diario/NTFS. Prueba NaN, archivos duplicados, tamaños y datos no serializables. Incluye tests del flujo real 0024 con mock de **dos snapshots que difieren**, obligándolo a bloquear sin filtrar secretos.

- **91/91 pruebas combinadas 0024/0025 PASS**, Ruff PASS.
- **Suite backend completa 1360/1360 PASS**, con 2 avisos de deprecación de dependencias externas; contenedor de pruebas sin red. La auditoría NTFS final conserva 2 diarios válidos, 0 borrados y 1 carpeta sin diario protegida. Ruff PASS para los archivos nuevos y modificados.

**Copia previa al trabajo**:
`/home/viewtv/viewtv-backups/estabilidad-evidencia-0025-pre-20261127-170310.tar.gz`
SHA-256: `92cca97869620f02b44688dd1ca40696481cb4490c60376a588eb2c5a682a0bd`.
`tar -tzf` verificado. Solo código y documentación anteriores; sin `.env`, claves, SQLite productiva ni películas. Sin cambios de esquema de base de datos.

## Bloqueos que siguen vigentes

1. Al menos otro perfil todavía no ha marcado la película como vista; **no alterar su marca para desbloquear una solicitud ajena**.
2. Torrent aún activo y con archivos extra no respaldados por el diario de publicación para retirada; no detenerlo ni borrar metadatos sin autorización y prueba de propiedad exclusiva.
3. Aprobación administrativa por título aún no provisionada en un host seguro; el prototipo 0019 no concede permisos reales.
4. El publicador Windows instalado es anterior al mutex 0022 y su tarea sigue `READY`; la actualización requerirá respaldo, ventana y autorización supervisada 0023.
5. No existe un protocolo atómico de exclusión entre **Jellyfin (nuevos streams), qBittorrent (seeding/escrituras), el publicador Windows y el ejecutor de retirada**. Ni dos GET ni un mutex cooperativo en un único proceso lo sustituyen.
6. El ejecutor durable por película, cancelación, medición física de bytes liberados y recuperación ante apagón siguen pendientes. Las pruebas de hardlinks 0020/0021 son sandbox.

**Orden sin cambios:** retirada y gestión de espacio segura → app Samsung Tizen instalable → VIEWTV Momentos.
