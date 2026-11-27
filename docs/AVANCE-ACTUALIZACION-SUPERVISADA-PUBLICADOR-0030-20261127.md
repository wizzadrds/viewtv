# VIEWTV 0030 — Actualización supervisada del publicador Windows (cierre operativo de 0023)

**Fecha:** 27/11/2026, Europe/Madrid. **Rama exclusiva:** `viewtv-seguimiento-descargas-0012`. **PR #2:** abierto y en borrador; no fusionar. **Equipo de verificación:** LAPTOP-V2QSMC01, instalación Windows real. No confundir este despliegue con el laboratorio 0022/0023.

## Resultado productivo, con límites

**Instalado y operativo:** el publicador Windows antiguo se reemplazó, con `[IO.File]::Replace` y copia verificada, por el mismo fichero de la rama que adquiere el mutex 0022 antes de reclamar, publicar o reconciliar. El helper `viewtv_windows_media_lock_0022.ps1` se instaló junto al script y ambos tienen las huellas aprobadas. El wrapper periódico no se cambió. La tarea programada quedó **reactivada**, con `RunLevel=Limited`, `LogonType=Interactive`, una ejecución `-Mode Once` por activación, límite configurado de cuatro minutos y sin servicio Windows permanente. Su cuenta pertenece al grupo de administradores local, pero la tarea se ejecuta sin elevación; no confundir pertenencia con token elevado.

**No instalado:** ninguna barrera ASGI 0028/0029, ninguna firma HLS vinculada a perfil/sesión/generación, ninguna barrera de acceso directo Jellyfin o escrituras qBittorrent/lectores NTFS, ninguna identidad administrativa 0019. El mutex es cooperativo: el nuevo publicador participa, pero Jellyfin y qBittorrent no. **No concede permiso de borrar.**

## Comprobaciones antes de tocar producción

Se verificaron tarea, configuración, proceso, servicio, ACL y archivos, comparando las huellas de ambos lados. Inicialmente `State=Ready`, último resultado de tarea 0, `RunLevel=Limited`, `LogonType=Interactive`, wrapper `-Mode Once`; servicio SCM ausente y ningún publicador activo observado. En el momento de la intervención no había staging `.viewtv-publicando-*`, ni procesos PowerShell sin línea de órdenes visible.

| Elemento | SHA-256 |
| --- | --- |
| Publicador antiguo instalado | `9533A16D2031F89ADFF414C1A9E226BCD503C6357B7105978113403E573F9611` |
| Publicador nuevo de la rama/instalado | `49765CF442D6084588F6BAF7B061BE4A29AD8DFFFA379B22681AECE17441993C` |
| Helper mutex 0022 nuevo de la rama/instalado | `C1DBE8C78D53DBFDE75F50E2CE97A9A0FC0E2F55A3156952196DCA445B29A6C8` |
| Wrapper no modificado | `ECAF1AFAF471228A13DF9650039B661F9B6AC26C36EE577FC35DBB397301CE2F` |

El helper anterior **no existía**: se registró y verificó esa ausencia en vez de inventar una copia. ACL de `C:\VIEWTV\publicador`, `bin` y `journal`: protegidas, con acceso únicamente para SYSTEM, Administradores y usuario local autorizado. Se comprobaron huellas y ACL de los ficheros tras la sustitución.

## Respaldo privado y recuperación independiente

Directorio privado **solo Windows, fuera de Git**:
`C:\VIEWTV\publicador\respaldo-0030-20261127-230828-9de04136`.

Contiene el script original, wrapper, XML de la tarea, manifiesto de versiones y ACL, copia automática de `File.Replace`, y guiones `install-0030.ps1` y `rollback-0030.ps1`. Manifiesto SHA-256 inmediatamente tras crearse: `C6B2E7C1CC5434CAC2743DCA781EBA8A37A1F284499663E5A1C85316552BA741`. Copia original de publicador y wrapper comparada con la instalada por SHA-256 antes del cambio. **No trasladar este respaldo a Git.** Los guiones empleados se conservaron asimismo como fuentes auditables bajo `scripts/viewtv_windows_publicador_upgrade_supervised_0030.ps1` y `scripts/viewtv_windows_publicador_rollback_0030.ps1`, con hashes idénticos a los guiones usados en Windows. Son específicos para este equipo y manifiesto, no un instalador genérico.

El rollback se **probó desde un proceso PowerShell independiente**, sobre versiones copiadas a un sandbox privado, con `File.Replace` y verificación de SHA-256 antes/después:
`ROLLBACK_0030_PROCESO_INDEPENDIENTE=PASS`, `ROLLBACK_0030_FILE_REPLACE_Y_HASHES=PASS`, `PRODUCCION_MODIFICADA=NO`. **No se ejercitó rollback destructivo en producción** después de instalar la versión buena. El modo `Restore` comprueba la tarea deshabilitada y ambos hashes, restaura solo el script y retira solo el helper exacto; deja tarea deshabilitada para revisión, sin tocar medios.

## Ventana de mantenimiento y recuperación

