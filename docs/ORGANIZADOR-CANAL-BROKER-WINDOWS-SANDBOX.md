# VIEWTV 0013 — Canal local Windows con admisión autenticada (sandbox)

**Fecha:** 20-11-2026. **SOLO ENSAYO. NO ES UN BROKER DE PRODUCCIÓN. NO DESPLEGAR.**

**Actualización posterior:** el servidor ya utiliza una apertura nativa Win32
con `FILE_FLAG_FIRST_PIPE_INSTANCE`, validada únicamente en sandbox:
[PRIMERA-INSTANCIA-PIPE-WIN32-SANDBOX.md](ORGANIZADOR-PRIMERA-INSTANCIA-PIPE-WIN32-SANDBOX.md).
El apartado histórico siguiente no prueba ni presupone cuentas Windows separadas.

**Actualización posterior del mismo día:** se añadió un desafío aleatorio por
conexión y un **acuse firmado y vinculado a la solicitud**. Consultar
[RESPUESTA-FIRMADA-BROKER-WINDOWS-SANDBOX.md](ORGANIZADOR-RESPUESTA-FIRMADA-BROKER-WINDOWS-SANDBOX.md).
El protocolo y el conteo de pruebas descritos a continuación reflejan
el **primer hito** del canal; la actualización actual los amplía, sin
demostrar identidades Windows separadas.

## Qué se ha probado

`scripts/viewtv_windows_pipe_broker_sandbox.ps1` implementa una operación
de **admisión sin publicación** entre dos procesos PowerShell nativos de
Windows. El cliente manda una intención serializada y el proceso servidor la
valida por **HMAC-SHA-256**, comprueba sus campos y reserva un **nonce durable**
en un diario restringido antes de devolver `intencion_registrada_sin_publicar`.

- Comunicación: `NamedPipeServerStream` y `NamedPipeClientStream` locales.
  Nombres únicos `viewtv-test-pipe-<GUID>`; sin puerto de red ni HTTP.
- ACL de tubería: DACL **sin herencia**, con acceso solo para el SID Windows
  del ensayo, SYSTEM y Administradores. Se consulta también la ACL
  realmente aplicada al objeto. **No** se ha ejecutado la prueba bajo otra
  cuenta ni demostrado denegación efectiva entre identidades separadas.
- Protocolo original: longitud `Int32` de cuatro bytes seguida de JSON UTF-8
  acotado a **8192 bytes**; los mensajes excesivos se rechazan usando el
  prefijo antes de leer su cuerpo. **El protocolo actualizado antepone
  32 bytes aleatorios como desafío de cliente y firma respuestas de hasta
  2048 bytes**, como explica el documento de actualización.
- Autorización de prueba: sobre `payload` JSON sin cifrar con `signature`
  base64. HMAC calculado sobre los bytes UTF-8 exactos del payload; firma
  cotejada sin salida anticipada dependiente del contenido. Valida versión,
  `download_id`, número de intento, worker, sandbox GUID, nombre de staging
  restringido, destino relativo sin escapes, hash de manifiesto, nonce y
  `expires_utc` estrictamente vigente, máximo cinco minutos.
- El servidor obtiene el secreto de ensayo desde un archivo efímero
  `%TEMP%\viewtv-test-key-<GUID>\key.bin` **fuera de Docker**.
  Las pruebas firman las peticiones con ese mismo secreto; **por lo tanto,
  esto no garantiza separación de credenciales entre cliente y broker**.
- Diario: carpeta exclusiva `%TEMP%\viewtv-pipe-broker-<GUID>`,
  con marcador `.viewtv-pipe-only`, DACL protegida y tres SID exactos.
  El servidor reserva `.viewtv-nonce-<nonce>.json` mediante
  `FileMode.CreateNew`, `FileShare.None`,
  `FileOptions.WriteThrough` y `Flush(true)`.
  El registro contiene únicamente identificadores de prueba y digest del
  manifiesto; ningún secreto ni ruta real.
- Si el nonce ya existe, incluso con **otro plan válido firmado**, se devuelve
  `replay_bloqueado`. En caso de respuesta perdida, un cliente no puede
  convertir la repetición en una segunda admisión.
- **Ninguna respuesta da permiso de `Directory.Move`**: el script no llama
  al publicador, al puente de leases, a qBittorrent ni a `worker/main.py`.

## Pruebas ejecutadas (Windows PowerShell 5.1)

`scripts/test_viewtv_windows_pipe_broker_sandbox.ps1` arranca servidores
en procesos `Start-Job` independientes y conexiones a tuberías con nombres
aleatorios, solo con claves y carpetas de prueba nuevas. **17 casos correctos**:

