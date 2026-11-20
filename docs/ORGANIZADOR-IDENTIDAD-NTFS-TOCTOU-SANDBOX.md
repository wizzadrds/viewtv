# VIEWTV 0013 — Identidad NTFS vinculada a la autorización (sandbox)

**Fecha:** 20-11-2026. **SOLO DESARROLLO. NO DESPLEGADO, NO CIERRA TODAVÍA TOCTOU.**

## Hallazgo medido en Windows 11

En `C:\Users\Public\viewtv-win-sandbox-<GUID>`, una carpeta de pruebas NTFS que
contenía un archivo abierto mediante `FileStream` **no pudo moverse con
`[IO.Directory]::Move()`**, incluso cuando la apertura permitía
`FileShare.Read | FileShare.Delete`. Se ensayaron también
`FileShare.Read`, `FileShare.None` y `FileShare.ReadWrite | FileShare.Delete`;
ninguno permitió mover la carpeta mientras el archivo estaba abierto.

**Conclusión:** mantener abiertos descriptores para impedir escrituras hasta
después del movimiento **no es compatible con la publicación nativa ensayada**.
No presentar esa técnica como cierre de TOCTOU. El sistema definitivo
necesita un broker con cuenta Windows independiente, ACL de staging
separadas del contenedor y control de acceso efectivo durante el traslado.

## Mejora aplicada en el prototipo de sandbox

- `scripts/viewtv_windows_stage_identity_sandbox.ps1` incorpora un
  ayudante Win32 `CreateFileW` + `GetFileInformationByHandle` mediante
  PowerShell `Add-Type`. Obtiene `VolumeSerialNumber` y los dos campos
  `FileIndex` de **la carpeta y de cada archivo**. Rechaza reparse points,
  subdirectorios y archivos con número de hardlinks distinto de **1**.
- `scripts/viewtv_windows_approval_sandbox.ps1` incorpora al contenido
  **firmado** del HMAC un campo obligatorio `stage_identity` con esas
  identidades. Al verificar, recalcula la identidad del staging o del
  destino ya publicado. `Directory.Move` conserva esos identificadores
  dentro del mismo volumen NTFS. **Una sustitución por un archivo nuevo,
  aunque tenga el mismo nombre y SHA-256, ya no coincide con la firma.**
- `scripts/viewtv_windows_publish_sandbox.ps1` toma una instantánea de
  identidad **antes** de comprobar hashes y autorización, y vuelve a leerla
  inmediatamente antes de mover. Si cambió, aborta, deja staging intacto
  cuando todavía existe y exige revisión sin reintento automático.
- Si Windows no puede recuperar la identidad nativa, el ayudante **falla
  cerrado**; no interpreta una lectura incompleta como permiso de publicación.
- Las aprobaciones antiguas sin `stage_identity` **dejan de ser aceptadas
  por este prototipo** y requieren inspección manual. No se migran ni
  reescriben autorizaciones preexistentes.
- El límite anterior de **8 KiB** de la autorización serializada resultó
  insuficiente para el máximo permitido de veinte ficheros de nombres largos.
  El verificador HMAC y el lector del diario tienen ahora un límite explícito
  de **32 KiB**, manteniendo las restricciones por archivo, nombre y cantidad.
  La primera prueba de ese máximo falló en modo conservador; al ajustar el
  límite, se publicó el grupo completo únicamente en el sandbox.

## Pruebas nuevas

`scripts/test_viewtv_windows_stage_identity_sandbox.ps1` crea solamente
una raíz marcada GUID de prueba en `C:\Users\Public` y comprueba:

1. Identidad estable en dos lecturas consecutivas.
2. Sustitución de un archivo con **bytes/SHA-256 idénticos** detectada por el
   cambio de FileIndex.
3. Hardlink adicional fuera del staging rechazado por el contador de enlaces.
4. Junction NTFS como carpeta staging rechazada por `ReparsePoint`.
5. Imposibilidad de mover con un descriptor del archivo todavía abierto.
6. Rechazo efectivo **del publicador firmado** cuando el archivo original
   se sustituye por otro con SHA-256 idéntico entre firma y publicación;
   staging y destino no son alterados.
7. Publicación íntegra de un vídeo y **19 subtítulos**, con nombres largos,
   hashes e identidades NTFS validados antes y después del movimiento.

`scripts/probe_viewtv_stage_handle_sandbox.ps1` conserva el ensayo
exploratorio de cuatro modos `FileShare`. Ambos crean raíces aleatorias,
nunca `C:\VIEWTV\media`, y retiran solo sus propias carpetas marcadas
y claves efímeras. Se comprobó explícitamente la retirada de junctions
**sin seguir el enlace**; el primer intento de prueba dejó una carpeta
GUID propia vacía tras el error de limpieza, que se inspeccionó y se
retiró únicamente después de verificar que no contenía nada.

### Cómo repetir (PowerShell nativo de Windows)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_stage_identity_sandbox.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_publish_sandbox.ps1"
```

Comprobaciones del repositorio desde **WSL Ubuntu**:

```bash
cd /home/viewtv/projects/viewtv-broker-0013-20261119
git diff --check
PYTHONPATH=backend:. /home/viewtv/projects/viewtv/backend/.venv/bin/python -m pytest -q backend/tests
```

## Riesgos que permanecen abiertos

**No se ha cerrado la carrera TOCTOU.** Las comprobaciones de identidad son
observaciones puntuales; tras cerrar los descriptores y antes de
`Directory.Move` otra identidad con permisos suficientes podría escribir,
renombrar o reemplazar el staging. La verificación posterior detectaría
una discrepancia, **pero no impediría por sí sola una exposición temporal**.
El script no usa una transacción conjunta NTFS/SQLite ni mantiene permisos
exclusivos sobre staging. Tampoco hay identidades Windows separadas,
autoridad de aprobación independiente, heartbeat para ficheros grandes ni
protección integral frente a antivirus y cortes de alimentación.

**Bloqueo obligatorio antes de producción:** comprobar bajo cuentas distintas
que Docker/copia no pueda mutar staging cuando el broker ya ha validado; el
broker deberá ser el único con derecho a mover a una raíz permitida, revalidar
lease y manifiesto justo antes de la operación y mantener diario duradero.
No habilitar `worker/main.py` ni `VIEWTV_ENABLE_DOWNLOAD_START`.

No se consultaron torrents ni se cambiaron rutas, datos, permisos o servicios
de producción. Todas las pruebas permanecen deliberadamente limitadas al
publicador ficticio con máximo 32 MiB por archivo.

## Validación final del bloque

Ejecutado en el equipo Windows 11 con PowerShell 5.1 y WSL Ubuntu:

- **7 escenarios nuevos** del test de identidad NTFS correctos.
- **4 variantes de `FileShare`** del ensayo exploratorio correctas: ningún
  descriptor abierto permitió el movimiento de carpeta.
- **20 casos** del publicador/reconciliador Windows correctos.
- **11 casos** del diario de intención, recuperación y carrera correctos.
- Prueba ACL Windows correcta; **6 pruebas** Docker→Windows correctas.
- **12 escenarios** del puente de lectura de leases Windows→WSL correctos.
- Backend (sin modificación en este hito): **517 pruebas aprobadas** y dos
  advertencias de deprecación conocidas.
- Se comprobó que no quedan carpetas GUID de pruebas, diarios ni claves
  efímeras tras las ejecuciones finales.

No se han realizado cortes físicos, pruebas con dos cuentas Windows
separadas ni operaciones sobre archivos multimedia de tamaño real.
**Ningún resultado de estos ensayos autoriza despliegue.**
