# VIEWTV 0026 — Custodia comprobada de archivos adicionales qBittorrent

**Fecha:** viernes 27 de noviembre de 2026 (Europa/Madrid).
**Repositorio:** `wizzadrds/viewtv`; rama exclusiva `viewtv-seguimiento-descargas-0012`; PR **#2 OPEN/DRAFT**, no fusionado.
**Prioridad:** seguridad de retirada y espacio antes de Samsung Tizen y VIEWTV Momentos.
**Alcance:** consultas read-only y evaluador puro; sin despliegues en la API ni paradas de torrents.

## Objetivo y resultado

Después de que un perfil marcara vista una película y pidiera su retirada (hito 0024), la revisión 0025 ya detecta cambios entre dos fotografías integrales de SQLite/Jellyfin/qBit, los diarios de publicación y NTFS. La siguiente barrera necesaria era distinguir **estado real reportado por qBit**, **propiedad e identidad del torrent** y **archivos ajenos al manifiesto** sin permitir que la clasificación «metadato», «100 % descargado» o «detenido» autorice una operación destructiva.

**El diagnóstico de producción ha confirmado que los DOS torrents analizados no están en reposo según la política. Los cuatro archivos extra siguen protegidos. Se prohíbe expresamente detener, pausar, reetiquetar, eliminar o alterar archivos/torrents como parte de esta prueba.**

Salida de la ejecución real del nuevo control:

```text
CUSTODIA_QBIT_0026=SOLO_GET
DOBLE_SNAPSHOT_SQL_JELLYFIN_QBIT=COINCIDENTE
DOBLE_EVIDENCIA_DIARIOS_Y_NTFS=COINCIDENTE
DESCARGAS=2
TORRENT_COMPLETO_Y_EN_REPOSO_REPORTADO=0
TORRENT_NO_EN_REPOSO_O_INCOMPLETO=2
TORRENT_PROPIEDAD_O_RUTA_INCONSISTENTE=0
TORRENTS_CON_ARCHIVOS_EXTRA=2
ARCHIVOS_QBIT=6
ARCHIVOS_PUBLICADOS_CORRELACIONADOS=2
ARCHIVOS_EXTRA_PROTEGIDOS=4
EXTRAS_CON_NOMBRE_NO_NORMALIZABLE=2
EXTRAS_TIPO_VIDEO=0
EXTRAS_TIPO_SUBTITULO=0
EXTRAS_TIPO_METADATO=4
EXTRAS_TIPO_OTRO=0
BYTES_LOGICOS_EXTRAS_PROTEGIDOS=488
ARCHIVOS_CON_TAMANO_INCOMPATIBLE=0
ARCHIVOS_CON_PROGRESO_INCOMPLETO=0
ARCHIVOS_CON_PRIORIDAD_EXCLUIDA=0
BYTES_LOGICOS_EXTRAS_NO_SON_ESPACIO_RECUPERABLE=SI
EXTRAS_CONSERVADOS=SI
QUIETUD_TRANSACCIONAL_QBIT_JELLYFIN=NO
PERMISO_BORRADO_FISICO=NO
ARCHIVOS_ELIMINADOS=0
TORRENTS_MODIFICADOS=0
```

**Interpretación prudente:**

- Dos torrents identificados de forma coherente por hash, etiqueta exclusiva VIEWTV, raíz de guardado Windows y diario asociado. Esta identidad de la descarga **no prueba propiedad exclusiva de todos sus archivos**.
- No hay estado reportado `pausedUP` o `stoppedUP` con progreso completo para ninguno; **no se ha tocado el estado real**.
- El archivo principal de cada uno coincide por nombre y tamaño con su diario Windows; los cuatro ficheros restantes **no fueron publicados** y **no pueden considerarse desechables**, aunque tengan extensiones de metadatos. Dos no satisfacen la política conservadora de nombres.
- 488 bytes son solo **tamaño lógico qBit**, sin garantía de presencia/bloques NTFS ni relación con un posible espacio físico recuperable; **cero bytes físicos atribuidos a retirada**.
- El resultado no incluye rutas, títulos, IDs de perfil, nombres de archivos ni infohash; se publican solo cifras agregadas.

## Componentes del hito

### `worker/retirement_qbit_custody_0026.py`

Motor Python puro, sin cliente HTTP, sin SQLite, sin operaciones de Windows ni autorizador:

1. Exige consulta qBit completa con una entrada por descarga organizada, diario para cada descarga y correspondencia unívoca.
2. Cruza hash, etiqueta exclusiva `viewtv-descarga-N`, raíz Windows conocida y hash de diario/manifiesto de publicación. Informa inconsistencias de procedencia sin declarar propiedad exclusiva de extras.
3. Diferencia torrent **en reposo reportado y completo** frente a **no en reposo o incompleto**. Nunca confunde `uploading`, `stalledUP`, `checkingUP`, `moving` o `queuedUP` con un estado de reposo. Un torrent en reposo sigue sin permiso de borrado.
4. Examina **todos** los archivos qBit (incluidos extras) con nombre único, tamaño positivo, progreso válido y prioridad no manipulada. Compara manifestaciones publicadas por ruta relativa y tamaño; separa los extras por tipo **solo como inventario**, no como justificación para descartarlos.
5. Falla cerrado si faltan registros, hay duplicados, tamaño/progreso inválidos o un diario no corresponde a la descarga. Nunca ofrece plan de eliminación, capacidad de cambiar torrents ni autorización física.
6. Todo resultado incluye `autoriza_borrado_fisico=false`, `bloqueo_jellyfin_y_qbit_transaccional=false`, `archivos_eliminados=0`, `torrents_modificados=0`.

