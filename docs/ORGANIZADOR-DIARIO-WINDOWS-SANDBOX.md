# VIEWTV — Diario exclusivo de publicación Windows (sandbox 0013)

**Fecha:** 19 de noviembre de 2026. **SOLO DESARROLLO. NO DESPLEGAR.**
Este entregable **no instala un servicio, no concede permisos en producción, no conecta la cola SQLite ni el worker**.

## Alcance exacto

Se incorporan dos scripts:
- `scripts/viewtv_windows_broker_journal_sandbox.ps1`: coordinador de publicación de prueba con **registro durable de intención**, rechazo de segundo movimiento por el mismo staging y conciliación **solo lectura**.
- `scripts/test_viewtv_windows_broker_journal_sandbox.ps1`: crea únicamente carpetas GUID temporales, genera claves efímeras, prepara vídeo/subtítulo ficticios, provoca cortes simulados y comprueba los estados. Elimina solo sus propias carpetas marcadas.

No modifica `scripts/viewtv_windows_publish_sandbox.ps1`, que continúa siendo el único invocador de `[System.IO.Directory]::Move()` en este flujo. Sigue siendo obligatorio ejecutar desde **PowerShell nativo Windows**; no se invoca PowerShell desde WSL.

## Protocolo de prueba, aún no protocolo de producción

1. La firma HMAC de prueba ya existente autoriza sandbox, staging, destino, nonce, vencimiento y lista exacta de archivos con tamaños y SHA-256.
2. El coordinador solo admite `C:\Users\Public\viewtv-win-sandbox-<GUID>` recién creado y marcado. Además exige un diario fuera del montaje Docker bajo `%TEMP%\viewtv-broker-journal-<GUID>`, con marcador y DACL de herencia desactivada. Verifica exactamente tres entradas explícitas: usuario Windows del ensayo, SYSTEM y Administradores; rechaza otras identidades.
3. Antes de calcular hashes de staging, obtiene un bloqueo exclusivo `.viewtv-lock-<id>` en el directorio privado del diario mediante `FileShare.None`, conservando el descriptor abierto hasta terminar. Un segundo proceso que encuentre el bloqueo devuelve `operacion_en_curso` sin leer staging ni intentar mover. Esta protección evita que la propia validación del segundo proceso bloquee el movimiento NTFS del primero. Verifica plan y contenido **dentro de la sección exclusiva**, antes de registrar la operación. Usa un registro derivado del staging, por ejemplo `.viewtv-intent-3.json`, no una ruta escogida libremente.
4. La primera llamada crea el registro con `FileMode.CreateNew`, `FileShare.None`, `FileOptions.WriteThrough` y `Flush(true)`, antes del movimiento. Contiene versión, sandbox, staging, nonce, fecha y SHA-256 de la autorización. No guarda la clave.
5. Solo tras crear el registro llama al publicador de sandbox. Finalizado el movimiento, utiliza el conciliador existente para comprobar los archivos realmente publicados. La respuesta `publicada_verificada` no confirma nada en SQLite.
6. Si ya existe el registro (incluso si otro proceso lo está escribiendo), **NO repite nunca el movimiento**. Responde `reutilizacion_bloqueada` con la observación de solo lectura. Si el registro está vacío, corrupto o no coincide con plan, nonce o sandbox, la observación es `requiere_revision`.
7. Las operaciones de conciliación no crean registros, no publican, no borran staging y no reutilizan aprobaciones caducadas para publicar. Una aprobación antigua solo puede verificar una publicación previa, según las reglas del conciliador.

La reserva exclusiva del diario evita dos movimientos automáticos del **mismo staging** incluso tras reiniciar el script. No hay todavía exclusión duradera global por `download_id`, control de leases ni autoridad Windows independiente. La colisión con otros stagings en el mismo destino sigue dependiendo del rechazo nativo de `Directory.Move`.

## Ensayos ejecutados

La prueba `test_viewtv_windows_broker_journal_sandbox.ps1` realizó **11 escenarios correctos**:

