# VIEWTV 0013 — Límites de espera en el canal de broker Windows (sandbox)

**20-11-2026 · Solo pruebas; no es un servicio ni un broker de publicación.**

**Actualización posterior:** se ha integrado una apertura Win32 con
`FILE_FLAG_FIRST_PIPE_INSTANCE` en el servidor de pruebas, tras validar que
el constructor .NET lo rechazaba. Véase
[PRIMERA-INSTANCIA-PIPE-WIN32-SANDBOX.md](ORGANIZADOR-PRIMERA-INSTANCIA-PIPE-WIN32-SANDBOX.md).
Las limitaciones indicadas más abajo reflejan el estado **anterior**
a esa integración; continúa pendiente separar las identidades Windows.

## Problema

En el prototipo de tubería anterior, `WaitForConnection()` y
`BinaryReader.ReadBytes/ReadInt32()` eran bloqueantes sin fecha límite.
Una conexión ausente, o un cliente que entregaba solo parte del desafío,
cabecera o cuerpo, podía retener un proceso de admisión de prueba
indefinidamente. Tampoco se limitaba el tiempo de espera del cliente
cuando el servidor aceptaba pero no respondía.

## Implementación en sandbox

- Nuevo `scripts/viewtv_windows_pipe_io_sandbox.ps1`: lectura exacta de
  bytes mediante `ReadAsync` sobre un `PipeStream` asíncrono, y
  `Stopwatch` con fecha límite. No reinicia el tiempo en cada fragmento
  de un mismo cuerpo. Rechaza EOF prematuro, tamaños fuera de rango y
  agotamiento del tiempo. La cabecera de cuatro bytes y el cuerpo
  comparten el plazo de un mensaje; el desafío inicial de 32 bytes
  tiene otro plazo, también acotado.
- El servidor de `viewtv_windows_pipe_broker_sandbox.ps1` usa
  `PipeOptions.Asynchronous` y `WaitForConnectionAsync` con máximo
  **5 segundos por defecto**. El desafío y el mensaje de solicitud usan
  un tiempo de lectura de **4 segundos por defecto** cada uno. Ambos
  límites se pueden ajustar **solo en el ensayo** dentro de 250–15000 ms
  y se rechazan valores fuera de ese intervalo. Ante una espera fallida
  cierra la conexión sin registrar ningún nonce ni publicar.
- El cliente del ensayo abre la tubería con `PipeOptions.Asynchronous`,
  limita el tiempo de recepción de cabecera y respuesta, y no interpreta
  desconexiones/ausencias como éxito firmado.
- Se conservan los máximos de **8192 bytes por petición** y
  **2048 bytes por respuesta**: un encabezado que anuncia una longitud
  inválida no permite reservas ni lecturas de memoria arbitrarias.
- El HMAC firmado por desafío, el diario de nonce con
  `FileMode.CreateNew`, las ACL protegidas, las reglas de identificación
  del trabajo y los resultados anteriores **no se modifican**.
- No existe una nueva ruta hacia `Directory.Move`, SQLite real, Docker
  ni descargas; el sistema sigue sin publicar nada desde el canal.

## Evidencia del equipo

`scripts/test_viewtv_windows_pipe_timeouts_sandbox.ps1` crea una carpeta
de diario aleatoria marcada bajo `%TEMP%`, con DACL restringida,
una clave temporal independiente y procesos PowerShell nativos efímeros.
Ejercita **ocho escenarios**:

1. Broker iniciado sin cliente: termina por límite de espera.
2. Cliente conectado pero sin enviar bytes: termina por límite.
3. Cliente envía tres bytes de los 32 del desafío.
4. Cliente envía solo el desafío de 32 bytes.
5. Cliente envía el desafío y dos de los cuatro bytes de longitud.
6. Cliente anuncia un cuerpo de 200 bytes y solo entrega tres.
7. Valores de timeout de servidor inválidos: rechazo antes de escuchar.
8. Servidor ficticio que acepta y no responde: el cliente abandona la
   espera sin aceptar un acuse inventado.

