# VIEWTV 0013 — Heartbeat independiente y protección del número de intento

**Estado: sandbox de desarrollo, no desplegado. Fecha: 20-11-2026.**

**Actualización posterior del 20-11-2026:** el hilo independiente ya se ha
integrado **como modo opcional del ejecutor de sandbox**, con pruebas de
bloqueo y pérdida de lease. Los párrafos siguientes conservan la evidencia
del hito inicial; para la integración más reciente consultar
[RUNNER CON HEARTBEAT CONCURRENTE](ORGANIZADOR-RUNNER-HEARTBEAT-CONCURRENTE-SANDBOX.md).
El flujo productivo sigue sin conexión al heartbeat ni al broker Windows.

## Objetivo

El ejecutor experimental de organización 0013 renovaba su lease en callbacks
de progreso de copia. Si el sistema de archivos bloquea una operación durante
más de 180 segundos, no hay callbacks y un lease puede caducar, permitiendo una
nueva reclamación mientras la primera copia continúa. Un HTTP correcto y un
SHA-256 final no prueban que el intento todavía sea propietario del trabajo.

Este bloque demuestra que un hilo **independiente del hilo que copia** puede
renovar el lease de una SQLite 0013 ficticia; además evita que un intento antiguo
del **mismo worker** renueve o finalice la reclamación siguiente (problema ABA).

## Componentes cambiados

- `backend/app/organization_queue.py`: las operaciones
  `renew_organization_lease`, `confirm_organization`,
  `mark_organization_review` y `defer_organization` aceptan el argumento
  opcional `expected_attempt`. Cuando se facilita, la condición SQL
  `UPDATE ... WHERE` exige la **coincidencia atómica** con
  `organizacion_intentos`; no hay lectura seguida de escritura separada.
  El intento se valida estrictamente de 1 a 3. Se preserva la compatibilidad
  con las llamadas existentes sin este parámetro.
- `worker/organization_runner_sandbox.py`: conserva el intento reclamado
  y lo remite en sus operaciones de renovación, confirmación, aplazamiento
  y revisión. **Sigue usando callbacks**, no incorpora todavía el nuevo hilo.
  No se modifica `worker/main.py`.
- `worker/organization_lease_heartbeat_sandbox.py`:
  `IndependentOrganizationHeartbeat` usa **otra sesión/conexión SQLite**
  desde un hilo distinto, con `Event.wait(intervalo)`, y no depende de
  callbacks. La ruta SQLite del engine debe corresponder exactamente a
  `/tmp/viewtv-lease-gate-<GUID>/organization.sqlite3` con marcador
  `.viewtv-lease-gate-sandbox-only`, comprobado antes y durante los
  pulsos. No puede abrir la base real ni cambiar rutas Windows.
- En el arranque se ejecuta una renovación **sincrónica**. Los ciclos
  posteriores ejecutan `renew_organization_lease(...,
  expected_attempt=intento)` y no confirman una publicación. Errores de
  conexión, bloqueos SQLite prolongados, marcador alterado, lease caducado,
  propietario modificado o intento sustituido activan estado de **pérdida
  conservadora**. El hilo se detiene y una llamada a `require_active()`
  impide seguir a publicación.
- El usuario del componente debe llamar `require_active()` antes de cada
  punto irreversible de su flujo y **después** de cualquier bloqueo largo.
  `stop()` detiene y espera al hilo; no deja renovaciones corriendo
  deliberadamente al terminar el ensayo.

## Pruebas y alcance

`backend/tests/test_organization_lease_heartbeat_sandbox.py` crea una
SQLite con perfil, solicitud, descarga y lease **ficticios**, únicamente
bajo una raíz aleatoria marcada de `/tmp`. Incluye:

1. Escritura y copia **efectivas** de **128 MiB** sintéticos, bloques de
   1 MiB, cotejo SHA-256 y varias renovaciones del hilo **sin callbacks**.
2. Reasignación del propietario mientras el ejecutor se encuentra bloqueado:
   detección de pérdida y rechazo de `require_active()`.
3. Nuevo intento del mismo worker tras caducar: el heartbeat viejo deja de
   poder renovar. Solo el intento nuevo puede renovar o confirmar.