1. Publicación inicial de vídeo y subtítulo con hash coincidente.
2. Repetición del mismo intento: bloqueo, sin segundo movimiento.
3. Corte **simulado** después de persistir intención y antes de mover: staging sigue presente; conciliación `pendiente_de_publicacion`, sin reintento.
4. Corte **simulado** después de `Directory.Move` pero antes de devolver resultado: destino verificado por conciliación, sin repetir.
5. Registro alterado: `requiere_revision`.
6. Destino ya ocupado por otro trabajo: conserva contenido original y staging.
7. Autorización caducada: no crea diario ni publica.
8. Conciliación sin registro previo: `requiere_revision`, sin movimiento.
9. Ruta de diario fuera de `%TEMP%` autorizada: rechazada.
10. Nonce en diario distinto de nonce firmado: `requiere_revision`.
11. Dos procesos PowerShell independientes compiten por el mismo staging: solo una publicación íntegra, la segunda solicitud bloqueada o `operacion_en_curso`. En la primera repetición se detectó una carrera real: un proceso retenía abierto un archivo para SHA-256 y el otro recibía `Access denied` en `Directory.Move`; se corrigió serializando la validación y el movimiento con el bloqueo anterior. Se repitió la prueba concurrente en tres ejecuciones completas posteriores, todas correctas.

La raíz de diario es distinta de la raíz accesible por el contenedor. La DACL de ensayo permite usuario Windows actual, SYSTEM y Administradores: **NO demuestra separación de usuarios**, ya que el firmante/publicador sigue bajo el mismo usuario. El diario de pruebas bajo `%TEMP%` es persistente entre ejecuciones mientras no se elimine; **no garantiza supervivencia ante mantenimiento o limpieza del perfil Windows**.

### Ejecución del ensayo

**PowerShell nativo de Windows** (equipo de desarrollo; no instalar, no elevar):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_broker_journal_sandbox.ps1"
```

**WSL Ubuntu**, solo comprobaciones de Git y suite backend:

```bash
git -C /home/viewtv/projects/viewtv-broker-0013-20261119 diff --check
cd /home/viewtv/projects/viewtv && PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests
```

## Riesgos abiertos — no apto para producción

- **No hay broker residente con identidades/ACL separadas** ni canal Docker↔Windows autenticado de producción; firma y diario están bajo el mismo usuario de prueba.
- **No hay lease 0013 en el permiso de publicar**; debe validarse con SQLite y revalidarse después de I/O bloqueante y justo antes del movimiento. Una firma HMAC por sí sola no demuestra un lease vigente.
- No hay control de replay global por `download_id` ni bloqueo entre varios stagings de un mismo trabajo, ni protocolo de autorización durable independiente. La exclusión de descriptor solo serializa procesos Windows colaboradores del mismo staging; no impide modificaciones por terceros al staging.
- La comprobación SHA-256 antes de mover no cierra todas las carreras **TOCTOU**: aún se requieren descriptores/identidad de fichero protegidos frente a mutaciones y rechazo de renames/reparse points concurrentes.
- `Flush(true)` y `Directory.Move` **no certifican atomicidad ante corte eléctrico, fallos de NTFS, antivirus o hardware**; los cortes de estas pruebas son provocados por excepciones en el proceso, no cortes físicos ni `Stop-Process`.
- No se han probado archivos de tamaño real ni heartbeat durante bloqueos. Sigue el límite de 32 MiB del publicador ficticio y la prohibición de escribir en `C:\VIEWTV\media`.
- Antes de migrar producción `0012→0013`: **respaldo nuevo de SQLite y ensayo de ida/vuelta en copia**, sin despliegue.

**Estado operativo:** producción 0012 sin cambios; `VIEWTV_ENABLE_DOWNLOAD_START=false`, sin tocar qBittorrent, Jellyfin, permisos de bibliotecas ni `worker/main.py`. PR #2 debe seguir en borrador y sin fusionar.
