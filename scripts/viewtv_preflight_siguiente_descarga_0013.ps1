# Preflight nativo Windows de 0013 para una NUEVA descarga futura.
# SOLO LECTURA: no instala servicios, no reclama cola y no enumera medios.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-PlainDirectory([string]$Path) {
    $entry = [IO.DirectoryInfo]::new($Path)
    if (-not $entry.Exists -or
        ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Directorio NTFS faltante o redirigido.'
    }
}
function Get-DockerLines([string[]]$Arguments) {
    $lines = @(& docker.exe @Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker no respondió a una comprobación de solo lectura.'
    }
    return $lines
}
function Assert-DockerFlag([string]$Service, [string]$Flag,
                            [string]$Expected) {
    $actual = @(Get-DockerLines @('exec',$Service,'printenv',$Flag))
    if ($actual.Count -ne 1 -or $actual[0] -cne $Expected) {
        throw ('Flag operativo de '+$Service+' no coincide: '+$Flag)
    }
}
function Assert-Container([string]$Service, [string]$Image) {
    $found = @(Get-DockerLines @('inspect','--format',
        '{{.Config.Image}}',$Service))
    if ($found.Count -ne 1 -or $found[0] -cne $Image) {
        throw ('Imagen de '+$Service+' inesperada.')
    }
    $running = @(Get-DockerLines @('inspect','--format',
        '{{.State.Running}}',$Service))
    if ($running.Count -ne 1 -or $running[0] -cne 'true') {
        throw ('Servicio '+$Service+' no está en marcha.')
    }
}
function Assert-ReadonlyMediaMount([string]$Service) {
    $mounts = @(Get-DockerLines @('inspect','--format',
        '{{range .Mounts}}{{println .Destination .RW}}{{end}}',$Service))
    if (@($mounts | Where-Object { $_ -ceq '/media false' }).Count -ne 1) {
        throw ('Falta /media en solo lectura para '+$Service)
    }
}
function Assert-Alembic0013([string]$Service) {
    $version = @(Get-DockerLines @('exec','-w','/opt/viewtv/backend',
        $Service,'alembic','current'))
    if (@($version | Where-Object {
        $_ -match '^0013_cola_organizacion(?: \(head\))?$'
    }).Count -ne 1) {
        throw ('Esquema 0013 no verificado en '+$Service)
    }
}

try {
    if ([IO.DriveInfo]::new('C').DriveFormat -cne 'NTFS') {
        throw 'Volumen C: no es NTFS.'
    }
    foreach ($folder in @('C:\VIEWTV','C:\VIEWTV\media',
        'C:\VIEWTV\media\descargas_temporales',
        'C:\VIEWTV\media\Peliculas')) {
        Assert-PlainDirectory $folder
    }
    Write-Output 'RUTAS_NTFS=OK_SOLO_METADATA'

    Assert-Container 'viewtv-api-1' 'viewtv:release-0013-api-candidate'
    Assert-Container 'viewtv-worker-1' 'viewtv:release-0013-worker-candidate'
    $health = @(Get-DockerLines @('inspect','--format',
        '{{.State.Health.Status}}','viewtv-api-1'))
    if ($health.Count -ne 1 -or $health[0] -cne 'healthy') {
        throw 'La API no está healthy.'
    }
    Assert-ReadonlyMediaMount 'viewtv-api-1'
    Assert-ReadonlyMediaMount 'viewtv-worker-1'
    Assert-Alembic0013 'viewtv-api-1'
    Assert-Alembic0013 'viewtv-worker-1'
    Write-Output 'API_WORKER_0013=OK'

    Assert-DockerFlag 'viewtv-api-1' 'VIEWTV_WINDOWS_PUBLICATION_MODE' 'disabled'
    Assert-DockerFlag 'viewtv-worker-1' 'VIEWTV_WINDOWS_PUBLICATION_MODE' 'disabled'
    Assert-DockerFlag 'viewtv-worker-1' 'VIEWTV_ENABLE_ORGANIZATION' 'false'
    Assert-DockerFlag 'viewtv-worker-1' 'VIEWTV_ENABLE_AUTO_DOWNLOAD' 'true'
    Assert-DockerFlag 'viewtv-worker-1' 'VIEWTV_AUTO_DOWNLOAD_AFTER_ID' '1'
    Assert-DockerFlag 'viewtv-worker-1' 'VIEWTV_ENABLE_DOWNLOAD_VERIFICATION' 'true'
    Assert-DockerFlag 'viewtv-worker-1' 'VIEWTV_ENABLE_DOWNLOAD_START' 'false'
    Assert-DockerFlag 'viewtv-worker-1' 'VIEWTV_ENABLE_TORRENT_SUBMIT' 'false'
    $status = @(Get-DockerLines @('exec','viewtv-api-1','python','-m',
        'worker.organization_windows_cli','status'))
    if ($status.Count -ne 1 -or
        ($status[0] | ConvertFrom-Json).estado -cne 'deshabilitado') {
        throw 'El publicador no está bloqueado antes de la prueba.'
    }
    Write-Output 'PUBLICACION_AUN_DESHABILITADA=OK'
    $service=Get-Service -Name 'ViewtvPublicador0013' -ErrorAction SilentlyContinue
    if ($service -and $service.Status -ne 'Stopped') {
        throw 'Servicio Windows de publicación en ejecución inesperada.'
    }
    Write-Output 'PUBLICADOR_WINDOWS_NO_ACTIVO=OK'
    Write-Output 'LISTO_PARA_NUEVA_SELECCION_VIEWTV_0013=SI'
} catch {
    Write-Output 'LISTO_PARA_NUEVA_SELECCION_VIEWTV_0013=NO'
    Write-Output ('CAUSA_PRECHECK='+$_.Exception.Message)
    exit 2
}
