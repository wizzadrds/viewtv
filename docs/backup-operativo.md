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


## Disponibilidad del portátil (no es un servidor 24/7)

VIEWTV vive en un portátil doméstico con Windows 11, WSL2 y Docker Desktop. El equipo puede apagarse, reiniciarse, suspenderse, hibernar o permanecer sin sesión iniciada. Por tanto, **no se puede garantizar una ejecución exactamente a las 03:00 ni una disponibilidad continua**.

Comportamiento esperado:

- **Encendido y con sesión iniciada:** el Programador de tareas puede lanzar el backup a las 03:00; WSL y Docker Desktop deben estar disponibles.
- **En suspensión:** Windows puede despertar el equipo si están habilitados «Activar el equipo para ejecutar esta tarea» y los temporizadores de activación de energía lo permiten. No es una garantía absoluta; depende del hardware, firmware y plan de energía.
- **Apagado:** la tarea no puede ejecutarse mientras el portátil está apagado. «Ejecutar lo antes posible después de que se omita un inicio programado» permite que Windows intente recuperarla cuando vuelva a estar disponible, pero no enciende por sí sola un equipo apagado.
- **Hibernación:** el despertar depende de que el hardware y la configuración de Windows admitan temporizadores de activación. No asumir que funcionará en todos los equipos.
- **Sin sesión iniciada:** la tarea actual está configurada para ejecutarse solo cuando el usuario haya iniciado sesión; no se ejecutará hasta que exista esa sesión.
- **WSL/Docker Desktop aún arrancando:** el lanzador reintenta durante un periodo limitado. Si Docker no queda disponible, debe fallar y dejar constancia en el log; no debe declarar éxito.

### Política de recuperación y comprobación

1. Mantener el desencadenador diario a las 03:00 (Europe/Madrid) y activar «Ejecutar la tarea lo antes posible si se omitió el inicio programado».
2. No exigir un archivo nuevo cada día natural cuando el portátil estuvo apagado o sin sesión. En su lugar, exigir una copia válida tras la siguiente oportunidad de ejecución.
3. Después de encender el portátil e iniciar sesión, comprobar el log y la fecha del backup más reciente. Si no se recuperó la ejecución omitida, lanzar la tarea manualmente.
4. La tarea solo cuenta como correcta si el archivo final aparece en `C:\\VIEWTV\\backups` y supera `PRAGMA integrity_check`; `LastTaskResult=0` por sí solo no demuestra que haya una copia nueva.
5. No borrar copias antiguas cuando el equipo estuvo desconectado o cuando falla una ejecución. La retención solo se aplica después de generar, transferir y validar correctamente una copia nueva.
6. Para un objetivo de recuperación más estricto, conservar una copia adicional fuera del portátil (por ejemplo, almacenamiento externo desconectado o destino remoto seguro). El backup local no protege frente a robo, avería o pérdida del propio portátil/SSD.

**Criterio realista:** una copia válida cada vez que el portátil esté disponible para ejecutar la tarea, con recuperación tras arranque/inicio de sesión cuando Windows pueda hacerlo; no disponibilidad 24/7.
