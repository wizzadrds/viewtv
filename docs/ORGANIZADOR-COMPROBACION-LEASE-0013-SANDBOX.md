# VIEWTV — Comprobación de lease para una futura publicación 0013 (sandbox)

**Estado:** SOLO PRUEBAS EN WSL. **NO DESPLEGADO, NO ES UN PERMISO DE PUBLICACIÓN NI UN SERVICIO WINDOWS.**
Fecha: 19 de noviembre de 2026.

## Problema que aborda

Una aprobación HMAC vinculada al staging podría seguir siendo válida cuando
el lease de organización de SQLite ya ha caducado, ha cambiado de dueño o
ha sido reclamado **de nuevo por el mismo worker**. Por ello la firma o el
estado HTTP del broker no demuestran que esté autorizado publicar.

El nuevo módulo `backend/app/organization_publication_gate_sandbox.py`
ofrece una **consulta puntual y de solo lectura** de la fila `descarga`
en una SQLite **ficticia** de versión de desarrollo 0013. No reclama,
renueva, confirma ni cambia la cola, ni escribe en NTFS o en medios reales.

## Política comprobada

La decisión solo es positiva cuando **todas** estas condiciones coinciden:

- `download_id` entero positivo y `worker_id` no vacío (máximo 128 caracteres).
- `expected_attempt` entero de 1 a 3 que coincide exactamente con `organizacion_intentos`. Esto protege contra el problema **ABA**: el mismo worker puede recuperar la tarea con un contador nuevo, pero una intención antigua permanece obsoleta.
- Hash de torrent esperado SHA-1 (40 hex) o SHA-256 (64 hex), en minúsculas, que coincide con `qbittorrent_hash`. Es comparación con SQLite, **NO verificación de identidad en vivo contra qBittorrent**.
- `estado=completada`, `progreso=1`, `estado_verificacion=verificada`, fecha `verificada_en` no nula y `organizacion_estado=pendiente`.
- `organizacion_locked_by` igual al worker; `organizacion_locked_until` estrictamente **posterior** al instante de consulta. En el formato SQLite existente, timestamps sin zona se interpretan como UTC.

Toda identidad inválida, fila ausente, marcador incorrecto, esquema ilegible, lease vencido o discrepancia **deniega**. El resultado es solo `allowed` y un código controlado; no revela rutas, PIN ni credenciales.

## Barrera de seguridad del ensayo

- La función requiere `Path('/tmp/viewtv-lease-gate-<GUID>/organization.sqlite3')` con marcador `.viewtv-lease-gate-sandbox-only` cuyo texto exacto es `VIEWTV_LEASE_GATE_SANDBOX_V1`.
- La raíz debe ser hija directa de `/tmp`, con nombre de 32 dígitos hex, sin symlink; el archivo SQLite no puede ser un symlink ni hardlink adicional. Quedan excluidos `/media`, rutas de producción, rutas Windows y bases importadas por `app.database`.
- Abre una **conexión nueva SQLite `mode=ro`** y activa `PRAGMA query_only=ON`; no usa el motor de producción ni importa `worker/main.py`.
- Cada comprobación refleja datos confirmados **en ese instante**. No emite una autorización firmada, token durable o lease exclusivo; entre la lectura y `Directory.Move` podría perderse el lease.

## Pruebas automatizadas

`backend/tests/test_organization_publication_gate_sandbox.py` comprueba:
1. Lease vigente y bytes SQLite intactos después de la consulta.
2. Rechazo de otro worker, otro intento, hash distinto y fila ausente.
3. Vencimiento estricto al segundo 180 y después.
4. Reclamación **del mismo worker** tras caducar: falla el intento antiguo, pasa el nuevo.
5. Cambios de descarga, progreso, verificación, fecha, organización, propietario, torrent e intentos.
6. Entradas mal formadas, marcador alterado, ruta ajena, symlink y SQLite corrupta.
7. Fecha de vencimiento ilegible: denegación.

Todas las pruebas crean su propia raíz aleatoria bajo `/tmp`, con SQLite y perfil ficticios; se eliminan únicamente los ficheros del ensayo. Los tests no consultan torrents, bibliotecas ni base de producción.

### Comandos de validación (WSL Ubuntu)

```bash
cd /home/viewtv/projects/viewtv-broker-0013-20261119
PYTHONPATH=backend:. /home/viewtv/projects/viewtv/backend/.venv/bin/python -m pytest -q backend/tests/test_organization_publication_gate_sandbox.py
PYTHONPATH=backend:. /home/viewtv/projects/viewtv/backend/.venv/bin/python -m pytest -q backend/tests
/home/viewtv/projects/viewtv/backend/.venv/bin/ruff check backend/app/organization_publication_gate_sandbox.py backend/tests/test_organization_publication_gate_sandbox.py
```

## Imprescindible antes de conectar Windows

1. Una **autoridad separada** del worker deberá revalidar esta decisión en una SQLite confiable, sin admitir rutas de base aportadas por Docker. No basta con que Docker entregue un JSON que afirme `allowed=true`.
2. Vincular `download_id`, número de intento, propietario, hash y **manifiesto/staging/destino** a un registro durable firmado por esa autoridad y a un protocolo local de autenticación mutua y control de replay.
3. El broker Windows debe verificar vigencia **justo antes de mover**, tras esperas/bloqueos, y reconciliar de manera conservadora si falla después. El guard actual **no participa todavía en `scripts/viewtv_windows_broker_journal_sandbox.ps1`**.
4. Probar denegación por otra cuenta Windows de privilegios mínimos, TOCTOU, bloqueo largo, tamaño real, lease perdido mientras se copia, caída abrupta y recuperación del diario.
5. Ningún despliegue 0013 hasta respaldo fresco y ensayo `0012→0013→0012` sobre una copia verificada.

**Estado de producción:** VIEWTV sigue en 0012; `VIEWTV_ENABLE_DOWNLOAD_START=false`. Este avance no ha tocado `C:\VIEWTV\media`, qBittorrent ni Jellyfin.

## Resultados verificados en el equipo

- **29 pruebas específicas correctas**, incluida sustitución del nombre exacto de SQLite por un symlink y rechazo sin abrir el objetivo.
- **517 pruebas del backend correctas**, con dos avisos de deprecación preexistentes.
- Ruff `check` correcto en ambos archivos Python nuevos.
- No quedó ningún directorio `/tmp/viewtv-lease-gate-*` tras finalizar las pruebas. Una primera versión del test de marcador había dejado una carpeta propia con marcador alterado: se identificó, se inspeccionó y se eliminó **solo ese sandbox generado por la prueba**; la prueba ahora restaura el marcador en `finally`.
- No se ha modificado `worker/main.py`, ningún archivo versionado anterior ni la base SQLite real.
