# VIEWTV 0013 — Primera instancia de tubería con Win32 (solo sandbox)

**Fecha:** 20-11-2026. **Prototipo de desarrollo. Sin despliegue ni servicios Windows.**

## Hallazgo y solución limitada

El constructor público `NamedPipeServerStream` de PowerShell 5.1 / .NET
Framework rechaza la opción `FILE_FLAG_FIRST_PIPE_INSTANCE` si se pasa
como `PipeOptions` (ensayo anterior, reproducible). Sin esa opción,
un proceso que cree la tubería antes que el broker puede reservar el
nombre y ofrecer su propia instancia. Aunque el cliente comprueba la
firma HMAC de los acuses, conviene que el broker **no arranque** si
el nombre ya está en uso.

El módulo nuevo
`scripts/viewtv_windows_pipe_first_instance_sandbox.ps1` implementa
la creación de **solo tuberías GUID de prueba**
`viewtv-test-pipe-<32 hex>` mediante P/Invoke
`CreateNamedPipeW`, con:

- `PIPE_ACCESS_DUPLEX`, `FILE_FLAG_OVERLAPPED` y
  **`FILE_FLAG_FIRST_PIPE_INSTANCE`**.
- Descriptor de seguridad binario procedente de `PipeSecurity`
  con **DACL protegida sin herencia**, y `SECURITY_ATTRIBUTES`
  con `bInheritHandle=0`.
- Una instancia permitida; búferes de 4096 bytes. El resultado es
  un `SafePipeHandle` de Win32 envuelto por el constructor público
  `NamedPipeServerStream(PipeDirection, isAsync, isConnected, SafePipeHandle)`.
  Se pasa expresamente **`isConnected=false`**: declarar verdadero
  antes de aceptar al cliente provocó una regresión de conexión, detectada
  y corregida durante el ensayo.
- Liberación segura del descriptor de ACL en memoria no administrada
  y del identificador nativo si falla la construcción de .NET.
  El objeto `NamedPipeServerStream` dispone del identificador cuando
  la construcción funciona.

El servidor de
`scripts/viewtv_windows_pipe_broker_sandbox.ps1` usa ahora ese
constructor nativo en lugar de crear la tubería sin el indicador.
La ACL efectiva vuelve a comprobarse **después de abrir el pipe**,
como ya hacía el código anterior. La autenticación por HMAC de
solicitudes/respuestas, reservas de nonce y los límites de tiempo
del bloque anterior siguen vigentes.

Si otro proceso ya posee el nombre, `CreateNamedPipeW` falla:
el broker no entra en espera de conexión ni registra un nonce.
**No se elimina ni desconecta ninguna instancia ajena.**

## Evidencia reproducible

`scripts/test_viewtv_windows_pipe_first_instance_sandbox.ps1`
comprueba cinco casos: primera instancia con DACL protegida, segunda
primera instancia rechazada, conexión local válida al pipe nativo,
nombre previamente ocupado por un pipe .NET rechazado y recreación
válida después de liberar el nombre.

`scripts/test_viewtv_windows_pipe_broker_sandbox.ps1` añade una sexta
comprobación de **integración**: otro proceso simulado ocupa el nombre,
el servidor completo rechaza arrancar y **no se crea ningún nonce**.
La batería original del canal añade 23 comprobaciones de firma,
replay y concurrencia, que se conservan.

Las pruebas `scripts/test_viewtv_windows_pipe_timeouts_sandbox.ps1`
demuestran que el servidor nativo todavía termina con los ocho
escenarios de conexiones inactivas o parciales, sin reserva ni
publicación. Las regresiones ajenas al canal (publicación Windows,
diario, puente WSL y backend) se mantienen sin modificar.

### Comandos (PowerShell Windows nativo)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_pipe_first_instance_sandbox.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_pipe_broker_sandbox.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_pipe_timeouts_sandbox.ps1"
```

### Backend y revisión Git (WSL Ubuntu)

```bash
cd /home/viewtv/projects/viewtv-broker-0013-20261119
PYTHONPATH=backend:. /home/viewtv/projects/viewtv/backend/.venv/bin/python -m pytest -q backend/tests
git diff --check
```

## Advertencias y tareas abiertas

**La protección de primera instancia está probada SOLO con nombres de
pipe aleatorios y procesos bajo el mismo SID de prueba.** No valida
aislamiento frente a otras cuentas ni garantiza disponibilidad ante un
actor capaz de crear continuamente tuberías para ocupar nombres. Tampoco
prueba que el servicio instalado tenga el SID esperado. La identidad
Windows del cliente y del broker sigue compartida, al igual que la
clave HMAC de ensayo; alguien con acceso al mismo secreto aún podría
fabricar acuses.

Falta el broker bajo una identidad Windows **independiente y de
mínimo privilegio**, ACL y clave inaccesibles a Docker/usuario web,
restricciones reales del cliente, autenticación del lease 0013 y
qBittorrent consultado en vivo, sellado efectivo de staging frente
a TOCTOU, recuperación ante caída/crash y pruebas con archivos grandes.
No se han creado cuentas ni servicios o tareas persistentes ni se ha
alterado `C:\VIEWTV\media`, qBittorrent, Jellyfin, SQLite de
producción, Docker Compose o `worker/main.py`.
`VIEWTV_ENABLE_DOWNLOAD_START=false` permanece; producción sigue
0012. El PR #2 sigue en borrador, sin fusionar.

## Resultados finales de integración — 20-11-2026

- **5 comprobaciones nativas** de primera instancia y ACL: correctas.
- **24 comprobaciones del canal HMAC**: correctas, incluida la prueba
  integrada en la que **otro proceso PowerShell**, arrancado con
  `Start-Job`, conserva el nombre y el broker completo se niega a
  arrancar sin registrar nonce.
- **8 pruebas de conexiones incompletas y timeouts**: correctas.
- **20 pruebas del publicador Windows**, **11 del diario** y **12 del
  puente Windows→WSL**: correctas y sin modificaciones a esos flujos.
- **545 pruebas del backend**: aprobadas, dos advertencias de
  deprecación conocidas.
- `git diff --check`: sin errores; los directorios de ensayos y
  claves temporales son eliminados por sus scripts de prueba.

**Precisión:** las comprobaciones de primera instancia evitan que este
broker de ensayo arranque como otra instancia de un nombre preexistente.
No demuestran identidad de servicio ni disponibilidad frente a
saturación del espacio de nombres. El proceso que ocupa primero el
nombre no se modifica, fuerza ni termina. El journal de ensayo no
está conectado a publicaciones reales.
