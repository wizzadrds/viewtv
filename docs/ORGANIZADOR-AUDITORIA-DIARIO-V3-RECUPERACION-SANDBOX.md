# VIEWTV 0013 — auditoría fail-closed del diario v3 entre procesos

Fecha: 20-11-2026. Rama: `viewtv-seguimiento-descargas-0012`.
**Sandbox Windows/Ubuntu, NO producción.** La API, las descargas
reales y `C:\VIEWTV\media` no se han modificado.

## Riesgo corregido en el ensayo

El broker de pipe ya utilizaba dos reservas durables por admisión:
`.viewtv-download-<id>.json` y `.viewtv-nonce-<nonce>.json`.
Al reiniciarlo con el mismo diario, un archivo parcial bloqueaba
la **misma descarga**, pero podía no impedir nuevas admisiones
para otras descargas. Tampoco bastaba validar que un JSON pareciera
coherente: un cambio arbitrario de `worker`, por ejemplo, podía
seguir siendo estructuralmente válido si el registro de nonce no
contenía ese campo.

En el nuevo modo de admisión **v3**, cada solicitud HMAC bien formada
audita TODO el diario **antes** de consultar el lease y el HTTP y
antes de intentar cualquier nueva reserva. La auditoría es de
**solo lectura**: no borra, repara ni sobrescribe registros.

**El control se ejecuta al procesar una solicitud**, incluso en un
proceso broker distinto del que creó el registro. No es todavía un
daemon de recuperación ni un barrido programado al arrancar el
sistema operativo. Los modos históricos v1/v2 siguen disponibles
para sus regresiones y NO se consideran seguros para producción.

## Implementación

Código nuevo:
`scripts/viewtv_windows_v3_journal_audit_sandbox.ps1`

Modificados:
- `scripts/viewtv_windows_pipe_broker_sandbox.ps1`
- `scripts/viewtv_windows_v3_claim_gate_sandbox.ps1`
- `scripts/test_viewtv_windows_pipe_dual_gate_sandbox.ps1`

El auditor exige un diario marcado con nombre
`%TEMP%\viewtv-pipe-broker-<GUID>`, ACL restringida y
sin reparse points. Inspecciona **todas** las entradas (con un
máximo de 129, incluida la marca), permite exclusivamente la marca,
las reservas de descarga y sus reservas de nonce, y verifica que
exista una pareja íntegra y única por descarga.

Cada pareja pasa el lector estricto de reserva v3:
tipos, campos exactos, JSON canónico, IDs, worker, intento,
sandbox, staging, destino, torrent_hash, SHA-256 del plan,
nonce, marca de tiempo, propietario y ACL. Si falta alguno,
la operación se detiene con estado HMAC `requiere_revision`.

### Integridad HMAC del registro de descarga

Antes de escribir una reserva de descarga **v3**, el broker
calcula `claim_hmac` sobre el JSON canónico del registro
**sin el propio campo HMAC**, con el dominio separado
`VIEWTV_V3_JOURNAL_CLAIM_V1\n`. El lector y el auditor
recalculan el MAC usando la **clave de laboratorio del broker**
y comparan los 32 bytes de forma constante.

Así se detectan modificaciones en campos que no están presentes
en el registro del nonce, incluido el worker. El registro
de nonce queda unido a la reserva de descarga mediante nonce,
hash de plan, ID, intento y marca de tiempo.

Las reservas v1/v2 no cambian de formato. Solo se acepta el
nuevo formato HMAC en el diario estricto v3. Antes de publicar
en el modo estricto, el publicador también exige ese MAC
en su lectura del registro de admisión.

**Límite criptográfico:** la misma clave efímera de prueba
se utiliza para el protocolo del laboratorio y el MAC; aún
no existe un secreto dedicado custodiado por un servicio Windows
de bajo privilegio. No protege ante un atacante con esa clave ni
ante un administrador hostil.

### Historia antigua frente a autorización reciente

La auditoría permite **parejas completas antiguas**, de modo que
un reinicio no obliga a borrar el historial para seguir funcionando.
Pero la verificación de una reserva para **publicar** mantiene
la caducidad estricta de cinco minutos: no puede usarse un
registro viejo como permiso de movimiento NTFS.

Nunca se libera automáticamente una reserva, y una admisión repetida
del mismo `download_id` sigue recibiendo `replay_bloqueado`.

