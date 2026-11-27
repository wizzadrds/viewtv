# VIEWTV 0022 — Mutex Windows compartido entre publicador y preflight de retirada

**Fecha:** viernes 27 de noviembre de 2026, Europa/Madrid.
**Repositorio:** `wizzadrds/viewtv`; **rama exclusiva:** `viewtv-seguimiento-descargas-0012`.
**PR #2:** abierto, borrador, **sin fusionar**.
**Orden exigido:** seguridad, retirada y espacio → app Samsung instalable → VIEWTV Momentos.

## Resultado

Se ha implementado **en el código fuente** un protocolo de exclusión nativa de Windows por mutex de nombre fijo y compartido. El publicador debe poseer el mutex durante **todo** `Process-One` —desde antes de leer política/reintentar escaneos/reclamar una tarea hasta después de la reconciliación y publicación—. Una auditoría de retirada independiente usa **el mismo nombre de mutex** y sigue siendo exclusivamente de lectura. Un ensayo real en procesos Windows distintos confirmó que solo uno lo posee simultáneamente y que se libera después de terminar o interrumpir el subproceso ficticio.

**Advertencia crítica: el publicador Windows que ya funciona NO se ha sustituido ni reiniciado.** Solo se modificó el código en el repositorio, y el proceso operativo instalado podría seguir usando el script anterior sin mutex. Por tanto, **no hay hoy una exclusión global efectiva que cubra producción**. Solo se ha validado el mecanismo, no su implantación simultánea en todas las autoridades.

**Tampoco entran en el mutex qBittorrent, Jellyfin ni descargas de otros programas.** El mutex es *cooperativo*: protege únicamente procesos que usan explícitamente el mismo nombre. No impide que un reproductor abra un archivo, que qBit escriba o reanude un torrent ni que una fuente no cooperativa actúe en `C:\VIEWTV\media`. Las cuatro películas permanecen bloqueadas, y no se habilita ningún ejecutor de borrado real.

## Componentes

### 1. Protocolo Windows

Archivo nuevo `scripts/viewtv_windows_media_lock_0022.ps1`:

- Nombre **invariable** `Global\VIEWTV-MEDIA-EXCLUSIVA-PUBLICACION-RETIRADA-0022` tanto para `publicador` como para `retirada`.
- Adquisición **no bloqueante** con `System.Threading.Mutex.WaitOne(0)`. Si otro proceso ya lo posee, falla cerrado antes de tocar la publicación. No se acepta personalizar el nombre del mutex de producción.
- `ReleaseMutex` y `Dispose` explícitos en `finally` del publicador y del auditor; si ocurre `AbandonedMutexException`, se libera la posesión adquirida y **se aborta** esa operación para revisión. Nunca se interpreta el abandono como permiso para continuar.
- Los tests únicamente usan `Global\VIEWTV-MEDIA-SANDBOX-0022-{GUID}` mediante un propósito especial `sandbox`; ese modo no permite obtener permiso de medios reales.
- Una entidad ajena podría mantener el nombre para provocar denegación de servicio; el mutex **no es autenticación, ni autorización de administrador, ni una prueba de propiedad de archivos**. Una publicación o retirada debe seguir demostrando identidad, ACL, lease, diarios y permisos.

### 2. Publicador con guardia antes de reclamar trabajos

Modificación acotada de `scripts/viewtv_windows_publicador_0013.ps1`:

- En `Process-One`, si la biblioteca auxiliar 0022 no está disponible, **falla cerrado**.
- Carga el helper y obtiene el mutex `-Proposito 'publicador'` **antes** de `Get-ViewtvPolicy`, `Retry-PendingScans` y `Invoke-ViewtvAuthority 'claim'`.
- Mantiene el mutex durante la preparación, verificación de qBit por los contratos existentes, creación de hardlinks, movimiento, confirmación de cola y solicitud de escaneo Jellyfin. Devuelve/libera por un `finally` en retorno normal o error.
- Se mantiene inalterado el alcance del contrato de publicación 0013: no incorpora instrucciones de borrado, pausa, eliminación de torrents ni modificaciones de SQLite adicionales.
- Los modos **`Library` y `Preflight`** no reclaman trabajo, ni crean/borran archivos. El preflight nuevo desde el worktree comprobó `PREFLIGHT_PUBLICADOR_WINDOWS_0013_OK` sin cambiar el servicio.

**Despliegue pendiente y delicado:** la instalación del nuevo publicador debe hacerse como una actualización supervisada por el administrador de la máquina Windows, con respaldo previo, revisión de ACL del directorio protegido, comprobación de que el proceso anterior ha terminado sin publicación activa, prueba exacta de versión del script instalado y mecanismo de reversión seguro. Nunca se debe instalar la nueva versión mientras el antiguo publicador pueda reclamar simultáneamente trabajos: este no respeta el mutex. **No se ha realizado ese despliegue ni detenido ningún proceso productivo.**

### 3. Auditoría de retirada bajo el mismo mutex

`scripts/viewtv_windows_retirada_mutex_auditoria_0022.ps1`:

- No tiene parámetros de ruta, película, título o torrent y **no tiene modo destructivo**.
- Adquiere el mutex `-Proposito 'retirada'`, ejecuta en modo `Audit` la auditoría Windows NTFS 0016 y valida el formato de su salida.
- Se limita a demostrar que la auditoría puede operar dentro del protocolo de exclusión común; **no borra originales, no modifica enlaces, no pausa torrents, no emite tickets administrativos y no habilita ejecución**.
- La propia salida advierte `PUBLICADOR_PRODUCCION_INTEGRADO=NO_VERIFICADO`, `BLOQUEO_QBIT_Y_STREAMS=NO` y `AUTORIZA_ELIMINACION=NO`.

