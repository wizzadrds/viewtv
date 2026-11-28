# VIEWTV 0042 — interrupción real de proceso Windows y recuperación de dos hardlinks NTFS

**Fecha:** 28/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`. PR #2 abierta y en borrador; **sin fusión ni despliegue**. Objetivo: probar una retirada física **exclusivamente en ficheros ficticios de un directorio Windows TEMP con GUID**, recuperable tras matar el proceso a mitad de la operación. No se ha elegido ni retirado ninguna película real.

## Por qué se necesitaba esta fase

El 0020 demostró un diario write-through y reconciliación en procesos distintos, y el 0034 probó dos handles `DELETE` y dos unlinks nativos, pero la interrupción era simulada mediante el flujo del propio script. En 0042 se prueba que **un proceso Windows desaparece de verdad**, mientras otro proceso independiente utiliza el diario persistido para restablecer el mismo File ID. Se ensayan dos cortes diferentes: tras `File.Delete` del primer nombre y, adicionalmente, tras `SetFileInformationByHandle(FileDispositionInfoEx)` del primer hardlink con ambos handles DELETE todavía adquiridos.

## Implementación

`scripts/viewtv_windows_crash_recovery_sandbox_0042.ps1` tiene solamente los modos `Test`, `Crash`, `Recover`, `KillNative`, `RecoverNative` y `Finish`. **No tiene parámetro de ruta, descarga, película o torrent ni modo de producción.** Cada directorio se genera como `TEMP/viewtv-0042-ficticio-<guid>`; únicamente acepta identificadores hexadecimales de 32 caracteres en subprocesos. Comprueba que TEMP y directorio no son reparse points, su marca de propiedad y una lista estricta de nombres permitidos. Rechaza colisiones y entradas externas; no utiliza `Remove-Item -Recurse` ni rutas de medios. La entrada de prueba nunca reutiliza un GUID enviado desde fuera.

Cada fase crea un diario **write-once** con `FileMode.CreateNew`, `FileOptions.WriteThrough` y `Flush(true)`, con versión, GUID, fase, File ID NTFS (volumen/alto/bajo), tamaño exacto y huella SHA256 del contenido. La recuperación reabre y verifica identidad, número de enlaces (exactamente 1 o 2 según fase) y contenido, antes de crear un nuevo hardlink del superviviente. El mismo intento de recuperación puede repetirse sin multiplicar enlaces.

Dos procesos hijo independientes ejecutan `kernel32.TerminateProcess(GetCurrentProcess(), 77/78)` **después** de que la fase durable esté escrita y el primer enlace ficticio haya desaparecido. Un intento adversarial de recuperar con un tercer hardlink creado en el mismo sandbox se rechaza y no genera publicación nueva. Tras restaurar, se comprueba que un lector preabierto impide conseguir las dos reservas nativas `DELETE|FILE_READ_ATTRIBUTES`. Finalmente, dos handles separados para el mismo File ID se validan contra el diario y se usan para `SetFileInformationByHandle(FileDispositionInfoEx, DELETE|POSIX_SEMANTICS)`; se verifica que ambos nombres desaparezcan. Repetir `Finish` con el journal `FINALIZADO` no vuelve a borrar.

`scripts/test_viewtv_windows_crash_recovery_0042.ps1` es el verificador: invoca el ensayo completo **dos veces en procesos Windows distintos y GUID distintos**, comprueba exactamente once indicadores y rechaza cualquier salida inesperada, código no cero o timeout. Nunca divulga rutas, hashes, títulos ni nombres de perfiles. En los casos correctos constata la limpieza del sandbox, cero borrados productivos y cero cambios de torrents.

## Evidencia Windows real (archivos ficticios)

La ejecución directa del ensayo devolvió los siguientes indicadores:

- `KILL_REAL_POST_PRIMER_UNLINK=PASS`: el hijo murió tras retirar el primer nombre ficticio.
- `TERCER_HARDLINK_BLOQUEA_RECUPERACION=PASS`: no se aceptó restauración con enlace adicional.
- `RECUPERACION_IDEMPOTENTE_FILE_ID=PASS`: repetición de recuperación conservó File ID y contenido.
- `KILL_REAL_DURANTE_UNLINK_NATIVO=PASS`: segundo hijo murió tras el primer unlink Win32 bajo dos handles.
- `RECUPERACION_NATIVA_RESTAURA_FILE_ID=PASS`: otro proceso reconstruyó el enlace con identidad original.
- `LECTOR_PREABIERTO_BLOQUEA_COMMIT=PASS`.
- `DOS_UNLINKS_NATIVOS_Y_REPETICION=PASS`.
- `SANDBOX_GUID_LIMPIADO=SI`, `EJECUTOR_PRODUCCION_INSTALADO=NO`, `BORRADOS_REALES=0`, `TORRENTS_REALES_MODIFICADOS=0`.

En el primer intento técnico, PowerShell convirtió el STDERR de un hijo **correctamente denegado** por tercer hardlink en error del proceso padre. Se corrigió utilizando un `System.Diagnostics.Process` hijo con salida silenciada, timeout y código de salida inspeccionado. **Un sandbox ficticio de esa ejecución fallida se limpió por separado** tras comprobar nombre GUID, marca de propiedad, ausencia de reparse points y lista estricta de archivos permitidos; constó `SANDBOX_PROPIO_0042_CLEANED=1` y cero operaciones reales. El ensayo corregido superó la primera ejecución íntegra.

## Calidad final

**Verificación real completada de Windows:** el runner 0042 ejecutó **2/2 ensayos PASS** (en cada uno hubo muerte de DOS procesos hijo y recuperación por procesos nuevos), sin discrepancias ni restos TEMP. Dos suites anteriores de NTFS 0034 siguen en PASS. **Ruff global** `backend worker scripts` PASS, **TypeScript PASS, ESLint PASS** y **smoke HTTP real read-only 10/10 PASS**.

**Preflight real posterior al crash-sandbox:** 4/4 películas BLOQUEADAS, 2/2 diarios NTFS verificados, aprobación administrativa ausente, perfiles sin completar; **cero archivos eliminados y cero torrents modificados**. Custodia qBit 0026: dos torrents no en reposo seguro, seis archivos consultados, dos publicados y **cuatro extras protegidos (488 bytes lógicos)**, sin alteraciones. **Regresión backend íntegra 1753/1753 PASS** en Docker sin red con fuentes montadas solo lectura (dos advertencias externas Starlette/FastAPI). El hito no modifica Python ni la API productiva.

## Qué NO demuestra y por qué no se habilita el borrado

**Importante:** `TerminateProcess` no equivale a desenchufar el equipo ni demuestra el orden de persistencia de todos los metadatos del volumen durante una caída eléctrica. Tampoco se cubre todavía un crash tras el **segundo** unlink nativo y antes del journal `FINALIZADO`, la recuperación ante corrupción simultánea de diarios, ni un servicio de broker reiniciado bajo cuenta de producción. El entorno ficticio opera con el usuario del ensayo, no con el SID separado y DACLs reales de 0037. Una DACL compartida entre todos los hardlinks sigue siendo imprescindible para prohibir a Jellyfin/qBit crear nuevas referencias o escribir. El diario de laboratorio no es el journal firmado/aprobado de producción.

Además faltan: quietud transaccional de qBit y cierre real de todas las GUI/WebUI de reinicio; aislamiento efectivo de puertos y reproductores Jellyfin, HLS v2 instalado y drenaje; autorización administrativa independiente, específica de película y consumida una vez; vínculo atómico exacto de descarga, torrent, File ID, perfiles y diario del publicador bajo el mismo lock; ejecución productiva con recuperación y medición de espacio libre real.

El preflight 0041 validó 8/8 informes de siete fuentes pero mantuvo **seis barreras pendientes y `ESTADO_RETIRADA_0041=BLOQUEADA`**. Las cuatro películas reales siguen sin ser elegibles; siguen intactos los metadatos auxiliares de qBittorrent. No hay autoridad para elegir una película ni para cambiar cuentas, ACL, firewall o servicios con esta prueba.

**Conclusión:** el mecanismo de dos unlinks Win32 y recuperación tras muerte **real de proceso** funciona en un laboratorio aislado. **El ejecutor productivo NO está instalado ni autorizado; eliminación física real = 0.** Samsung TV y Momentos permanecen pospuestos hasta cerrar el borrado seguro.
