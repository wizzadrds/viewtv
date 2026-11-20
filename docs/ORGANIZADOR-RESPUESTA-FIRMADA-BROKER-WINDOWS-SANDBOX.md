# VIEWTV 0013 — Acuse de broker Windows firmado por conexión (sandbox)

**Fecha:** 20 de noviembre de 2026. **Solo desarrollo. Sin despliegue, servicio, cuentas nuevas ni publicaciones NTFS.**

**Avance posterior (mismo día):** el canal de sandbox tiene plazos
acotados de conexión y de lectura, y pruebas contra clientes parciales
o inactivos. Consultar
[ORGANIZADOR-TIMEOUTS-PIPE-WINDOWS-SANDBOX.md](ORGANIZADOR-TIMEOUTS-PIPE-WINDOWS-SANDBOX.md).
**La primera instancia de tubería sigue sin estar garantizada.**

## Riesgo que se aborda

En el prototipo de tubería anterior, el servidor verificaba el HMAC del cliente, pero
el cliente aceptaba cualquier respuesta JSON recibida en la tubería esperada.
Un proceso capaz de suplantar una tubería con el nombre previsto podía
responder «intención registrada» sin conocer el secreto de ensayo.
Además, una respuesta firmada sin desafío podría copiarse de otra conexión.

La prueba añade **autenticidad del acuse** y vinculación a la sesión.
No demuestra todavía autenticación **de la identidad Windows del servicio**
ni separación de privilegios.

## Protocolo de ensayo v1

- `scripts/viewtv_windows_pipe_response_sandbox.ps1`: funciones puras de
  desafío, firma y comprobación de respuestas de sandbox.
- El **cliente** crea 32 bytes aleatorios con
  `RandomNumberGenerator` y los envía al comenzar la conexión,
  antes de la longitud `Int32` y el cuerpo JSON UTF-8.
- El servidor mantiene la comprobación HMAC anterior sobre la **petición**,
  valida datos y reserva el nonce durable. Su respuesta ahora es
  `{payload,signature}`, donde el `payload` incluye versión,
  desafío (hexadecimal), SHA-256 de la petición recibida,
  estado y `publicacion_iniciada=false`.
- La firma de respuesta se calcula mediante **HMAC-SHA-256**
  sobre los bytes UTF-8 de
  `VIEWTV_PIPE_SIGNED_RESPONSE_V1\n` concatenados con el JSON
  `payload`, separando este uso de la clave del HMAC de las peticiones.
- El cliente verifica la firma con comparación de bytes sin
  salida anticipada dependiente de su contenido, el desafío exacto y
  el digest de la **solicitud que él mismo envió**, más una lista cerrada
  de estados y `publicacion_iniciada=false`. No confía en la respuesta
  si falla cualquier comprobación.
- Los mensajes de solicitud conservan el límite de **8 KiB**
  y las respuestas están limitadas a **2 KiB**, con prefijos de longitud.
  Para solicitudes excesivas, el servidor responde rechazo firmado
  con digest de cadena vacía: solo se permite este caso cuando la longitud
  ya obliga al rechazo, **nunca se autoriza publicar**.
- La respuesta aceptada mantiene por compatibilidad
  `estado` y `publicacion_iniciada=false`. No se conecta al
  publicador Windows ni cambia el comportamiento de SQLite.

## Evidencia automatizada

El archivo `scripts/test_viewtv_windows_pipe_broker_sandbox.ps1`
mantiene las 17 verificaciones del canal anterior y añade:

1. Acuse HMAC válido de servidor: verificado.
2. Estado del acuse manipulado después de firmarlo: rechazado.
3. Acuse firmado para otro desafío, como el de una sesión anterior: rechazado.
4. Acuse firmado para otro contenido de petición: rechazado.
5. Acuse firmado con una clave de ensayo distinta: rechazado.
6. **Proceso que suplanta una tubería y devuelve una respuesta de éxito
   sin firma**: el cliente la rechaza, aunque la tubería exista y se conecte.

Los ensayos usan únicamente procesos PowerShell transitorios, tuberías
GUID y claves efímeras bajo `%TEMP%`, con comprobación de limpieza.
No se crea, inicia ni altera ningún servicio Windows.

**PowerShell nativo Windows**:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_pipe_broker_sandbox.ps1"
```

**WSL Ubuntu**, regresión:

```bash
cd /home/viewtv/projects/viewtv-broker-0013-20261119
PYTHONPATH=backend:. /home/viewtv/projects/viewtv/backend/.venv/bin/python -m pytest -q backend/tests
git diff --check
```

## Límites obligatorios antes de producción

**No se ha conseguido separación de identidades:** el cliente y el
servidor de prueba todavía comparten el mismo SID y la misma clave temporal,
por lo que un atacante con acceso a esa identidad/clave puede firmar también
las respuestas. Este acuse demuestra posesión de la clave de ensayo,
no identidad independiente del proceso o servicio.

Faltan además:

- Un servicio Windows mínimo y aislado, bajo otro SID, con ACL que impidan
  a Docker/worker leer sus claves, suplantar su tubería, registrar sus
  nonces o modificar staging/destinos.
- Protección contra creación anticipada de la tubería, por ejemplo
  verificando la primera instancia real, identidad del proceso y canales
  de gestión del servicio. El test del servidor falso comprueba que no
  basta devolver JSON, **no impide que un servidor con la clave suplante**.
- Timeout y cancelación del servidor para clientes conectados que no
  envían todos los bytes, más límites de sesiones, sincronización y
  supervisión de caídas.
- Autoridad independiente de lease 0013, hash del torrent comprobado
  en vivo, manifiesto y destino vinculados a la intención durable,
  barrera TOCTOU bajo cuentas distintas y reconciliación de errores NTFS.
- Pruebas de archivos de varios GiB, bloqueo físico, caída brusca,
  migración reversible de SQLite 0012→0013 sobre copia reciente y
  despliegue expresamente autorizado.

**Producción VIEWTV sigue en 0012** con
`VIEWTV_ENABLE_DOWNLOAD_START=false`. No se ha accedido a
`C:\VIEWTV\media`, qBittorrent, Jellyfin ni a SQLite de producción.
El PR #2 permanece en borrador, sin fusionar.

## Resultados finales verificados en el equipo

- **23 escenarios** del canal local con acuse firmado, superados en dos
  ejecuciones completas independientes iniciadas en paralelo. Incluyen
  reserva exclusiva del mismo nonce en dos procesos servidores y rechazo
  de una respuesta falsificada por un servidor de prueba sin firma.
- **20 pruebas del publicador Windows**, **11 del diario** y
  **12 del puente Windows→WSL** correctas; sin cambios de comportamiento
  de los componentes anteriores.
- **545 pruebas del backend aprobadas**, con dos advertencias de
  deprecación conocidas, sin errores.
- `git diff --check` y comprobación de que los sandboxes temporales
  de Windows/WSL, las claves efímeras y diarios de pruebas no permanecen
  después de la ejecución.
- El test de servidor falso usa una tubería con DACL del ensayo, sin
  tocar cuentas Windows ni servicios. El único cambio funcional es en
  el protocolo de la tubería ficticia, no en el publicador real.

**Prueba no realizada:** no se ha atacado una clave compartida por dos
identidades Windows diferentes; tampoco se ha medido un cliente reteniendo
un canal abierto indefinidamente. Ambas situaciones siguen siendo
condiciones de no despliegue.
