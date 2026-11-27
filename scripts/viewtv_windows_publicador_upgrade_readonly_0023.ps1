# VIEWTV 0023: inventario de actualizacion del publicador, ESTRICTAMENTE lectura.
# Sin parar servicios/tareas, sin instalar, sin cambiar permisos ni medios.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

$InstalledRoot='C:\VIEWTV\publicador'
$InstalledBin=Join-Path $InstalledRoot 'bin'
$InstalledScript=Join-Path $InstalledBin 'viewtv_windows_publicador_0013.ps1'
$InstalledMutex=Join-Path $InstalledBin 'viewtv_windows_media_lock_0022.ps1'
$InstalledTaskScript=Join-Path $InstalledBin 'viewtv_publicador_tarea_periodica_0013.ps1'
$SourceScript=Join-Path $PSScriptRoot 'viewtv_windows_publicador_0013.ps1'
$SourceMutex=Join-Path $PSScriptRoot 'viewtv_windows_media_lock_0022.ps1'
$SourceTaskScript=Join-Path $PSScriptRoot 'viewtv_publicador_tarea_periodica_0013.ps1'
$TaskName='VIEWTV - Publicador automatico 0013'
$ServiceName='ViewtvPublicador0013'

function Assert-FileIsPlain([string]$Path) {
    $entry=[IO.FileInfo]::new($Path)
    if(-not $entry.Exists -or
        ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        $entry.Length -lt 100 -or $entry.Length -gt 60000) {
        throw 'Archivo de publicador no verificable.'
    }
}
function Assert-DirIsPlain([string]$Path) {
    $entry=[IO.DirectoryInfo]::new($Path)
    if(-not $entry.Exists -or
       ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Directorio instalado no verificable.'
    }
}
function Hash-Plain([string]$Path) {
    Assert-FileIsPlain $Path
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}
function Publish-Bool([string]$Key,[bool]$Value) {
    Write-Output ($Key+'='+$(if($Value){'SI'}else{'NO'}))
}

