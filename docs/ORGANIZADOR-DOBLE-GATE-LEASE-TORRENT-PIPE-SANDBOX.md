# VIEWTV 0013 — doble gate lease + torrent en pipe Windows (sandbox)

Fecha: 20-11-2026. Rama: `viewtv-seguimiento-descargas-0012`.
**NO apto para producción. NO publica, descarga ni mueve archivos.**

## Objetivo y mejora comprobada

La admisión por pipe v2 comprobaba un lease contra una SQLite ficticia,
pero **no consultaba el estado de ningún torrent**. La sonda HTTP GET de
torrent también existía, pero no estaba conectada al servidor broker.

La modalidad optativa de prueba v3 une **ambas** validaciones y exige
su resultado favorable **antes** de `FileMode.CreateNew` para
`download_id` y nonce.

- Firma HMAC correcta, estructura v3 exacta, intento y hash válidos.
- Lease vigente contra una SQLite de prueba en Ubuntu, cuya ruta fija
  configura el servidor Windows; no puede elegirla el cliente.
- Sonda HTTP GET de torrent ficticio en un puerto alto de
  `127.0.0.1` dentro de Ubuntu: URL fijada por el servidor, nunca
  por el sobre firmado ni por argumentos de modo Client.
- En la sonda se exige el marcador de ensayo, GUID de sandbox que
  **coincida con la solicitud firmada**, hash, etiqueta de propietario,
  estado terminado, progreso, carpeta sintética, tamaños y archivos.
- Si cualquiera falla, respuesta HMAC `no_autorizada` y
  **ninguna reserva nueva**. Si ambos pasan, solo se registra
  `intencion_registrada_sin_publicar`.
- El ledger del `download_id` aceptado en v3 conserva
  `version=3`, worker, intento, torrent_hash, manifest SHA-256,
  sandbox, staging, destino y nonce.
- No se cambia el protocolo de respuesta ni se publica nada.

La modalidad v3 usa en modo Server:
`-RequireSandboxLease -LeaseDatabase <SQLite sintética>`
junto con `-RequireSandboxTorrent -TorrentFixtureUrl <URL de test>`.
No permite habilitar el gate de torrent sin el de lease.
Los sobres v1 y v2 quedan rechazados por un servidor v3;
un servidor v1 o v2 rechaza los sobres v3.
**Los servidores v1/v2 históricos siguen existiendo para tests**;
esto NO es una política de seguridad global o de servicio.

## Código de esta iteración

Modificado:
`scripts/viewtv_windows_pipe_broker_sandbox.ps1`

Nuevos:
- `scripts/viewtv_windows_pipe_torrent_auth_sandbox.ps1`
  llama a WSL con argumentos separados; consulta la sonda Python;
  exige una única respuesta JSON estricta con `allowed=true`
  y código `torrent_ficticio_vigente_en_consulta`.
- `worker/organization_qbit_http_probe_cli_sandbox.py`:
  envoltorio CLI de la sonda GET existente, sin leer .env ni
  contraseñas, sin acceso a qBittorrent real.
- `worker/organization_qbit_http_fixture_server_sandbox.py`:
  servidor HTTP **ficticio** en `127.0.0.1`, puerto alto aleatorio
  desocupado, bajo raíz
  `/tmp/viewtv-qbit-http-<GUID>`, marcador y cierre programado
  por watchdog. Solamente responde a GET de marcador, `torrents/info`,
  `torrents/files` y endpoints internos de control de ensayo.
  Todos los datos (hash, etiquetas, bytes y carpetas) son sintéticos.
- `scripts/test_viewtv_windows_pipe_dual_gate_sandbox.ps1`:
  test integrado, usa procesos Windows broker y WSL fixture distintos;
  crea una SQLite de ensayo, un diario GUID y clave temporal,
  y los elimina tras la prueba.

## Pruebas observadas

La batería integrada `test_viewtv_windows_pipe_dual_gate_sandbox.ps1`
terminó **20 comprobaciones correctas** con exit code 0 (32,14 s) en
la primera ejecución. Se amplió luego a **22 comprobaciones**
(incluidas URL de servidor no autorizada y origen insertado en
el sobre HMAC), con nueva ejecución completa exit code 0
(31,03 s).
Entre ellas:

| Condición | Resultado |
|---|---|
| Sobre v1 o v2 ante servidor que exige v3 | Rechazado |
| Worker o intento distintos del lease | Rechazado sin reserva |
| Hash distinto del registrado en SQLite | Rechazado sin reserva |
| SQLite de prueba inexistente | Rechazado |
| Sobre v3 ante servidor v1 o v2 | Rechazado |
| Cliente intenta elegir DB o fuente torrent | Rechazado |
| URL de origen no loopback/puerto alto | Rechazada al arrancar servidor |
| Cliente incluye URL de origen extra en el sobre firmado | Rechazado |
| Activar gate de torrent sin gate de lease | Rechazado |
| Marcador de origen HTTP no fiable | Rechazado sin reserva |
| Etiqueta de descarga ajena | Rechazado sin reserva |
| Descarga incompleta | Rechazado sin reserva |
| Hash GET inconsistente | Rechazado sin reserva |
| Ruta torrent diferente del staging ficticio | Rechazado |
| Lista de archivos ambigua | Rechazado |
| GUID del sandbox no coincide con el HTTP | Rechazado |
| Lease y torrent correctos | **Una admisión**, no publicación |
| Repetición con nonce nuevo | Rechazada por `download_id` |
| Lease vencido tras la admisión | Sin reservas adicionales |

Antes de cualquier admisión, el test comprobó cero archivos de
reserva para cada rechazo. La única admisión creó una reserva de
descarga versión 3, con worker, intento, hash de torrent y manifiesto.
La prueba de limpieza confirmó **cero** raíces HTTP de ensayo,
SQLite ficticias, diarios de pipe, claves temporales y sandboxes
Windows residuales.

Regresiones independientes, repetidas tras los cambios:
- Canal v1: **30 comprobaciones aprobadas**, exit 0 (20,94 s).
- Canal v2 lease: **9 comprobaciones aprobadas**, exit 0 (14,64 s).
- Parser PowerShell 5.1 de scripts modificados/nuevos: correcto.
- Ruff: sin incidencias en los módulos Python.
- Backend WSL: **615 tests aprobados, 2 warnings** conocidos,
  exit code 0 (44,89 s), sin caché ni bytecode.
- Validación final de Windows PowerShell 5.1 y Ruff: correctas.
- Limpieza de recursos comprobada: cero registros o raíces ficticias restantes.
- `git diff --cached --check` antes de commit.

## Respaldo verificado antes de modificar archivos existentes

Archivo:
`/home/viewtv/viewtv-backups/doble-gate-lease-torrent-pre-20261120-155106.tar.gz`

SHA-256:
`42fb262fd1cc13198bd136e0ecf59f2be02e860b8ee4fbb62dcaff9d11ea8c78`

`tar -tzf` verificó exclusivamente:
- `scripts/viewtv_windows_pipe_broker_sandbox.ps1`
- `docs/ORGANIZADOR-ADMISION-LEASE-BROKER-PIPE-SANDBOX.md`
- `docs/ORGANIZADOR-SONDA-QBITTORRENT-HTTP-SANDBOX.md`

Los cuatro archivos nuevos no existían y no tenían versión
anterior que respaldar.

## Límites que siguen bloqueando la fase 1

- La fuente HTTP marcada es **ficticia** y su token/marker NO autentica
  un origen hostil. NO se ha consultado el qBittorrent productivo.
  Solo se ha demostrado la mecánica de dos gates obligatorios v3.
- El proceso de broker de pruebas corre bajo PowerShell Windows
  elevado, con HMAC de prueba compartido. NO existe todavía un
  servicio real bajo SID Windows separado de bajo privilegio ni
  control exclusivo de credenciales por un broker independiente.
- La consulta SQLite/HTTP del **pipe** es puntual. Puede cambiar
  la autoridad después del GET y antes de la reserva; el canal
  de admisión **no mueve archivos**.
  **Actualización posterior:** en otro modo estricto del
  publicador NTFS de sandbox se han integrado nuevas consultas a
  lease/HTTP antes de cada rename, leídas de una configuración
  privada asociada al hash del plan firmado. La validación final
  sigue siendo una operación NO transaccional; el modo histórico
  no exige todavía esta política. Véase
  [ORGANIZADOR-REVALIDACION-FINAL-LEASE-TORRENT-SANDBOX.md](ORGANIZADOR-REVALIDACION-FINAL-LEASE-TORRENT-SANDBOX.md).
- El journal es local al GUID, no una autoridad global persistente
  entre instancias. No existe transacción NTFS+SQLite ni protocolo
  completo de recuperación para corte de energía o fallos multigiB.
- No tocar biblioteca real, torrents, `.env`, PIN, producción,
  Docker ni SQLite productiva. Mantener inicio automático de
  descargas deshabilitado y PR #2 en borrador.
- La API 0012 sigue reiniciándose por incompatibilidad de migraciones
  que requiere restauración separada y autorizada.

**Decisión:** el doble gate de admisión v3 está probado únicamente
en sandbox. **La fase 1 permanece abierta** y no se autoriza
fusión, publicación o despliegue.