### `scripts/viewtv_retirada_custodia_qbit_0026.py`

Ejecuta en WSL, únicamente con consultas:

1. Primer inventario NTFS nativo Windows de solo lectura.
2. Primer snapshot SQL/Jellyfin/qBit y primera lectura de diarios con `O_NOFOLLOW`.
3. Segundo snapshot completo y segunda lectura de diarios.
4. Segundo inventario NTFS.
5. Requiere coincidencia íntegra mediante la barrera 0025; después emite **solo contadores permitidos** sobre qBit.

Cualquier error o cambio entre fotografías produce `BLOQUEADA_FUENTE_NO_CONFIABLE` sin filtrar identidades o secretos. **La consulta no bloquea nuevos clientes, streams ni procesos qBit** y no puede prevenir el problema ABA (estado cambia y vuelve al mismo antes del segundo GET).

### Pruebas

- `backend/tests/test_custodia_qbit_0026.py`: estados qBit de carga, comprobación, pausa, parada y movimiento; extensión de metadatos/vídeos/subtítulos; nombres NTFS no normalizables; etiquetas, hash, raíz, tamaños, prioridades, archivos excluidos, duplicados, progreso no válido y ficheros extra protegidos.
- `backend/tests/test_custodia_runner_0026.py`: corrige el riesgo de confundir GET dobles estables con bloqueo: pruebas sintéticas de drift qBit/NTFS/diario, fallo de fuente, salida agregada segura y prohibición constante de borrar.
- **64/64 pruebas específicas PASS**, Ruff PASS.
- Smoke real de solo lectura **10/10 PASS**. **Suite completa backend 1424/1424 PASS** en contenedor de pruebas sin red; 2 avisos de deprecación en dependencias externas. Ruff PASS. La revisión read-only por película mantiene la solicitud bloqueada y no concede permisos físicos.

## Otros bloqueos comprobados

- La petición real por película está registrada, pero **otro perfil aún no la marcó vista**, sin consentimiento administrativo independiente ni permiso físico. No cambiar las marcas de otro perfil.
- El publicador Windows instalado es anterior al protocolo de mutex 0022 y su tarea programada sigue habilitada. El preflight 0023 devuelve **4 bloqueos**: helper ausente, versión antigua, tarea no deshabilitada e instalación no validada. No se ha sustituido ni detenido esa tarea.
- Ningún código productivo de Jellyfin o qBit utiliza el mutex Windows común; **no hay mecanismo de exclusión efectivo** entre reproducir, compartir torrent y liberar hardlinks.
- Los cuatro archivos adicionales qBit **no se pueden borrar, excluir ni reconfigurar** sin prueba explícita de propiedad exclusiva y autorización granular por película. Tampoco se debe detener el torrent real para obtener un estado «verde».
- Sin ejecutor productivo de retirada, no hay liberación medible de espacio de películas reales; el ensayo NTFS 0021 se limita a ficheros ficticios.

## Respaldo previo y cambios productivos

Antes de editar ningún archivo existente se archivaron y verificaron fuentes, tests y documentos originales:
`/home/viewtv/viewtv-backups/custodia-qbit-0026-pre-20261127-171210.tar.gz`
SHA-256: `60e112d90264f63c80aaae17ea5737a38c5b1aaba8b8711da324c9d1ef96a8a9`; `tar -tzf` verificado.

No contiene películas, SQLite, secretos, credenciales ni torrents. **No hay migraciones, nuevas imágenes ni cambios de contenedores, procesos, tareas programadas, descargas, marcas de perfiles o medios**.

## Siguiente fase imprescindible

El próximo avance no debe consistir en suavizar los bloqueos para conseguir más candidatos artificialmente. Se requiere un **protocolo transaccional real entre qBit, Jellyfin, Windows y el administrador**:
- Actualizar el publicador antiguo bajo mantenimiento supervisado y autorizado, después de respaldar y asegurar la tarea (0023).
- Proteger nuevas sesiones Jellyfin, no solo consultar `/Sessions` dos veces.
- Coordinar qBit sin detener o manipular torrents sin autorización específica ni arriesgar archivos extras.
- Exigir aprobación administrativa independiente para una única película y sus perfiles, firma vigente, revalidación de evidencia, uso único y journal durable.
- Confirmar todos los hardlinks y medir el espacio NTFS realmente recuperado solo después de que las condiciones se cumplan.

**Orden:** espacio y retirada seguros → app instalable Samsung Tizen → VIEWTV Momentos.
