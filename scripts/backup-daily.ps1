# VIEWTV — copia diaria desde el Programador de tareas de Windows
$ErrorActionPreference = "Stop"

$Distro = "Ubuntu-24.04"
$WslUser = "viewtv"
$LogDir = "C:\VIEWTV\logs"
$LogFile = Join-Path $LogDir "backup-daily.log"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
Start-Transcript -Path $LogFile -Append | Out-Null

try {
    $LinuxCommand = @'
set -e
cd "$HOME/projects/viewtv"

# Asegura que la API esté levantada. Compose puede tardar si Docker Desktop
# acaba de iniciar; el bucle posterior espera a que /health responda.
docker compose up -d api

for attempt in $(seq 1 60); do
    if curl --fail --silent --show-error http://127.0.0.1:8000/health >/dev/null 2>&1; then
        docker compose exec -T api sh -c 'cd /opt/viewtv/backend && python scripts/backup_db.py'
        exit $?
    fi
    sleep 5
done

echo "ERROR: la API no respondió correctamente en 5 minutos." >&2
exit 1
'@

    # Reintenta si WSL/Docker Desktop todavía no están disponibles al iniciar Windows.
    for ($attempt = 1; $attempt -le 10; $attempt++) {
        Write-Output "Intento $attempt de 10: iniciando backup VIEWTV."
        & wsl.exe -d $Distro -u $WslUser -- bash -lc $LinuxCommand
        if ($LASTEXITCODE -eq 0) {
            Write-Output "Backup VIEWTV completado correctamente."
            exit 0
        }

        Write-Warning "WSL/Docker/backup devolvió código $LASTEXITCODE."
        if ($attempt -lt 10) {
            Start-Sleep -Seconds 60
        }
    }

    throw "No se pudo completar el backup tras 10 intentos."
}
finally {
    Stop-Transcript | Out-Null
}