Los seis primeros escenarios **no registran nonce**. Los recursos de
prueba se retiran solo si coinciden el GUID, raíz y marcador exactos.

El test existente
`scripts/test_viewtv_windows_pipe_broker_sandbox.ps1` sigue probando
**23 comprobaciones**, incluida autenticación de respuesta y protección
de reuso durable con dos servidores concurrentes.

### Primera instancia de pipe: bloqueo documentado

`scripts/probe_viewtv_pipe_first_instance_sandbox.ps1` prueba en un
nombre de tubería GUID el indicador nativo
`FILE_FLAG_FIRST_PIPE_INSTANCE` (0x80000) a través de
`NamedPipeServerStream` de PowerShell 5.1 / .NET Framework.

**Resultado medido: el constructor .NET rechaza el valor de
`PipeOptions` no reconocido.** No se integró el indicador ni se afirma
que el servidor sea la primera instancia. Una implementación definitiva
necesitaría una apertura nativa Win32 `CreateNamedPipeW` validada, una
DACL propia del servicio y verificación explícita de la identidad del
proceso servidor. **No crear cuentas o servicios Windows en este paso.**

### Reproducción (PowerShell nativo de Windows)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_pipe_timeouts_sandbox.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_pipe_broker_sandbox.ps1"
```

### Reproducción backend (WSL Ubuntu)

```bash
cd /home/viewtv/projects/viewtv-broker-0013-20261119
PYTHONPATH=backend:. /home/viewtv/projects/viewtv/backend/.venv/bin/python -m pytest -q backend/tests
git diff --check
```

## Pendientes y límites de seguridad

**Los timeouts no demuestran inmunidad frente a denegación de servicio.**
Faltan cuotas por identidad, límite de procesos simultáneos, supervisión,
cancelación de escritura cuando el cliente deja de leer y pruebas de
llegada progresiva de fragmentos. El servidor solo gestiona una conexión
por instancia; un atacante podría seguir provocando ocupaciones repetidas
dentro de esos límites.

**La autenticación del proceso servidor sigue incompleta**: el cliente
y el servidor de pruebas comparten SID Windows y clave HMAC. Falta probar
denegación efectiva entre cuentas, impedir creación de tubería por
otros procesos, y separar físicamente claves y permisos de staging.

No se ha conectado la autoridad de leases 0013 al canal, tampoco se ha
cerrado TOCTOU, ni se ha ensayado la migración 0012→0013 sobre un respaldo
fresco. Sin despliegue, ficheros multimedia reales, cambios de Docker,
qBittorrent, Jellyfin o `worker/main.py`. `VIEWTV_ENABLE_DOWNLOAD_START=false`
sigue siendo condición operativa. PR #2 debe permanecer en borrador.

## Resultados finales del bloque

- **8 escenarios nuevos de timeout** aprobados: 6 clientes incompletos,
  rechazo de timeout inválido y servidor que no devuelve respuesta.
- **23 escenarios del canal autenticado anterior** correctos, incluida
  concurrencia y replay entre servidores.
- **20 escenarios del publicador Windows**, **11 del diario** y
  **12 del puente de lease Windows→WSL** correctos.
- **545 tests backend aprobados**, con las dos advertencias de
  deprecación preexistentes.
- `git diff --check` sin errores. Inspección posterior:
  **cero** directorios de prueba GUID, diarios y claves efímeras
  en las raíces `%TEMP%`, `C:\Users\Public` y `/tmp`.
- La prueba `FILE_FLAG_FIRST_PIPE_INSTANCE` devolvió
  `FIRST_INSTANCE_FLAG_NOT_SUPPORTED_BY_DOTNET`; **no hay protección
  de primera instancia implementada ni validada en este bloque**.
