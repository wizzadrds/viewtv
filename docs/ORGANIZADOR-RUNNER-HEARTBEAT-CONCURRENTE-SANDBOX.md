# VIEWTV 0013 — Heartbeat concurrente integrado en el ejecutor de sandbox

**Fecha:** 20-11-2026. **SOLO DESARROLLO: no desplegar, no usar medios reales.**

## Objetivo y frontera de seguridad

Antes, `run_one_sandbox_organization` renovaba el lease en callbacks de
progreso. Si la consulta al proveedor o una escritura quedaba bloqueada,
no se emitían pulsos de renovación. El módulo
`IndependentOrganizationHeartbeat` ya se había probado por separado,
pero no se utilizaba desde el ejecutor.

Ahora el ejecutor admite un modo explícito y **opcional**:

```python
run_one_sandbox_organization(
    engine, root, "worker-ficticio", fake_source_provider,
    independent_heartbeat=True, heartbeat_interval_seconds=0.02,
)
```

El comportamiento anterior sigue siendo el predeterminado para conservar
las pruebas históricas. **No** se ha importado ni activado en
`worker/main.py`. No se ha conectado a Docker de producción, qBittorrent
real ni a la publicación nativa de Windows.

## Funcionamiento del modo concurrente

1. `_check_sandbox(root)` exige que el directorio sea hijo de `/tmp`,
   con marcador exacto `.viewtv-organization-test-only`.
   Antes de reclamar una descarga se valida el modo, intervalo y la
   correspondencia exacta de engine SQLite con
   `<root>/test-organization.db`.
2. La cola reclama una descarga con su **número de intento**. Se crea
   `IndependentOrganizationHeartbeat` con propietario, ID y
   `organizacion_intentos`, validando de nuevo la SQLite marcada. Además de
   las bases `/tmp/viewtv-lease-gate-<GUID>/organization.sqlite3`
   existentes en las pruebas, el heartbeat admite **solamente**
   `test-organization.db` dentro de un sandbox de organización marcado.
   Comprueba marcador, archivo regular y contador de hardlinks.
3. `start()` renueva inicialmente en la sesión principal y luego crea
   un hilo que pulsa sobre **otras sesiones SQLite**. La lectura del
   trabajo se cierra antes de llamar al proveedor o al copiador: una
   lectura abierta no debe bloquear el hilo que intenta renovar.
4. Los callbacks del copiador pasan a ser **verificaciones de vigencia**:
   comprueban el hilo y renuevan de forma segura; el hilo sigue pulsando
   por sí solo aunque el callback no se ejecute durante una espera larga.
5. Si cambia propietario, número de intento, verificación o estado de la
   cola, cualquier error del heartbeat se considera `lease_perdido`.
   No se confirma organización. El staging incompleto se conserva y el
   destino no se publica en los escenarios ensayados.
6. Tras publicar, el ejecutor vuelve a verificar el lease, **detiene y
   espera** el hilo y solo entonces intenta la confirmación SQL con el
   número exacto de intento. Existe una carrera entre esta comprobación
   y la escritura SQL, cerrada parcialmente por
   `confirm_organization(..., expected_attempt=intento)` y
   `UPDATE` condicionado. El `finally` detiene el hilo también ante
   excepción o fallo del proveedor.

## Pruebas de integración

`backend/tests/test_organization_runner_sandbox.py` añade casos de:

- Proveedor ficticio que tarda sin invocar callbacks: el vencimiento
  almacenado se extiende durante la espera y se completa la organización.
- Escritura del copiador ficticio bloqueada: el lease se sigue
  renovando desde el hilo independiente mientras no hay callbacks.
- Pérdida de propietario a mitad de escritura: staging permanece para
  revisión, no se publica ni confirma.
- Aparición de un intento nuevo con el **mismo worker_id** durante la
  escritura: el intento antiguo no publica ni confirma.
- Excepción de proveedor: se detiene el hilo y la base conserva el estado
  pendiente.
