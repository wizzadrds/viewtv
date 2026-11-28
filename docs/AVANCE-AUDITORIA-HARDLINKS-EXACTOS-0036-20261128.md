# VIEWTV 0036 — auditoría NTFS de exactamente dos enlaces

**Fecha:** 28/11/2026. Rama `viewtv-seguimiento-descargas-0012`; PR #2 OPEN/DRAFT, no fusionada. **Cambio limitado a la auditoría de solo lectura y una prueba con ficheros TEMP ficticios**; no se modifica el publicador instalado ni se alteran medios, torrents, servicios o ACL reales.

## Defecto detectado después del ensayo 0034

El 0034 demostró que Windows permite crear un **tercer hardlink durante `FileShare.None` o dos handles `DELETE`**. La auditoría global `scripts/viewtv_windows_retirada_auditoria_0016.ps1` tenía una función `Test-SameHardlink` que aceptaba cualquier recuento `>= 2` siempre que origen y copia compartieran File ID. Aunque el inventario integrado `scripts/viewtv_windows_retirada_inventario_0018.ps1` ya exigía exactamente dos enlaces, la auditoría base y las comprobaciones que reutilizan su función podían presentar como verificados pares que tenían otros nombres no inventariados.

## Corrección preventiva

- En `Test-SameHardlink` se cambia **únicamente** el criterio de `links >= 2` por `a.links == 2 && b.links == 2`, manteniendo la coincidencia de File ID, volumen y tamaño. No se añaden funciones de unlink ni modos de escritura.
- Respaldo privado previo de la auditoría 0016 en `/home/viewtv/viewtv-backups/0036-20261128/viewtv_windows_retirada_auditoria_0016.ps1`; SHA-256 `a015ac6627a76d6eeac90b794e30d9511f8a2c93a55230c117ff17f00b62632b`, comprobado contra el original antes de editar.
- `scripts/viewtv_windows_ntfs_exclusividad_sandbox_0034.ps1` introduce un **test negativo específico de la función real `Test-SameHardlink`**, mientras existen tres hardlinks ficticios del mismo File ID en TEMP. Debe rechazarlos antes de limpiar el enlace extra ficticio. `scripts/test_viewtv_windows_ntfs_kernel_0034.ps1` verifica la nueva línea `AUDITORIA_BASE_0016_RECHAZA_TERCERO=PASS` y rechaza discrepancias de salida o código de proceso.

## Verificación real

- Suite 0034 (dos procesos PowerShell y solo ficheros ficticios): **PASS**; `NTFS_0034_DOS_SUITES_SANDBOX=PASS`, `PREPARADO_PARA_BORRADO_REAL=NO`, 0 archivos reales eliminados, 0 torrents modificados.
- Auditoría base 0022 bajo mutex, sobre Windows real **SOLO LECTURA**: `RETIRADA_0022_DIARIOS_NTFS_VERIFICADOS=SI`, `RETIRADA_0022_AUTORIZA_ELIMINACION=NO`, 0 eliminaciones, 0 torrents modificados.
- Preflight integrado 0018 sobre Windows/API **SOLO LECTURA**: 4/4 películas bloqueadas, 2/2 diarios NTFS verificados; permiso de borrado NO, 0 eliminados y 0 torrents modificados. La nueva condición no bloquea falsamente los dos diarios válidos existentes.
- Regresión backend de 0035, ejecutada después del saneamiento Ruff: **1572/1572 PASS**, TypeScript/ESLint PASS, smoke real read-only 10/10 PASS y Ruff global limpio. No se cambia Python en 0036.

## Bloqueos que quedan abiertos

**Esta mejora detecta un tercer enlace cuando se comprueba, pero NO impide su creación futura**. Antes de autorizar una operación se requieren identidad Windows del broker separada, ACL de metadatos que impidan `CreateHardLinkW` a qBittorrent/Jellyfin/usuarios ajenos, pruebas con tokens de SID diferentes, cierre real de acceso directo Jellyfin y de HLS v1, custodia transaccional de un torrent exacto, autorización administrativa real y journal seguro con reconciliación tras apagones. Las cuatro películas siguen sin candidato apto. Este cambio no activa borrados ni despliega nuevas barreras.
