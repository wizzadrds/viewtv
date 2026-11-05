# VIEWTV — procedimiento operativo de backup (actualizado el 5 de noviembre de 2026)

## Estado de las copias recuperadas

El 5 de noviembre se ejecutó manualmente la tarea de Windows. El script original informó de dos copias en `/backups` dentro del contenedor API:

- `viewtv-20261105-131312.db`
- `viewtv-20261105-131424.db`

El bind mount declarado por Docker como `/mnt/c/VIEWTV/backups:/backups` no reflejaba los archivos escritos por el contenedor en WSL/Windows. Las pruebas bidireccionales demostraron que los archivos creados dentro de `/backups` solo eran visibles en el contenedor; los archivos creados desde WSL sí aparecían en Windows. `df -h /backups` también mostraba un filesystem de 7,7 GB, no el SSD anfitrión.

Las dos copias se recuperaron mediante una tubería de `tar` desde el contenedor al SSD y se verificaron directamente en `C:\\VIEWTV\\backups`:

| Archivo | Integridad SQLite | Perfiles | Alembic |
| --- | --- | ---: | --- |
| `viewtv-20261105-131312.db` | `ok` | 2 | `0001_initial` |
| `viewtv-20261105-131424.db` | `ok` | 2 | `0001_initial` |

No se modificó la base de datos activa `/data/viewtv.db` ni el volumen `viewtv_viewtv_data`. Las copias anteriores del 4 de noviembre permanecen intactas.

## Corrección implementada en el repositorio

- `scripts/backup-daily.sh` genera el backup en `/tmp/viewtv-backups` dentro del contenedor mediante SQLite Online Backup API.
- El script identifica el nombre generado, transmite los bytes explícitamente por stdout hacia una carpeta temporal en `/mnt/c/VIEWTV/backups`, y valida allí `PRAGMA integrity_check`, el número de perfiles y la versión Alembic.
- Solo después de validar la copia transferida la publica en `/mnt/c/VIEWTV/backups`.
- La retención se aplica en el SSD anfitrión, después de publicar correctamente una copia nueva, y solo a archivos `viewtv-*.db` con más días que `BACKUP_RETENTION_DAYS`.
- `compose.yaml` deja de montar la carpeta de Windows como `/backups` dentro del API; `BACKUP_DIR` pasa a `/tmp/viewtv-backups`. El volumen SQLite `viewtv_viewtv_data` y el montaje de caché no cambian.
- El lanzador Windows `scripts/backup-daily.ps1` conserva su llamada a WSL y su registro en `C:\\VIEWTV\\logs\\backup-daily.log`.

## Aplicación y prueba pendientes en el equipo

La corrección está publicada en la rama `feature/fase-1-backend-base`, pero debe actualizarse y probarse en el equipo antes de confiar de nuevo en la tarea diaria.

En Ubuntu/WSL:

```bash
cd ~/projects/viewtv
git pull --ff-only
bash -n scripts/backup-daily.sh
docker compose config --quiet
docker compose up -d --build api
docker compose ps
```

Después, en PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\\VIEWTV\\scripts\\backup-daily.ps1"
```

El archivo `C:\\VIEWTV\\scripts\\backup-daily.ps1` ya existente puede seguir usándose: invoca el script Bash desde WSL, que es el que se actualiza con Git.

La prueba solo se considera correcta si el log confirma la validación en SSD y aparece un archivo nuevo en Windows:

```powershell
Get-ChildItem "C:\\VIEWTV\\backups" -Filter "viewtv-*.db" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 3 Name, Length, LastWriteTime
```

Luego comprobar desde WSL el archivo más reciente con `python3` y SQLite, y comprobar `LastTaskResult=0`. La siguiente ejecución diaria programada (03:00, hora de Madrid) también debe dejar un archivo nuevo. Hasta superar la prueba manual con el script corregido y una ejecución programada real, el backup diario no se considera validado de forma continuada.

## Precauciones

- No ejecutar `docker compose down -v`, no borrar volúmenes y no eliminar `viewtv_viewtv_data`.
- No copiar directamente `/data/viewtv.db` mientras SQLite está en uso; usar siempre la Online Backup API.
- No considerar éxito solo porque el comando dentro del contenedor imprimió «Backup verificado»: la copia debe existir y superar la comprobación SQLite en `C:\\VIEWTV\\backups`.
- Mantener una copia adicional fuera del portátil para recuperación ante fallo del SSD.
