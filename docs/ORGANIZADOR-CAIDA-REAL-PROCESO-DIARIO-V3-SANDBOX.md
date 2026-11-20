# VIEWTV 0013 — fallo real de proceso tras reservar la descarga v3

Fecha: 20-11-2026. Rama: `viewtv-seguimiento-descargas-0012`.
**Únicamente laboratorio:** proceso `Start-Job` Windows, SQLite
sintética de Ubuntu, servidor HTTP qBittorrent ficticio y diario
temporal marcado. No es un servicio de producción ni prueba de
supervivencia ante corte eléctrico.

## Motivo del experimento

El broker ya tenía un journal `viewtv-pipe-broker-<GUID>`
con dos registros por solicitud: primero una reserva durable de
`download_id`, después el registro de nonce. La auditoría v3
rechaza un diario en estado incompleto. Hasta ahora se había
**inyectado un archivo parcial desde el test**, pero no se había
terminado realmente el proceso broker después de la primera
escritura con `Flush(true)`.

Este hito introduce una **inyección optativa y limitada al servidor
de ensayo**: `-TestCrashAfterDownloadClaim`. Solamente es válido
con `-Mode Server -RequireSandboxLease -RequireSandboxTorrent`,
una SQLite ficticia y un origen HTTP de loopback marcado. Los
clientes y servidores v1/v2 no pueden activar ese indicador.

Después de aceptar una solicitud firmada, consultar el lease y
el HTTP sintético y escribir el primer registro con
`FileMode.CreateNew`, `FileOptions.WriteThrough` y `Flush(true)`,
el broker de laboratorio llama a `[Environment]::Exit(73)`.

**Importante:** el proceso que termina es exclusivamente un
**proceso hijo `Start-Job` creado por el test**, no el conector,
el PowerShell principal, Docker ni ningún servicio Windows real.
El flag es una herramienta de fallo destructivo **solo de prueba**,
que no debe habilitarse en una ejecución normal.

## Secuencia ensayada

1. El test crea un diario GUID restringido, una clave temporal,
   un lease SQLite de ensayo y un HTTP de torrent falso en WSL.
2. Inicia un broker Windows aislado en `Start-Job` con el flag
   de caída y le envía una petición v3 HMAC válida.
3. El broker guarda la reserva de descarga, con su `claim_hmac`,
   y termina abruptamente **antes** de escribir el nonce o
   enviar un acuse HMAC.
4. El cliente detecta la conexión interrumpida: **no recibe
   confirmación firmada ni puede asumir publicación**.
5. El test inspecciona el journal: existe exactamente el registro
   de descarga esperado, con identidad y MAC, y no existe el
   nonce de esa petición.
6. Un **nuevo proceso broker** recibe otra solicitud v3 válida,
   con el mismo `JournalRoot`. Su auditoría de todo el diario
   devuelve `requiere_revision`; no admite, repara ni elimina
   automáticamente la reserva huérfana.
7. El test comprueba que el contenido de la primera reserva no
   cambió. Para continuar su batería, **solo el propio test**
   elimina después esa corrupción que generó, dentro del diario
   temporal verificado, y sigue con las admisiones válidas.

Además, el test rechaza el uso del indicador de caída desde
`-Mode Client` o un `-Mode Server` histórico sin ambos gates,
para que la inyección no pueda viajar en una petición firmada.

## Código afectado

Se modificaron **dos archivos ya existentes**:

- `scripts/viewtv_windows_pipe_broker_sandbox.ps1`:
  nuevo interruptor de fallo, validación estricta del modo y
  terminación justo después del primer registro durable.
- `scripts/test_viewtv_windows_pipe_dual_gate_sandbox.ps1`:
  proceso hijo aislado, comprobación de ausencia de acuse,
  verificación de la reserva huérfana y reinicio con
  el mismo diario. También prueba dos rechazos de configuración.

No se han modificado la lógica de publicación real, la SQLite,
las migraciones ni imágenes Docker, ni se ha creado un servicio.

## Alcance, límites y criterio de seguridad

- **El punto de caída es determinista y después de `Flush(true)`.**
  No se ha simulado interrupción durante los bytes del primer
  registro, archivo corrupto por disco, pérdida de energía o
  fallo de hardware. Los test de registros incompletos existentes
  cubren otros estados por inyección sintética, no esos fallos reales.
- El modo se limita al diario GUID y no constituye una autoridad
  global entre diarios distintos, hosts o reinstalaciones.
- Una interrupción tras la reserva de descarga provoca una
  **indisponibilidad conservadora** de todo ese diario hasta
  revisión; no existe reconciliación automática aprobada.
- No resuelve transacciones NTFS/SQLite, congelación del torrent
  ni la carrera entre GET, lease y renames.
- El HMAC sigue siendo una clave efímera de ensayo compartida;
  aún falta broker Windows bajo SID separado y autoridad real.
- `viewtv-api-1` sigue siendo una incidencia independiente,
  pendiente de reparación autorizada.
- El PR #2 sigue abierto en borrador; prohibido fusionar o
  desplegar este prototipo en producción.

## Evidencias y respaldo

Prueba principal:
`scripts/test_viewtv_windows_pipe_dual_gate_sandbox.ps1`.

La batería ampliada del canal v3 pasó **29 comprobaciones**, código
0 (54,69 s). Se ejecutó PowerShell 5.1 con parser correcto.
Regresiones: publicador estricto **17 correctas** (20,78 s),
pipe v1 **30 correctas** (27,75 s), pipe v2 **9 correctas**
(18,66 s), entrega privada NTFS **14 correctas**, seguridad
ACL **29 correctas** y publicador histórico **20 correctas**.
El backend completo en Ubuntu pasó **615 pruebas**,
2 avisos de deprecación conocidos, exit code 0 (47,50 s),
sin caché ni bytecode.

La comprobación final de limpieza confirmó **cero** diarios de pipe,
claves temporales, cuentas Windows efímeras, carpetas sandbox
GUID en `C:\Users\Public` y fixtures SQLite/HTTP de `/tmp`.
La API real seguía reiniciándose con `viewtv:local` (solo lectura).

Antes de modificar ambos archivos se creó y verificó el respaldo:
`/home/viewtv/viewtv-backups/crash-proceso-v3-pre-20261120-173039.tar.gz`

SHA-256:
`597fa2be9848ef074fd12405e7baf3f7ec413adc18560202efb554b88339a582`

`tar -tzf` verificó exactamente:
- `scripts/viewtv_windows_pipe_broker_sandbox.ps1`
- `scripts/test_viewtv_windows_pipe_dual_gate_sandbox.ps1`
- `docs/ORGANIZADOR-AUDITORIA-DIARIO-V3-RECUPERACION-SANDBOX.md`

Este documento es nuevo, sin versión anterior.

**Decisión:** interrupción real de proceso y bloqueo tras reinicio
**demostrados solamente en el sandbox**. Fase 1 permanece abierta.