- SQLite ajena al sandbox e intervalo inválido: rechazo **antes de
  reclamar**, sin incrementar el contador de intentos.

Las pruebas existentes de runner/copia/cola siguen funcionando con modo
predeterminado. También se conservan las pruebas anteriores del heartbeat
con **128 MiB** ficticios en WSL. La copia de 128 MiB es una prueba de
renovación concurrente de ficheros sintéticos; **no** prueba una película
de tamaño real atravesando Docker/NTFS.

### Cómo repetir las pruebas (WSL Ubuntu)

```bash
cd /home/viewtv/projects/viewtv-broker-0013-20261119
PYTHONPATH=backend:. /home/viewtv/projects/viewtv/backend/.venv/bin/python -m pytest -q backend/tests/test_organization_runner_sandbox.py backend/tests/test_organization_lease_heartbeat_sandbox.py
PYTHONPATH=backend:. /home/viewtv/projects/viewtv/backend/.venv/bin/python -m pytest -q backend/tests
/home/viewtv/projects/viewtv/backend/.venv/bin/ruff check worker/organization_runner_sandbox.py worker/organization_lease_heartbeat_sandbox.py backend/tests/test_organization_runner_sandbox.py
```

No se requiere **PowerShell Windows** para estas pruebas de WSL; ni se
modifican servicios o volúmenes reales. El usuario Windows conserva los
permisos anteriores: esta integración no crea ni usa cuentas de servicio.

## Limitaciones que impiden producción

- **No existe todavía un broker Windows con identidad mínima independiente,
  ACL realmente separadas y canal autenticado**. El puente Windows→WSL
  anterior es una prueba, no autenticación de producción.
- Un hilo no puede interrumpir una llamada NTFS/DrvFS bloqueada; podrá
  señalar la pérdida del lease, pero solo cuando el hilo ejecutor retorne
  podrá detenerse antes de la publicación. No basta para cerrar TOCTOU.
- Un `Directory.Move` de NTFS y una escritura SQLite no comparten
  transacción. Recuperación ante cortes físicos, replay entre intentos,
  leasing de autoridad independiente y conciliación durable siguen
  pendientes.
- El copiador Linux de sandbox mantiene un límite **32 MiB por archivo**;
  no se ha integrado la publicación de varios GiB ni un grupo de
  subtítulos en temporada preexistente.
- Migración a 0013 requiere **backup nuevo de SQLite** y ensayo
  `0012→0013→0012` sobre copia antes de plantear despliegue.

**Estado de producción:** VIEWTV 0012, sin modificar
`VIEWTV_ENABLE_DOWNLOAD_START=false`, `C:\VIEWTV\media`,
qBittorrent, Jellyfin ni SQLite real. PR #2 debe seguir en borrador.

## Resultados del equipo

- **45 pruebas específicas** de ejecutor de sandbox y heartbeat aprobadas.
- **545 pruebas del backend aprobadas**, con dos advertencias de
  deprecación ya conocidas; no hubo fallos.
- **12 escenarios Windows→WSL correctos**, sin cambios en el flujo de
  publicación existente.
- Ruff correcto en los tres archivos Python tratados por el bloque.
- Se ejecutaron esperas sintéticas de unos 200 ms sin callbacks, revocaciones
  y cambios de número de intento durante una escritura ficticia.
- Los casos de lease perdido no crearon carpeta final; conservaron el
  staging y no confirmaron SQLite. La copia independiente previa de 128 MiB
  sigue siendo una prueba aparte: **no se ha efectuado aquí una publicación
  Windows de gran tamaño**.
- Se comprobó el directorio Git aislado y no se observaron errores de diff.
  El backup de los archivos anteriores se creó antes de modificarlos.

**No se demostró una pausa real superior a 180 s**, pérdida eléctrica ni
parada violenta de proceso; el heartbeat debe probarse con bloqueos de I/O
realistas y un broker Windows de privilegios mínimos antes de producción.