Resultado real:

```text
RETIRADA_0022_MUTEX_COMPARTIDO=ADQUIRIDO
RETIRADA_0022_AUDITORIA_NTFS=SOLO_LECTURA
RETIRADA_0022_DIARIOS_NTFS_VERIFICADOS=SI
RETIRADA_0022_PUBLICADOR_PRODUCCION_INTEGRADO=NO_VERIFICADO
RETIRADA_0022_BLOQUEO_QBIT_Y_STREAMS=NO
RETIRADA_0022_AUTORIZA_ELIMINACION=NO
RETIRADA_0022_ARCHIVOS_ELIMINADOS=0
RETIRADA_0022_TORRENTS_MODIFICADOS=0
```

## Ensayos aislados y validaciones

- `scripts/viewtv_windows_media_lock_sandbox_0022.ps1`: crea un GUID en TEMP para la identidad del test. Un subproceso PowerShell toma el mutex de sandbox y el padre comprueba que no puede adquirirlo. Se rechaza usar el GUID con propósito de producción. Después se **interrumpe solo el proceso de sandbox creado por el mismo ensayo**, se comprueba que el mutex se puede adquirir de nuevo y se elimina únicamente la carpeta de ensayo. Cero archivos de medios, base de datos, Jellyfin o qBit alterados.
- `scripts/viewtv_windows_publicador_lock_mock_sandbox_0022.ps1`: carga el publicador con `-Mode Library` y **sustituye las funciones de política y broker** por mocks. Prueba que `Process-One` toma el guard y devuelve `sin_trabajos`; al lanzar un error de autoridad sintético, impide publicar y libera el guard. No se invoca `docker.exe` ni se reclama trabajo real.
- `backend/tests/test_retirada_mutex_0022.py`: **15 pruebas** de contrato para impedir una regresión accidental: mismo nombre productivo, adquisición no bloqueante, fracaso ante guard ausente o abandono, liberación en finally, prohibición de convertir la auditoría en ejecutor destructivo y delimitación de procesos de sandbox.
- El publicador ejecutado en **solo `Preflight`** respondió `PREFLIGHT_PUBLICADOR_WINDOWS_0013_OK`.
- Smoke HTTP de solo lectura: **10/10 PASS**, API y frontend saludables.
- Suite backend **1221/1221 PASS** en contenedor de pruebas sin red, con 2 advertencias de deprecación de dependencias externas. Ruff **PASS**. Auditoría Windows posterior: **2/2 diarios NTFS verificados, 0 bloqueados, 1 carpeta sin diario conservada y 0 eliminaciones reales**. Preflight real SQLite/Jellyfin/qBit: **4/4 películas bloqueadas**, 2 torrents activos o incompletos para la política, 0 borrados; publicador read-only status `listo`. API y frontend 0017 **healthy**.

Resultados de sandbox Windows:

```text
PUBLICADOR_Y_RETIRADOR_FICTICIOS_EXCLUIDOS=PASS
NOMBRE_MUTEX_PRODUCTIVO_NO_MODIFICABLE=PASS
SALIDA_ABRUPTA_HIJO_MUTEX_RECUPERABLE=PASS
PUBLICADOR_BAJO_MUTEX_SOLO_CON_MOCKS=PASS
ERROR_DE_AUTORIDAD_NO_PERMITE_PUBLICACION=PASS
PUBLICACION_REAL_Y_CLAIMS=0
ARCHIVOS_REALES_MODIFICADOS=0
TORRENTS_REALES_MODIFICADOS=0
```

## Respaldo previo verificado

`/home/viewtv/viewtv-backups/lock-compartido-0022-pre-20261127-163228.tar.gz` SHA-256:
`7ea22dfa26ab4619c3b6290d0e57b95cdeb9a8d5a83016759b37078aff4ef7b1`.
Se verificó con `sha256sum` y `tar -tzf`. Contiene únicamente código y documentación anteriores; no contiene secretos, bases de datos, archivos de vídeo ni torrents.

No se realizaron migraciones, builds de nuevas imágenes ni reinicios de contenedores. No hay cambios productivos que revertir; el commit puede revertirse en el worktree conservando las versiones activas.

## Próximos controles imprescindibles, en orden

1. Revisar el proceso Windows actual, respaldarlo y **planificar una sustitución segura y supervisada del publicador**; mientras la instancia vieja permanezca activa no se puede afirmar exclusión real. No detenerlo ni sustituirlo de forma silenciosa.
2. Hacer que el futuro ejecutor de retirada adopte el mismo mutex **más** la autenticación, el journal y la autorización 0019, sin dar al mutex autoridad de borrar por sí solo.
3. Congelar o reservar de manera efectiva las reproducciones Jellyfin, incluyendo arranques tardíos; `GET /Sessions` del hito 0021 no ofrece esa garantía.
4. Añadir exclusión transaccional respecto a qBittorrent, que no obedece el mutex de Windows, y proteger los **4 metadatos extras** de los 2 torrents ViewTV actualmente activos.
5. Mantener la protección de todas las rutas y hardlinks, incluido el directorio sin diario, con pruebas de crash, revocación y consumo único de firma administrativa por película.
6. Medir bytes realmente liberados por volumen sin confundirlos con tamaño lógico de películas. Activar borrados reales **solo después** de todos los controles y de autorización específica para cada película.

**La app Samsung Tizen y VIEWTV Momentos siguen pendientes** hasta finalizar la eliminación y gestión física segura.