1. Mensaje HMAC válido: una intención **sin publicar** queda registrada.
2. Repetición en **otro proceso servidor**: rechazado por diario persistente.
3. Destino cambiado sin rehacer la firma: rechazado.
4. Huella del manifiesto cambiada: rechazado.
5. Petición caducada: rechazada.
6. Vencimiento demasiado lejano: rechazado.
7. Escape con ruta relativa peligrosa: rechazado.
8. Nonce malformado: rechazado.
9. Mensaje firmado con otra clave: rechazado.
10. JSON de sobre malformado: rechazado.
11. Cuerpo superior a 8 KiB: rechazado sin lectura ilimitada.
12. **Nonce ya utilizado con otro plan recién firmado**: bloqueado.
13. `download_id` como texto en lugar de número: rechazado.
14. Intento como texto en lugar de número: rechazado.
15. Nonce nuevo, petición válida: admitido.
16. **Dos procesos servidores y clientes concurrentes con el mismo nonce**:
    exactamente **una reserva** y una respuesta `replay_bloqueado`.
17. Nombre Windows reservado (`COM1.txt`) aun con HMAC correcto: rechazado.

Al terminar, el test verifica que solo existan los tres registros legítimos
y elimina únicamente sus propias claves efímeras y carpeta GUID marcada.
No modifica cuentas ni servicios Windows, tampoco los permisos de carpetas
preexistentes.

### Repetición

Ejecutar desde **PowerShell nativo Windows** (sin administrador requerido):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_pipe_broker_sandbox.ps1"
```

Para comprobar Git y pruebas Python, desde **WSL Ubuntu**:

```bash
cd /home/viewtv/projects/viewtv-broker-0013-20261119
git diff --check
PYTHONPATH=backend:. /home/viewtv/projects/viewtv/backend/.venv/bin/python -m pytest -q backend/tests
```

## Riesgos abiertos y criterios de no despliegue

**Esto prueba autenticidad HMAC bajo una clave de ensayo compartida entre
procesos del mismo SID, no autenticación de producción ni autorización de
publicación.** Faltan controles fundamentales:

1. Dos cuentas de Windows distintas, sin privilegios del administrador, con
   separación efectiva: el cliente de copia no debe poder leer la clave,
   el diario, crear instancias de la tubería del broker ni escribir destinos.
   Los ACL de ensayo incluyen Administradores, como es normal para
   mantenimiento; **no prueban mínimo privilegio entre identidades**.
2. El **acuse firmado con desafío** de la actualización acredita la
   posesión de la clave compartida, pero todavía falta autenticación
   **de la identidad Windows del servicio titular**, protección frente
   a creación anticipada de la tubería (`FILE_FLAG_FIRST_PIPE_INSTANCE`)
   y proceso/servicio de identidad separada. Un proceso del mismo SID
   que lea la clave todavía podría suplantar la tubería.
3. Interfaz con la autoridad de lease 0013 independiente y qBittorrent
   **solo GET**, vinculando `download_id`, propietario, intento, hash de
   torrent observado, manifiesto, staging y destino autorizados. El HMAC
   de este prototipo prueba integridad del JSON de prueba, pero **no
   consulta el estado real de la cola**.
4. Protección frente a DOS: conexiones parciales o bloqueadas todavía pueden
   mantener ocupado al servidor de una conexión. Se necesitan timeouts,
   cuotas y cancelación, pruebas de parada abrupta y confinamiento de rutas
   antes de considerar un servicio persistente.
5. Control de replay global por `download_id` y `attempt_id`, además del
   nonce; journal duradero en ubicación de servicio, permisos, revalidación
   pre-movimiento, bloqueo de mutaciones TOCTOU y conciliación de la
   divergencia NTFS/SQLite.
6. Copia de varios GiB con heartbeat durante bloqueo real, fallo físico,
   destinos existentes, multiarchivos y migración reversible ensayada
   sobre **copia fresca** `0012→0013→0012`.

No se han creado usuarios, servicios, tareas programadas ni claves reales;
no se ha accedido a bibliotecas ni al torrent ajeno. Producción permanece
en 0012 con `VIEWTV_ENABLE_DOWNLOAD_START=false`. PR #2 debe continuar
en borrador y sin fusionar.

## Regresiones del bloque

La batería existente, ejecutada tras añadir el prototipo de tubería, conservó:
**20** escenarios del publicador Windows, **11** del diario de intención y
**12** del puente Windows→WSL, todos correctos. La suite backend pasó
**545 pruebas** con dos avisos de deprecación preexistentes. El código
anterior no se modificó para añadir el canal, y el modo normal del worker
sigue sin importar el script de tubería. Las 17 comprobaciones de tubería
deben completarse sin publicar carpetas, únicamente escribiendo registros
de intención efímeros bajo el diario GUID.

**Límite de persistencia:** `WriteThrough` y `Flush(true)` del registro
prueban una sincronización solicitada al sistema operativo, no una garantía
de supervivencia ante cortes de alimentación o corrupción del volumen;
esas pruebas continúan pendientes.