## Pruebas de recuperación y regresión

`scripts/test_viewtv_windows_pipe_dual_gate_sandbox.ps1`:
**26 comprobaciones correctas**, exit code 0 (44,69 s).

La prueba usa varios procesos broker `Start-Job` que comparten el
**mismo diario GUID** mientras el ensayo está activo. Verificó:

- Un registro huérfano de una descarga distinta detiene una nueva
  solicitud válida en otro proceso: `requiere_revision`, cero
  reservas nuevas. El archivo huérfano permanece intacto.
- Un archivo inesperado detiene el diario sin borrarlo.
- Después de retirar el daño **exclusivamente desde el test**,
  vuelve a admitirse una solicitud legítima.
- Modificar el worker de una reserva firmada invalida su MAC;
  el broker rehúsa admitir otra solicitud y conserva el registro.
- Una pareja íntegra pero de hace tres horas se reconoce como
  historia válida; aun así, no admite de nuevo la descarga.
- Se mantienen las comprobaciones anteriores de versión, propiedad,
  hash de torrent, estado completo, nonce y lease.

Se completaron además:
- Publicador estricto con admisión y MAC del pipe: **17 correctas**,
  exit code 0 (20,37 s).
- Pipe v1: **30 correctas**, exit code 0 (29,42 s).
- Pipe v2 con lease: **9 correctas**, exit code 0 (18,54 s).
- Parser PowerShell 5.1: correcto para los cinco scripts implicados.
- Backend Ubuntu: **615 pruebas aprobadas**, dos avisos de
  deprecación conocidos, exit code 0 (46,54 s), sin caché ni bytecode.
- Cleanup: comprobación independiente de temporales Windows y WSL.

En todos los casos de corrupción, **solo el test** deshizo su
inyección para poder proseguir; el broker no intentó reparar,
recortar o suprimir evidencias.

## Respaldo previo a cambios

`/home/viewtv/viewtv-backups/auditoria-arranque-v3-pre-20261120-170608.tar.gz`

SHA-256:
`742b30b8ff5a76610f486b9d9aded7099092acca1f86904ef774df049f61c886`

Verificado con `tar -tzf`. Incluye exactamente:
- `scripts/viewtv_windows_pipe_broker_sandbox.ps1`
- `scripts/viewtv_windows_v3_claim_gate_sandbox.ps1`
- `scripts/test_viewtv_windows_pipe_dual_gate_sandbox.ps1`
- `docs/ORGANIZADOR-RESERVA-V3-VINCULADA-PUBLICACION-SANDBOX.md`

Segundo respaldo del lector de publicación previo a editarlo:
`/home/viewtv/viewtv-backups/firmar-claim-v3-final-pre-20261120-171244.tar.gz`

SHA-256:
`5ea741bb015f64e3f49b2aba3ba23cb0acaea05b071215088e1656fe5cd51ab2`

Verificado con `tar -tzf` con una sola entrada:
`scripts/viewtv_windows_final_gate_sandbox.ps1`.

El archivo de auditoría y este informe son nuevos.

## Límites y próximos pasos

- La autoridad es **un diario GUID dentro de `%TEMP%`**. Los
  tests muestran varios procesos compartiendo ese diario, pero
  otro GUID puede admitir otra vez el mismo ID. Todavía no existe
  un journal único global, persistente entre instalaciones.
- No hay servicio Windows autónomo bajo SID no administrativo,
  ni custodia separada de secretos.
- La auditoría no garantiza sincronización atómica de dos archivos:
  otra petición podría observar una escritura en curso y
  rechazar conservadoramente. Esto requiere una estrategia de
  bloqueo/serialización y recuperación antes de despliegue.
- Los registros válidos siguen pendientes de conciliación
  NTFS/SQLite/qBittorrent, así como recuperaciones reales ante
  pérdida de energía, disco lleno y volúmenes multigiB.
- Nada de esto habilita descargas o publicación en producción,
  ni repara la API 0012 reiniciándose.
- PR #2 continúa en borrador y sin fusionar.

**Decisión:** auditoría de reinicio/reentrada en un diario v3
de pruebas, con MAC e inspección completa, validada. **Fase 1
aún abierta**: servicio de bajo privilegio y autoridad durable
global siguen pendientes.