try {
    Assert-DirIsPlain 'C:\VIEWTV'
    Assert-DirIsPlain $InstalledRoot
    Assert-DirIsPlain $InstalledBin

    $installedHash=Hash-Plain $InstalledScript
    $sourceHash=Hash-Plain $SourceScript
    $versionMatches=($installedHash -ceq $sourceHash)
    $sourceHelperHash=Hash-Plain $SourceMutex
    $mutexInstalled=[IO.File]::Exists($InstalledMutex)
    $mutexMatches=$false
    if($mutexInstalled) {
        $mutexMatches=((Hash-Plain $InstalledMutex) -ceq $sourceHelperHash)
    }
    $taskWrapperMatches=(
        (Hash-Plain $InstalledTaskScript) -ceq
        (Hash-Plain $SourceTaskScript)
    )

    # Estado de la tarea programada y del servicio, SIN arrancarlos.
    $scheduled=Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $taskLimited=(
        $scheduled.Principal.RunLevel -ceq 'Limited' -and
        $scheduled.Principal.LogonType -ceq 'Interactive'
    )
    $taskState=[string]$scheduled.State
    if($taskState -cnotin @('Ready','Disabled','Running','Queued')) {
        throw 'Estado de tarea no verificable.'
    }
    $taskActive=$taskState -cin @('Running','Queued')
    $actions=@($scheduled.Actions)
    $taskExact=(
        $actions.Count -eq 1 -and
        [string]$actions[0].Execute -match 'powershell\.exe$' -and
        [string]$actions[0].Arguments -match
            'viewtv_publicador_tarea_periodica_0013\.ps1'
    )
    $service=Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    $serviceActive=$false
    $serviceInstalled=$false
    if($null -ne $service) {
        $serviceInstalled=$true
        $serviceActive=($service.Status -cne 'Stopped')
    }

    # WMI: inspeccionar procesos, nunca imprimir PIDs ni command-lines.
    $processes=@(Get-CimInstance -ClassName Win32_Process -Filter (
        "Name='powershell.exe' OR Name='pwsh.exe' OR " +
        "Name='ViewtvPublicadorServicio0013.exe'"
    ) -ErrorAction Stop)
    $matching=0
    $unknown=0
    foreach($process in $processes) {
        $exe=[string]$process.Name
        $line=$process.CommandLine
        if($null -eq $line) { $unknown++;continue }
        if($exe -ieq 'ViewtvPublicadorServicio0013.exe' -or
           $line -match 'viewtv_windows_publicador_0013\.ps1' -or
           $line -match 'viewtv_publicador_tarea_periodica_0013\.ps1') {
            $matching++
        }
    }

    # La propuesta de reemplazo nunca se ejecuta desde este diagnóstico.
    # "Listo" aquí es solo evidencia, no autoridad para detener la tarea.
    Write-Output 'UPGRADE_0023=SOLO_LECTURA'
    Publish-Bool 'PUBLICADOR_INSTALADO_COINCIDE_CON_FUENTE_0022' $versionMatches
    Publish-Bool 'HELPER_MUTEX_0022_INSTALADO' $mutexInstalled
    Publish-Bool 'HELPER_INSTALADO_COINCIDE_CON_FUENTE_0022' $mutexMatches
    Publish-Bool 'TAREA_PROGRAMADA_CON_USUARIO_LIMITADO' $taskLimited
    Publish-Bool 'ACCION_TAREA_ES_ESPERADA' $taskExact
    Publish-Bool 'WRAPPER_TAREA_COINCIDE_CON_FUENTE' $taskWrapperMatches
    Write-Output ('ESTADO_TAREA='+$taskState.ToUpperInvariant())
    Publish-Bool 'TAREA_EN_EJECUCION' $taskActive
    Publish-Bool 'SERVICIO_SCM_EXISTE' $serviceInstalled
    Publish-Bool 'SERVICIO_SCM_ACTIVO' $serviceActive
    Write-Output ('PROCESOS_PUBLICADOR_OBSERVADOS='+[string]$matching)
    Write-Output ('PROCESOS_POWERSHELL_SIN_LINEA_VISIBLE='+[string]$unknown)
    Publish-Bool 'VERSION_LISTA_PARA_REVISION_DE_MUTEX' (
        $versionMatches -and $mutexMatches -and $taskWrapperMatches -and
        $taskLimited -and $taskExact -and -not $taskActive -and
        -not $serviceActive -and $matching -eq 0 -and $unknown -eq 0
    )
    # Una instantanea de procesos NUNCA puede demostrar quietud durable;
    # la tarea puede iniciar otra pasada inmediatamente despues.
    Write-Output 'PUEDE_AFIRMARSE_EXCLUSION_PRODUCTIVA=NO'
    Write-Output 'REEMPLAZO_AUTOMATICO_DESDE_AUDITORIA=NO'
    Write-Output 'PROCESOS_DETENIDOS=0'
    Write-Output 'TAREAS_MODIFICADAS=0'
    Write-Output 'ARCHIVOS_MEDIA_MODIFICADOS=0'
    Write-Output 'TORRENTS_MODIFICADOS=0'
} catch {
    # Nunca emitir excepciones, command lines, nombres de usuarios o rutas.
    Write-Output 'UPGRADE_0023=BLOQUEADO_SIN_PRUEBA_SUFICIENTE'
    Write-Output 'PUEDE_AFIRMARSE_EXCLUSION_PRODUCTIVA=NO'
    Write-Output 'REEMPLAZO_AUTOMATICO_DESDE_AUDITORIA=NO'
    Write-Output 'PROCESOS_DETENIDOS=0'
    Write-Output 'TAREAS_MODIFICADAS=0'
    Write-Output 'ARCHIVOS_MEDIA_MODIFICADOS=0'
    Write-Output 'TORRENTS_MODIFICADOS=0'
    exit 2
}