4. Marcador de SQLite alterado: fallo cerrado; restauración del marcador del
   sandbox durante el `finally`.
5. Rechazo de inicios dobles, verificaciones tras parada, valores inválidos
   y bases SQLite fuera de la raíz de pruebas.
6. La cola comprueba por separado que el intento antiguo **no puede**
   renovar, confirmar, aplazar ni poner en revisión el intento nuevo,
   incluso si el identificador de worker coincide.

La copia es **128 MiB**, bastante mayor que los tests pequeños previos,
pero **no constituye todavía una prueba de una película real de varios GiB,
ni de NTFS/DrvFS, antivirus, Jellyfin, cortes de alimentación o bloqueo
efectivo de escritura en Windows**. Tampoco implementa una operación atómica
entre la base SQLite y un `Directory.Move` de NTFS.

### Reproducción (WSL Ubuntu, NO PowerShell Windows)

```bash
cd /home/viewtv/projects/viewtv-broker-0013-20261119
PYTHONPATH=backend:. /home/viewtv/projects/viewtv/backend/.venv/bin/python -m pytest -q backend/tests/test_organization_lease_heartbeat_sandbox.py backend/tests/test_organization_queue.py
PYTHONPATH=backend:. /home/viewtv/projects/viewtv/backend/.venv/bin/python -m pytest -q backend/tests
/home/viewtv/projects/viewtv/backend/.venv/bin/ruff check backend/app/organization_queue.py worker/organization_runner_sandbox.py worker/organization_lease_heartbeat_sandbox.py backend/tests/test_organization_lease_heartbeat_sandbox.py
```

**Restricciones de seguridad:** no se ha instalado un servicio Windows ni
usado las cuentas locales preexistentes. No se crea ninguna cuenta nueva.
El heartbeat experimental NO está conectado al publicador de Windows,
`worker/main.py` ni a la base de producción. No se accede a
`C:\VIEWTV\media`, torrents, qBittorrent o servicios de producción;
`VIEWTV_ENABLE_DOWNLOAD_START=false` permanece como requisito.

## Bloqueos antes de declarar 0013 operativo

- Broker Windows bajo identidad realmente separada de la identidad que
  copia, ACL auditadas entre cuentas y autenticación del canal Docker–Windows.
- Ligadura durable de lease, intento, hash de torrent validado en vivo,
  manifiesto/staging y destino con revisión **justo antes** de publicar.
- TOCTOU: impedir por permisos que Docker o terceros muten el staging
  después de la verificación; el simple bloqueo de descriptores se mostró
  incompatible con `Directory.Move` en este NTFS.
- Integrar el hilo con el ejecutor end-to-end sin prolongar leases de
  trabajos terminados; probar copia de varios GiB, I/O bloqueante real,
  expiración durante copia, caída abrupta y recuperación del diario.
- No desplegar hasta respaldo nuevo y ensayo reversible
  `0012 → 0013 → 0012` sobre copia, seguido de un plan supervisado.

## Resultados verificados en el equipo (20-11-2026)

- **57 tests específicos** de cola y heartbeat correctos.
- **535 tests backend correctos**, dos avisos de deprecación preexistentes.
- **12 comprobaciones del puente Windows→WSL correctas**, sin cambio de
  comportamiento en el publicador.
- Ruff `check` correcto en todos los archivos Python afectados.
- No quedaron `/tmp/viewtv-lease-gate-*`, sandbox Windows, diario ni
  directorios de claves efímeras tras la ejecución.
- `git diff --check` correcto. Solo se modifica el código de desarrollo
  de la cola y el ejecutor sandbox y se añaden módulo, tests y este documento.

**Interpretación:** 128 MiB fue un archivo ficticio copiado por bloques, no
una descarga gestionada por qBittorrent. El hilo sí renovó el lease mientras
el bucle de copia no invocaba callbacks. Una interrupción o revocación de
lease impide la autorización posterior; todavía no detiene por sí misma
una llamada de I/O bloqueante ni retira contenidos que hayan quedado
publicados: esas situaciones deben conciliarse de forma conservadora.
