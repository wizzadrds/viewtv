# VIEWTV 0013 — lease obligatorio en la admisión por pipe (solo sandbox)

Fecha: 20-11-2026. Rama: `viewtv-seguimiento-descargas-0012`.

**Estado:** ensayo Windows→Ubuntu con SQLite ficticia, sin publicación.
No instalar como servicio, ni usar bases de producción, ni modificar
qBittorrent, la biblioteca `C:\VIEWTV\media` o Docker.

## Brecha abordada

El broker de pipe validaba firma HMAC, campos, vencimiento, nonce y
reserva durable por `download_id`. Esto no demostraba que la descarga
y su intento aún pertenecieran al worker solicitante.

Se ha añadido una modalidad del servidor de **admisión condicionada al
lease** mediante dos nuevos archivos:

- `scripts/viewtv_windows_pipe_lease_auth_sandbox.ps1`: llama desde
  Windows a la consulta de solo lectura que ya existía en WSL:
  `worker.organization_lease_gate_cli_sandbox`.
- `scripts/test_viewtv_windows_pipe_lease_admission_sandbox.ps1`:
  prueba el pipe real con procesos PowerShell separados, una SQLite
  ficticia en `/tmp`, clave temporal y diario GUID restringido.

`scripts/viewtv_windows_pipe_broker_sandbox.ps1` ofrece únicamente en
`-Mode Server` dos argumentos nuevos:
`-RequireSandboxLease -LeaseDatabase <ruta-sandbox>`.

No se acepta `-LeaseDatabase` en el cliente. El servidor exige
`/tmp/viewtv-lease-gate-<GUID>/organization.sqlite3`, validada de
nuevo por Python contra el marcador y la naturaleza regular del
archivo. No se construyen cadenas de shell con texto del usuario:
los argumentos de `wsl.exe` se pasan separadamente.

## Contrato de la modalidad v2

El servidor sin gate conserva el protocolo v1 para pruebas históricas;
**rechaza un sobre de versión 2**. El servidor con gate exige una
intención HMAC de versión **2**, con todos los campos v1 más
`torrent_hash` (SHA-1 40 hex o SHA-256 64 hex, minúsculas).
Cualquier versión distinta, campo extra, tipo inválido o firma
incorrecta se rechaza sin reservar.

Cuando la firma y los campos son correctos, **antes** de
`FileMode.CreateNew` para la descarga y el nonce:

1. Se invoca la comprobación WSL en una conexión SQLite de solo
   lectura sobre una raíz nueva marcada `/tmp`.
2. Se compara `download_id`, `worker`, `attempt`,
   `torrent_hash`, estado completado, verificación, organización
   pendiente y expiración estricta del lease.
3. Fallo de la fuente, salida inválida, discrepancia o vencimiento:
   se devuelve un acuse HMAC `no_autorizada` y **no se registra
   ninguna reserva nueva**. No se divulga al cliente el estado
   interno de la consulta.
4. Si la consulta es positiva, se aplican las reservas existentes
   por `download_id` y nonce. La reserva por descarga usa ahora
   `version=2` e incluye `torrent_hash`, además de worker, intento,
   manifiesto, sandbox, staging, destino, nonce y fecha.
5. La respuesta positiva sigue siendo
   `intencion_registrada_sin_publicar`. No se mueve ningún archivo
   y no se confirma nada en SQLite.

Es una configuración **explícita del servidor de prueba**, no un
modo seguro predeterminado para producción. La ruta de SQLite no
procede del sobre HMAC.

## Resultados comprobados

La prueba de integración terminó con **9 resultados correctos**,
salida 0 (14,21 segundos en la repetición final):

| Caso | Resultado |
|---|---|
| Sobre v1 enviado al servidor que exige lease | Rechazado |
| Worker distinto del titular del lease | Rechazado, sin reservas |
| Número de intento obsoleto | Rechazado, sin reservas |
| Hash del torrent distinto del valor SQLite | Rechazado, sin reservas |
| Ruta de SQLite ficticia inexistente | Rechazado, sin reservas |
| Sobre v2 enviado al servidor histórico sin gate | Rechazado |
| Cliente intenta escoger `LeaseDatabase` | Rechazado |
| Lease ficticio vigente | Admitido, reserva v2 con identidad y hashes |
| Lease caducado tras la admisión | Nueva solicitud rechazada sin nuevo nonce |