1. Tras comprobar el respaldo, se ejecutó `Disable-ScheduledTask` y se verificó `State=Disabled`.
2. Se repitió dos veces una lectura real del estado, con 6 segundos de separación: **0** procesos publicador, **0** procesos PowerShell no inspeccionables, **0** staging, **0** servicio y tarea `Disabled` en las dos lecturas.
3. Se preparó la pareja en archivos provisionales en el mismo directorio protegido; se contrastaron SHA-256 y ACL. Se escribió un diario de intención `CreateNew` + `WriteThrough` + `Flush(true)`. Se reemplazó el script con `File.Replace` (backup explícito), se movió el helper y se volvió a verificar versión y ACL. El diario registra fase completa. Ante fallo, el instalador invoca el rollback en otro proceso manteniendo tarea deshabilitada.
4. Preflight **del fichero instalado real**: `PREFLIGHT_PUBLICADOR_WINDOWS_0013_OK`. Inventario 0023 posterior: script coincidente `SI`, helper instalado y coincidente `SI`, wrapper `SI`, tarea Limited `SI`, sin servicio ni procesos, estado `Disabled`.
5. Solo entonces se ejecutó `Enable-ScheduledTask`: `Ready`, `Limited`, `Interactive`, mismos hashes. `Start-ScheduledTask` comprobó una pasada real `Once` el 27/11/2026 a las 23:11:47 hora de Madrid; último resultado **0**, tarea otra vez `Ready`, estado privado `correcto`, publicación `sin_trabajos`, catálogo `sincronizado`, marca del fichero de estado `2026-11-27T22:11:54Z`. **No se publicó película nueva ni se creó un servicio permanente.**

El auditor 0023 tiene una advertencia de texto fija `PUEDE_AFIRMARSE_EXCLUSION_PRODUCTIVA=NO`; esa herramienta nunca atribuye exclusión a una instantánea y no debe citarse como test de participación. La integración se avala por hashes de la pareja realmente instalada y la ejecución `Once`. La exclusión no alcanza procesos no cooperativos.

## Auditoría real posterior, exclusivamente lectura

- NTFS 0016: `DIARIOS_ENCONTRADOS=2`; `DIARIOS_VERIFICADOS_POR_HARDLINK=2`; `DIARIOS_BLOQUEADOS=0`; `FICHEROS_PUBLICADOS_VERIFICADOS=2`; **1 carpeta sin diario verificable, excluida**; `BORRADOS_PRODUCCION=0`.
- Preflight integrado 0018: `PELICULAS_ANALIZADAS=4`; `DIARIOS_NTFS_VERIFICADOS=2`; `DIARIOS_VERIFICADOS_EN_SNAPSHOT=2`; **`PELICULAS_BLOQUEADAS=4`**; `PERMISO_DE_BORRADO_OTORGADO=NO`; `ARCHIVOS_ELIMINADOS=0`; `TORRENTS_MODIFICADOS=0`. Los medios 2, 3, 4 y 5 siguen bloqueados. Faltan 4 aprobaciones administrativas, 4 marcas de vista completas; 2 torrents no están en reposo; otros bloqueos persisten.
- El mutex de retirada 0022 se pudo adquirir para ejecutar una auditoría NTFS real sin borrar. El script de auditoría antiguo conserva una etiqueta estática `PUBLICADOR_PRODUCCION_INTEGRADO=NO_VERIFICADO` y no reemplaza la comprobación de hashes hecha arriba.
- Los cuatro metadatos adicionales de qBittorrent y la carpeta sin diario quedan fuera de cualquier retirada. No se modificó caché de Jellyfin, originales NTFS ni torrents.

## Pruebas de calidad y reserva explícita

- **Backend completo: 1528/1528 PASS**, dos advertencias ajenas de dependencias; Docker de pruebas sin red, código montado en modo lectura.
- **TypeScript: PASS** (`tsc --noEmit --incremental false`).
- **ESLint: PASS** tras corregir solo la anotación de que `frontend/scripts/generate-release.cjs` utiliza CommonJS; se respaldó previamente el archivo y no se cambió su lógica.
- **Smoke: 10/10 PASS**, comprobaciones GET/401; son complemento, no sustituyen pruebas de tarea y NTFS.
- **Ruff 0023 específico: PASS** en `worker/publication_upgrade_gate_0023.py` y `scripts/viewtv_publicador_upgrade_preflight_0023.py`; se eliminó una anotación `noqa` redundante tras copiar y verificar el original. El **Ruff global de `backend worker scripts` NO PASÓ**: encontró fallos heredados en migraciones, tests y guiones antiguos ajenos al 0030. No se han saneado ni se declara Ruff global verde; evitar barrer esos ficheros sin una intervención propia. La ejecución inicial de Ruff global también detectó que había que usar `--no-cache` con el volumen montado en solo lectura; repetida con ese parámetro, obtuvo los fallos heredados.

**Cierre real:** actualización operativa Windows 0030 instalada y auditada; pruebas completas backend, frontend y smoke en verde; **reserva de calidad sobre Ruff global preexistente**. No considerar esa reserva como prueba de que todo el repositorio pasa Ruff. No habilitar borrados hasta superar hitos 2, 3, 4 y aprobación por película. El trabajo de implementación del hito 2/3 **no se ha iniciado**. Sus diseños y casos de prueba pendientes se documentan aparte, sin despliegue.
