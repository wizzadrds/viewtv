# VIEWTV 0013 — Puente de lectura de lease WSL→publicador Windows (sandbox)

**Fecha:** 19-11-2026. **NO DESPLEGADO. Solo pruebas con datos ficticios y carpetas GUID de sandbox.**

## Propósito y alcance

Se demuestra la integración **PowerShell nativo Windows → WSL Ubuntu (SQLite 0013 ficticia en /tmp) → diario de intención Windows → publicación nativa de carpeta NTFS**, manteniendo la regla de que **un HTTP o un movimiento con éxito NO equivale a confirmar el trabajo de organización en SQLite**.

Se crean cuatro componentes nuevos; no se modifican los módulos del worker productivo, la cola de organización, las migraciones ni los scripts de publicación anteriores:

- `worker/organization_lease_gate_cli_sandbox.py`: ofrece una interfaz CLI únicamente de lectura que retorna `allowed` y `code`. Reutiliza `app.organization_publication_gate_sandbox.check_sandbox_organization_lease`, que exige propietario, intento, torrent y lease vigentes de una base de prueba marcada `/tmp/viewtv-lease-gate-<GUID>/organization.sqlite3`.
- `worker/organization_lease_gate_fixture_sandbox.py`: crea y gestiona **solo datos ficticios de pruebas** bajo una raíz GUID nueva. Sus acciones de fallo inyectado pueden caducar el lease, retirar la verificación o reasignar el worker; solo acepta una raíz marcada y el nombre exacto de SQLite. Para limpiar, exige que solo estén presentes los dos archivos esperados.
- `scripts/viewtv_windows_lease_bridge_sandbox.ps1`: desde Windows invoca `wsl.exe -d Ubuntu-24.04` con **argumentos separados** (sin construir una cadena de comandos) y un intérprete Python/ruta de repositorio de pruebas fijados. Comprueba el lease dos veces antes de llamar al diario y vuelve a leerlo después de la publicación; la pérdida posterior produce `requiere_revision` y ninguna confirmación SQLite. Tiene dos interruptores de inyección de fallo **solo sandbox**, nunca usados por servicios reales.
- `scripts/test_viewtv_windows_lease_bridge_sandbox.ps1`: crea únicamente un sandbox GUID en `C:\Users\Public`, un diario protegido en `%TEMP%`, una clave de ensayo, staging de vídeo/subtítulos ficticios y cinco bases SQLite ficticias independientes bajo `/tmp`. Usa `finally` para retirar solamente los recursos creados y marcados por la prueba.

## Flujo exitoso y denegación conservadora

1. Windows recibe identificadores de la intención y una ruta de SQLite que **únicamente puede apuntar** a `/tmp/viewtv-lease-gate-<GUID>/organization.sqlite3`; no admite rutas proporcionadas hacia producción.
2. WSL verifica el estado real de la fila SQLite de prueba; el resultado no contiene contraseñas, rutas Windows, credenciales ni secretos. Se rechaza cualquier fallo de lectura o respuesta mal formada.
3. Windows repite la lectura inmediatamente antes de invocar el diario de publicación. Si falla, no se crea registro ni se mueve staging.
4. El diario anterior conserva la reserva exclusiva de intención y el bloqueo por staging, y llama al publicador nativo Windows para mover **una carpeta completa nueva** con vídeo/subtítulos.
5. Una tercera lectura verifica que el lease no se perdió mientras se publicaba. Si ya no pertenece al intento vigente, se devuelve `requiere_revision`; el destino publicado se conserva y **no se confirma ni se repite nada automáticamente**.
6. El resultado normal es `publicada_verificada_sin_confirmar_sqlite`, no `organizada`. La validación independiente del estado real del disco y la confirmación de la cola son responsabilidades pendientes de una futura autoridad segura.

## Pruebas ejecutadas en Windows + WSL

La integración nueva superó **12 escenarios**: publicación íntegra y hash SHA-256, bloqueo de segundo intento, otro worker, número de intento incorrecto, hash de torrent distinto, ruta SQLite no permitida, colisión con destino preexistente, pérdida **inyectada** de lease entre comprobaciones (sin publicar), pérdida **inyectada** de lease después de mover (revisión), lease caducado, worker reasignado y verificación revocada.

No se consultó ningún torrent real ni se ejecutaron acciones qBittorrent. El identificador de torrent se compara con **el valor ficticio de SQLite**, no con la API de qBittorrent. Las inyecciones de fallos alteraron exclusivamente las SQLite de prueba bajo `/tmp`; no se forzó una caída del equipo ni se simularon fallos físicos.

### Comandos reproducibles

Desde **PowerShell nativo de Windows** (no desde WSL):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_lease_bridge_sandbox.ps1"
```

Desde **WSL Ubuntu** (para revisión y regresión):

```bash
cd /home/viewtv/projects/viewtv-broker-0013-20261119
/home/viewtv/projects/viewtv/backend/.venv/bin/ruff check worker/organization_lease_gate_cli_sandbox.py worker/organization_lease_gate_fixture_sandbox.py
PYTHONPATH=backend:. /home/viewtv/projects/viewtv/backend/.venv/bin/python -m pytest -q backend/tests
git diff --check
```

## Limitaciones y bloqueos imprescindibles

**Este puente NO es el broker autenticado final**: todos los procesos siguen bajo el mismo usuario Windows, el intérprete del sandbox está fijado a este equipo y el diario anterior aún puede invocarse directamente sin pasar por este puente. No ofrece aislamiento frente a un actor con acceso al usuario Windows ni frente a un proceso hostil en el host.

**La lectura del lease no es una capacidad transaccional sobre NTFS.** Puede caducar entre la segunda lectura y `Directory.Move`, y el código no participa en un protocolo de autorización firmado por una autoridad independiente. Se ha probado el rechazo de pérdidas entre fases, pero no se afirma eliminar el TOCTOU. El diario tampoco reserva todavía un `download_id` a nivel global.

Antes de cualquier publicación real: identidad Windows del broker separada de Docker y del usuario web; canal local autenticado resistente a replay; comprobación vinculada a lease, intento, torrent consultado en vivo, manifiesto, destino y espacio; bloqueo real de mutaciones de staging; copia de tamaño real con heartbeat independiente; pruebas de cortes físicos, concurrencia, permisos reales entre cuentas, series existentes y conciliación durable. Antes de desplegar 0013, respaldo nuevo y ensayo `0012→0013→0012` en copia.

**Estado operativo:** producción VIEWTV continúa 0012, con `VIEWTV_ENABLE_DOWNLOAD_START=false`; no se ha tocado `C:\VIEWTV\media`, ninguna descarga ajena, qBittorrent, Jellyfin, SQLite de producción, Compose ni `worker/main.py`. El PR #2 debe permanecer en borrador y sin fusionar.
