# VIEWTV 0013 — reservas anti-replay por descarga en el canal broker (solo sandbox)

Fecha: 20-11-2026. Rama: `viewtv-seguimiento-descargas-0012`.
**No es un servicio Windows productivo. No publica medios.**

## Brecha resuelta dentro del ensayo

El broker de prueba `scripts/viewtv_windows_pipe_broker_sandbox.ps1`
ya verificaba HMAC-SHA-256 sobre la intención y reservaba un nonce
durable mediante creación exclusiva de archivo. Pero una petición
con **otro nonce legítimo y el mismo `download_id`**, incluso con
otro `attempt`, podía admitirse. La protección por nonce era insuficiente
para impedir dos admisiones del mismo trabajo.

Se añadió una **reserva por `download_id` en el mismo diario privado
y marcado**, sin cambiar el protocolo de pipe ni autorizar ninguna
publicación. El `download_id` tiene que ser un entero positivo verificado
dentro del sobre HMAC y la reserva está ligada a intento, worker,
sandbox GUID, staging, destino, SHA-256 de manifiesto, nonce y fecha.

## Orden obligatorio de escrituras

Para cada mensaje HMAC válido, sobre un diario
`%TEMP%\viewtv-pipe-broker-<GUID>` prevalidado con ACL restringida:

1. Se rechaza sin mutación cualquier nonce YA existente.
2. Se intenta crear exclusivamente
   `.viewtv-download-<download_id>.json` mediante
   `FileMode.CreateNew`, `FileShare.None`,
   `FileOptions.WriteThrough` y `Flush(true)`.
3. Si la reserva existe, se devuelve `replay_bloqueado` incluso si
   el nonce y el intento son nuevos. Si no puede reservarse con
   fiabilidad, **no se admite**.
4. Solo después se crea
   `.viewtv-nonce-<nonce>.json` con las mismas garantías.
5. Se devuelve `intencion_registrada_sin_publicar` solamente si
   ambas escrituras finalizan. No se llama a `Directory.Move`,
   al worker, a qBittorrent, a Docker o a SQLite.

**El orden importa:** la reserva de la descarga se crea primero. Si
el proceso cae antes de reservar el nonce, un reinicio conserva el
bloqueo por `download_id`. No se elimina automáticamente ningún
registro parcial ni se permite un reintento ciego: requiere
**conciliación humana**. El almacenamiento de dos archivos no
constituye una transacción atómica y puede bloquear conservadoramente
trabajos por interrupción o error de I/O.

No se promete supervivencia ante un corte físico de alimentación:
`WriteThrough` y `Flush(true)` son solicitudes al sistema de archivos,
no una comprobación de fallo de hardware.

## Evidencias ejecutadas

Prueba: `scripts/test_viewtv_windows_pipe_broker_sandbox.ps1` en
PowerShell 5.1 nativo con servidores/clientes en procesos `Start-Job`
independientes.

Además de las pruebas anteriores de firma, cambio de manifiesto,
acuse autenticado, primera instancia, timeout, nonce, nombres,
caducidad y mensajes malformados, se comprobaron:

- Firma correcta, `download_id=17`: admitida una vez; existe
  reserva por descarga y por nonce.
- Mismo `download_id` con nonce **nuevo**: `replay_bloqueado`.
- Mismo `download_id` con `attempt=2` y nonce nuevo:
  `replay_bloqueado`.
- Nonce ya utilizado en `download_id=22` diferente: bloqueado
  y **sin crear** el archivo de reserva de la descarga 22.
- Otra descarga (`download_id=18`) distinta: admitida.
- Dos brokers simultáneos con **el mismo nonce** para la descarga
  19: exactamente una admisión.
- Un registro `.viewtv-download-20.json` creado de forma incompleta
  como fallo inyectado (sin nonce): **no** permite recuperar admisión
  ni crea el nonce solicitado.
