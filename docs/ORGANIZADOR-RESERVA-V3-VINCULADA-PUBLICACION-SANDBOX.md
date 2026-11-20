# VIEWTV 0013 — reserva durable v3 vinculada al plan de publicación

Fecha: 20-11-2026. Rama: `viewtv-seguimiento-descargas-0012`.
**SOLO SANDBOX, NO DESPLIEGUE.** Ni qBittorrent real ni medios de
`C:\VIEWTV\media` ni SQLite productiva.

## Problema que se corrige

La publicación estricta del hito anterior consultaba lease y torrent
ficticio **antes de ambos movimientos NTFS**, pero una configuración
privada aparentemente correcta bastaba sin comprobar que el broker de
admisión hubiera aceptado *ese mismo plan firmado*. Se podía intentar
publicar una intención firmada sin una admisión durable v3.

El control añadido
`scripts/viewtv_windows_v3_claim_gate_sandbox.ps1` exige ahora,
**obligatoriamente en el modo
`-BrokerHandoff -RequireFinalSandboxAuthority`**, que existan:

- Una reserva `.viewtv-download-<download_id>.json` con
  `version=3`, creada de manera exclusiva y durable por el
  broker de pipe del ensayo.
- Una reserva `.viewtv-nonce-<nonce>.json` con `version=1`,
  escrita después de la anterior por el mismo protocolo.
- Un `journal_root` leído **solo** del registro con ACL privada
  de la cámara broker y validado como directorio temporal
  `viewtv-pipe-broker-<GUID>` con su marcador exacto.
- Coincidencia exacta con el **payload de aprobación HMAC**:
  SHA-256 de ese payload, nonce firmado, ID de descarga,
  worker, intento, nombre del sandbox, staging, destino
  y hash del torrent registrado.
- Coincidencia también entre los dos archivos de reserva,
  incluida la fecha `reserved_utc`.

Se rechazan las reservas v1/v2 reutilizadas, ausentes, vacías,
parciales o con campos inesperados, JSON no canónico, hash/tipo
alterado, nonce incorrecto, marcas de tiempo futuras o de
más de cinco minutos. No hay auto-reintento.

## Barreras de permisos y tiempo

El lector no crea ni modifica reservas: usa exclusivamente lectura.
Rechaza un diario con propietario o ACL inesperada, herencia
de permisos sin protección en la raíz, ACE ajenas o denegadas,
falta de FullControl de broker, SYSTEM y Administradores, y
reparse points. En ficheros comprueba sus reglas heredadas o
protegidas, propietario autorizado y tamaño acotado.
El lector exige el marcador
`VIEWTV_PIPE_BROKER_TEST_ONLY_V1`.

En `scripts/viewtv_windows_final_gate_sandbox.ps1`, después de
verificar la relación con el plan firmado y antes de consultar
las fuentes WSL, ahora se exige este registro durable. La misma
función se llama antes del primer rename a la cámara privada y
antes del segundo rename al destino; un fallo posterior a la
primera entrega deja el escrow para revisión manual.

**Este vínculo no es una transacción NTFS+SQLite**: los registros,
las consultas y los movimientos ocurren en instantes distintos.
Administradores hostiles y procesos con los secretos de prueba
siguen fuera del modelo de protección. La validez de la reserva
está limitada a cinco minutos para impedir usar una admisión
histórica como autorización permanente.

## Pruebas ejecutadas en Windows y Ubuntu

Se amplió
`scripts/test_viewtv_windows_premove_double_gate_sandbox.ps1`.
Ahora, en un GUID marcado y con clave efímera, crea un diario
restringido y solicita una admisión **real a través del named pipe
v3**, con SQLite sintética y HTTP GET ficticio. Solo después
presenta el plan y verifica los dos renames de archivos
sintéticos.

Resultados: **17 verificaciones correctas**, exit code 0
(18,02 s en la ejecución final). Incluye:

