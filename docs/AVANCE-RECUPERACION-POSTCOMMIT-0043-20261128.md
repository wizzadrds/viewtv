# VIEWTV 0043 — recuperación tras muerte del proceso después de ambos unlink NTFS

**Fecha:** 28/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`; PR #2 OPEN/DRAFT, sin fusionar. **Ámbito:** Windows NTFS, solamente ficheros binarios ficticios recién creados en un directorio TEMP con GUID y marca de propiedad. No existe modo de borrar películas reales, cambiar ACL, detener torrents ni intervenir servicios.

## Caso que faltaba tras 0042

El 0042 ya había matado de verdad procesos Windows inmediatamente después del primer `File.Delete` y después del primer `SetFileInformationByHandle(FileDispositionInfoEx)`. En ambos casos sobrevivía exactamente un hardlink al File ID original, lo que permitía recuperar el otro enlace conservando identidad y SHA256. Quedaba sin probar el caso opuesto: **ambos nombres eliminados por dos llamadas nativas, pero el proceso muere antes del diario FINALIZADO**. Después del segundo unlink ya puede no existir ningún nombre por el que reabrir ese File ID: **no sería seguro intentar reconstruirlo ni repetir el par de borrados**.

## Implementación y protección

Se amplió **solo el sandbox** `scripts/viewtv_windows_crash_recovery_sandbox_0042.ps1`, sin modificar servicios o rutas productivas, con tres nuevos modos:

- `TestAfterBoth`: genera su propio GUID aleatorio y ejecuta los mismos tres cortes/recuperaciones previos de 0042 sobre dos hardlinks ficticios. Tras verificar que un lector preabierto impide el commit, lanza un nuevo hijo y valida que el journal `COMMIT_PREPARADO` exista y **ambos nombres hayan desaparecido**, pero `FINALIZADO` aún no exista.
- `KillBoth`: bajo **dos handles separados** `DELETE|FILE_READ_ATTRIBUTES` del mismo File ID, exactamente dos enlaces y ninguna reparse point, persiste `COMMIT_PREPARADO` con `WriteThrough` y `Flush(true)`, realiza los **dos** `SetFileInformationByHandle(FileDispositionInfoEx, DELETE|POSIX_SEMANTICS)` y llama `TerminateProcess(GetCurrentProcess(), 79)` **sin cerrar los handles ni escribir FINALIZADO**.
- `ReconcileBoth`: reabre en otro proceso las seis fases esperadas y verifica el GUID, fase, File ID, tamaño y SHA256 registrados. Si alguno de los dos nombres existe, o ha aparecido un tercero conocido, **rechaza la operación sin tocarlo**. Solo si ambos nombres están ausentes registra `FINALIZADO`; al ejecutarse por segunda vez valida el mismo diario y sale sin unlink.

La prueba incorpora una carrera negativa concreta: después de la muerte, coloca **un nuevo archivo ficticio controlado por el ensayo** en el nombre que quedó libre. `ReconcileBoth` debe fallar y conservar íntegramente ese archivo; solo el proceso padre, tras verificar su marca de propiedad, limpia esa propia intrusión de prueba y reintenta. En todo el flujo el número de nombres permitidos queda restringido por `Assert-Sandbox`, junto con comprobaciones de GUID, TEMP y rechazo de reparse points.

`scripts/test_viewtv_windows_postcommit_recovery_0043.ps1` es un verificador sin argumentos que ejecuta `TestAfterBoth` **dos veces en distintos procesos Windows y sandboxes GUID**, con timeout y comparación exacta de trece indicadores. Se mantiene `scripts/test_viewtv_windows_crash_recovery_0042.ps1` para garantizar que el modo original también sigue pasando y conserva su salida.

## Resultados en Windows

La ejecución directa de `TestAfterBoth` terminó con:

- `KILL_REAL_POST_PRIMER_UNLINK=PASS`
- `TERCER_HARDLINK_BLOQUEA_RECUPERACION=PASS`
- `RECUPERACION_IDEMPOTENTE_FILE_ID=PASS`
- `KILL_REAL_DURANTE_UNLINK_NATIVO=PASS`
- `RECUPERACION_NATIVA_RESTAURA_FILE_ID=PASS`
- `LECTOR_PREABIERTO_BLOQUEA_COMMIT=PASS`
- `KILL_REAL_POST_SEGUNDO_UNLINK_NATIVE=PASS`
- `NOMBRE_REOCUPADO_BLOQUEA_RECONCILIACION=PASS`
- `RECONCILIACION_DOS_UNLINKS_SIN_REPETIR_BORRADO=PASS`
- `SANDBOX_GUID_LIMPIADO=SI`; `EJECUTOR_PRODUCCION_INSTALADO=NO`; `BORRADOS_REALES=0`; `TORRENTS_REALES_MODIFICADOS=0`.

**Resultados confirmados:** runner 0043 **2/2 ejecuciones PASS**; runner original 0042 **2/2 ejecuciones PASS**, conservando los once indicadores exactos de su contrato. Todos los ensayos terminaron con directorio TEMP GUID limpio, cero medios reales borrados y cero cambios de torrents. **Ruff global** `backend worker scripts` PASS, **TypeScript PASS**, **ESLint PASS**, smoke HTTP real solo lectura **10/10 PASS**. **Preflight real 0018:** 4/4 películas bloqueadas y 2/2 diarios NTFS verificados, permiso de borrado NO; **custodia qBit 0026:** 2/2 torrents fuera de reposo seguro, dos archivos publicados y cuatro extras protegidos (488 bytes lógicos). **Regresión completa backend 1753/1753 PASS** en Docker sin red con fuentes montadas solo lectura, con **2 advertencias externas de Starlette/FastAPI**. La suite kernel NTFS 0034 de dos casos sigue PASS. Comprobación posterior de Windows TEMP: **0 directorios residuales del ensayo 0042/0043**.

## Límites importantes

Este flujo reconcilia **la presencia de dos rutas de un laboratorio**, no garantiza que los bloques físicos del disco se hayan liberado. Si existen otros hardlinks no enumerados, snapshots, sistemas de copias, handles y demás referencias, la ausencia de ambos nombres conocidos no demuestra recuperación de espacio. El control que impide crear terceros enlaces **debe ser una DACL kernel aplicada al File ID por un broker de SID distinto**, no el mero diario. Además, `TerminateProcess` NO equivale a un corte de corriente, ni demuestra orden durable de metadatos de NTFS frente a pérdida total de energía. No se ha probado corrupción de disco ni recuperación bajo servicio productivo.

Continúan las seis barreras detectadas por el interlock 0041: custodia exclusiva de qBit frente a GUI/WebUI, segregación Windows/NTFS y eliminación de terceros hardlinks, drenaje efectivo Jellyfin/HLS v2, aprobación administrativa específica consumida una sola vez, ejecutor de producción con journal privado y pruebas bajo apagado/reinicio, y comprobación física de espacio. Además, las películas reales del preflight 0018 están bloqueadas por perfiles, solicitudes, torrents y admin, y deben permanecer intactas.

**Estado:** se demuestra el protocolo de conciliación postsegundo-unlink en un sandbox NTFS. **No existe ejecutor real instalado ni permiso de retirar medios reales.** El paso a producción necesitará una ventana de mantenimiento y autorización expresa separada, sin afectar torrents ajenos, cuatro archivos auxiliares protegidos, cachés o perfiles.