- Dos procesos broker simultáneos con **nonces distintos** para
  `download_id=21`: exactamente una admisión; el otro recibe
  `replay_bloqueado`.
- Conteos finales antes del `finally`: cuatro registros de nonce
  de admisiones válidas y cinco registros por descarga (cuatro
  completos y el incompleto intencional). Los registros completos
  se comprobaron por `download_id`, intento, nonce y JSON.
- El `finally` elimina solamente el diario GUID y claves
  efímeras creados y marcados por el test.

El test del pipe devolvió **30 resultados correctamente observados**
en dos ejecuciones completas (códigos de salida 0), y se verificó
sintaxis PowerShell por el parser de Windows.

Regresiones independientes: el diario NTFS mantuvo **11 casos correctos**;
el puente lease Windows→WSL mantuvo **12 casos correctos**; el backend en
Ubuntu pasó **545 tests, 2 advertencias de deprecación**, exit code 0
(42,48 s). Finalmente se comprobó que había cero diarios pipe,
claves temporales, carpetas sandbox y cuentas Windows efímeras
residuales; y cero raíces ficticias de lease en `/tmp`.
`git diff --check` no informó incidencias.

## Qué **no** resuelve

- La reserva por descarga aplica **solamente dentro del mismo
  `JournalRoot`**. No es un índice global persistente entre
  varios diarios, reinstalaciones ni hosts. El broker definitivo
  necesita una única autoridad duradera y reconciliación de su
  propiedad y continuidad.
- La intención firmada declara un `download_id`, worker, attempt
  y manifiesto, pero **no se coteja con una autoridad viva de lease**,
  ni con la identidad del torrent real. Una firma válida no equivale
  a permiso de publicación.
- La clave HMAC de este ensayo está disponible al cliente de prueba;
  no acredita independencia de secretos ni cuenta Windows de
  servicio realmente separada.
- No hay journal NTFS+SQLite transaccional, protocolo de
  recuperación al caer el broker, validación de intentos reanudados
  en la cola ni prueba de fallo físico.
- Este cambio **no habilita descargas, organización o publicación**.
  No se ha modificado ningún `worker/main.py`, `C:\VIEWTV\media`,
  qBittorrent, Jellyfin ni la SQLite de producción.
- El PR #2 permanece en borrador; la API real 0012 sigue necesitando
  reparar el desajuste de versión respecto del worker.

## Respaldo anterior a cambios

`/home/viewtv/viewtv-backups/replay-descarga-durable-pre-20261120-151620.tar.gz`

SHA-256:
`3b99c3b874475d03525fd8ef588393f7ca173f84705c0487f012f0edc6d6df68`

Se verificó `tar -tzf` y contenía exclusivamente:
- `scripts/viewtv_windows_pipe_broker_sandbox.ps1`
- `scripts/test_viewtv_windows_pipe_broker_sandbox.ps1`
- `docs/ORGANIZADOR-CANAL-BROKER-WINDOWS-SANDBOX.md`

Este documento es nuevo, no existía para respaldarlo.

## Actualización posterior: admisión con lease del servidor

Se añadió la modalidad `-RequireSandboxLease` al servidor de pipe,
con sobre HMAC v2 y hash de torrent. Antes de crear las reservas,
Windows consulta en Ubuntu la SQLite ficticia marcada, comprueba el
worker, intento, hash y vencimiento. El cliente no decide qué DB
consultar, y el rechazo no consume reserva. El registro por descarga
v2 conserva también el hash del torrent. **El canal v1 de prueba
sigue disponible**; esto no habilita ningún servicio de producción.

Detalles, nueve pruebas integradas y límites:
[ORGANIZADOR-ADMISION-LEASE-BROKER-PIPE-SANDBOX.md](ORGANIZADOR-ADMISION-LEASE-BROKER-PIPE-SANDBOX.md).

**Decisión:** hito del bloqueo conservador por descarga completado
en el canal sandbox; **fase 1 abierta**, sin publicar, sin crear
servicios ni tocar producción.