| Condición | Resultado |
|---|---|
| Publicación estricta sin entrega privada | Rechazada |
| Configuración final inexistente | Rechazada |
| SID del broker registrado incorrecto | Rechazado |
| SHA-256 de plan ajeno | Rechazado |
| ACE del grupo Users en configuración | Rechazada |
| Configuración sin reservas v3 | Rechazada |
| Admisión real v3 por pipe | Registrada, sin publicación |
| Worker falseado dentro de reserva | Rechazado |
| Reserva v2 reutilizada en modo estricto | Rechazada |
| Hash de torrent distinto en reserva | Rechazado |
| Nonce/manifiesto contradictorio | Rechazado |
| Reserva de descarga sin registro nonce | Rechazada |
| ACE Users de lectura en reserva | Rechazada |
| Etiqueta del torrent ajena antes de mover | Rechazada |
| Plan+lease+torrent+reserva coherentes | Publicación sintética correcta |
| Torrent incompleto en escrow simulado | Bloqueado |
| Lease caducado en escrow simulado | Bloqueado |

El ensayo de cambio después del primer movimiento **usa un escrow
simulado y el mismo lector que emplea el publicador**. No demuestra
aún un crash real durante una operación productiva.

Para probar un segundo trabajo del laboratorio con el mismo ID
ficticio se utiliza **otro diario GUID**. Este hecho refuerza
una limitación: aún no existe un único journal protegido que evite
replays entre diarios/hosts. NO se debe interpretar la prueba
como una autoridad global de descarga.

Regresiones de Windows:
- Handoff/identidad: **14 correctas**.
- Publicador histórico: **20 correctas**.
- ACL/quiescencia: **29 correctas**.
- Canal broker v3: **22 correctas**.
- Backend Ubuntu: **615 pruebas aprobadas**, dos avisos de deprecación
  conocidos, exit code 0 (43,25 s) sin caché ni bytecode.
- Parser Windows PowerShell 5.1 de archivos nuevos/editados: correcto.

Los fixtures crean únicamente ficheros de pequeño tamaño bajo
`C:\Users\Public\viewtv-win-sandbox-<GUID>`,
`%TEMP%\viewtv-pipe-broker-<GUID>` y
`/tmp/viewtv-lease-gate-<GUID>` y
`/tmp/viewtv-qbit-http-<GUID>`.
El `finally` verifica nombres, marcadores y ausencia de reparse
antes de eliminar **solo** los recursos que generó el ensayo.

## Respaldo anterior a las modificaciones

`/home/viewtv/viewtv-backups/pinned-v3-claim-pre-20261120-164624.tar.gz`

SHA-256:
`12cfc20981bfecf9c4b5e58e75f8b73f48ddafa35054f7e2fa06fbf819c4ac34`

Verificado con `tar -tzf`; incluye exactamente:
- `scripts/viewtv_windows_final_gate_sandbox.ps1`
- `scripts/test_viewtv_windows_premove_double_gate_sandbox.ps1`
- `docs/ORGANIZADOR-REVALIDACION-FINAL-LEASE-TORRENT-SANDBOX.md`

Este nuevo lector y este informe no tenían versión anterior.

## Pendiente para terminar la fase 1

- Crear servicio broker **Windows de bajo privilegio**, con SID
  propio, configuración/secreto custodiados fuera del worker y
  un **único journal durable**, sin aceptar URL o base de datos
  elegidas por clientes.
- Eliminar/cerrar toda publicación que no requiera la política
  estricta. El modo histórico del sandbox aún existe para
  regresiones y no debe desplegarse.
- Integrar autoridad real de lease y torrent y revalidar sin
  TOCTOU observable, además de un protocolo de reconciliación
  con SQLite y NTFS ante crash/pérdida de alimentación.
- Ensayar con varios GiB, fallos de I/O y recuperación.
- Resolver por separado la incompatibilidad de imagen
  API/worker 0012 con respaldo consistente y plan reversible.
- Mantener PR #2 en borrador; ninguna fusión, despliegue o
  reparación de producción sin autorización.

**Decisión:** asociación de admisión v3 y publicación sintética
comprobada; **fase 1 sigue abierta**.
