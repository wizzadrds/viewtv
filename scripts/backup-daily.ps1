# VIEWTV — copia diaria desde el Programador de tareas de Windows
$ErrorActionPreference = "Stop"

$Distro = "Ubuntu-24.04"
$WslUser = "viewtv"
$LinuxScript = "/home/viewtv/projects/viewtv/scripts/backup-daily.sh"
$LogDir = "C:\\VIEWTV\\logs"
$LogFile = Join-Path $LogDir "backup-daily.log"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
Start-Transcript -Path $LogFile -Append | Out-Null

try {
    # Reintenta si WSL/Docker Desktop todavía no están disponibles al iniciar Windows.
    # Ejecutamos un archivo Bash directamente para evitar problemas de comillas
    # al pasar bloques multilínea con bash -lc desde PowerShell.
    for ($attempt = 1; $attempt -le 10; $attempt++) {
        Write-Output "Intento $attempt de 10: iniciando backup VIEWTV."
        & wsl.exe -d $Distro -u $WslUser --exec /bin/bash $LinuxScript
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