El primer ensayo falló por intentar firmar un estado no incluido en
el protocolo de acuses. Se corrigió conservando la respuesta
autenticada **`no_autorizada`**; no se amplió la enumeración de
estados ni se dejó un camino de admisión ambiguo. Se comprobó que
el `finally` eliminaba el diario, la clave y la SQLite ficticia.

Regresión: `scripts/test_viewtv_windows_pipe_broker_sandbox.ps1`
volvió a completar **30 comprobaciones** (21,09 segundos), incluida
concurrencia y el replay por descarga. El backend en Ubuntu,
con `PYTHONDONTWRITEBYTECODE=1` y sin caché de pytest, terminó con
**545 passed, 2 warnings**, exit code 0 (40,74 segundos), sin
cambios en los archivos de producción.

Se verificó el parser PowerShell 5.1 de los cuatro scripts del hito,
`git diff --check` y el inventario de limpieza: **cero** diarios pipe,
claves efímeras, cuentas Windows temporales y carpetas sandbox en
`C:\Users\Public`, y ninguna SQLite de ensayo en `/tmp`.

## Respaldo anterior a cambios

`/home/viewtv/viewtv-backups/admision-lease-pipe-pre-20261120-153423.tar.gz`

SHA-256:
`03666f810340c4ce1aaa0170ba3619951885673e1c096a1bd39b01476a18587f`

El `tar -tzf` verificado contiene exactamente:
- `scripts/viewtv_windows_pipe_broker_sandbox.ps1`
- `scripts/test_viewtv_windows_pipe_broker_sandbox.ps1`
- `docs/ORGANIZADOR-REPLAY-POR-DESCARGA-BROKER-WINDOWS-SANDBOX.md`

Los dos scripts de lease para pipe y este documento son nuevos.

## Límites pendientes y criterio de NO despliegue

- El lease proviene de una **SQLite creada por el ensayo**. La ruta se
  fija al iniciar el servidor, pero todavía no es una autoridad de
  producción ni una consulta viva a qBittorrent. El hash se coteja
  contra SQLite, **no contra el cliente de torrent en tiempo real**.
- Una consulta puntual y `FileMode.CreateNew` no forman una
  transacción. El lease puede perderse entre la comprobación y la
  reserva; tampoco se repite en esta modalidad antes de un
  `Directory.Move` porque este canal **no publica**.
- El canal de ensayo v1 sigue disponible con otros argumentos para
  las regresiones. Por tanto **no existe cierre de bypass de
  publicación** ni obligación de gate en todos los procesos reales.
- El HMAC de prueba sigue compartido; no existe servicio Windows
  persistente bajo SID independiente del worker, ni autoridad única
  protegida de lease/intent/torrent para publicación.
- Faltan recuperación durable global y conciliación NTFS+SQLite,
  bloqueo TOCTOU, comprobación qBittorrent GET auténtica y pruebas
  de volumen/caída física. No cambiar `VIEWTV_ENABLE_DOWNLOAD_START=false`.
- La API 0012 sigue requiriendo diagnóstico y recuperación aparte:
  imagen `viewtv:local` reiniciándose con worker en imagen distinta.

## Actualización posterior: doble gate lease + torrent ficticio

Se añadió la **modalidad v3** que exige lease WSL y consulta HTTP GET de
un origen qBittorrent **ficticio** antes de reservar. La fuente HTTP
queda fijada por el servidor y no puede elegirse desde el cliente.
Las modalidades v1 y v2 siguen disponibles para regresiones de sandbox,
**no como vías productivas de publicación**. Véase
[ORGANIZADOR-DOBLE-GATE-LEASE-TORRENT-PIPE-SANDBOX.md](ORGANIZADOR-DOBLE-GATE-LEASE-TORRENT-PIPE-SANDBOX.md).

**Decisión:** admisión por pipe vinculada a lease de sandbox demostrada.
La **fase 1 sigue abierta** y el PR #2 continúa en borrador,
sin publicación ni despliegue.
