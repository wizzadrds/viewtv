# Habilita SOLO publicaciones de películas verificadas con ID > 3.
# La tarea Windows debe estar registrada pero DESHABILITADA.
# No publica archivos ni reclama trabajos ni toca credenciales.
[CmdletBinding()]
param([switch]$ApproveFutureDownloads)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not $ApproveFutureDownloads) { throw 'No hay aprobación de futuras descargas.' }
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Solo administrador puede cambiar autorización local.'
}
$backup='/home/viewtv/viewtv-backups/publicador-auto-general-pre-20261122-003621.tar.gz'
$expected='672a3d896c70e113b88d21a1b32e6dc8b3224cc7412370f004c12fb0d80f11b6'
$hash=@(& wsl.exe -d Ubuntu-24.04 -- sha256sum $backup)
if($LASTEXITCODE -ne 0 -or $hash.Count -ne 1 -or
    -not $hash[0].StartsWith($expected+' ')) {
    throw 'Respaldo anterior no verificado.'
}
$root='C:\VIEWTV\publicador'
$task=Get-ScheduledTask -TaskName 'VIEWTV - Publicador automatico 0013' -ErrorAction Stop
if($task.State -ne 'Disabled' -or
    $task.Principal.RunLevel -cne 'Limited' -or
    $task.Principal.LogonType -cne 'Interactive') {
    throw 'La tarea no está detenida y confinada al usuario.'
}
if(Get-Service ViewtvPublicador0013 -ErrorAction SilentlyContinue) {
    throw 'No se admite servicio SCM simultáneo.'
}
$state=@(& docker.exe exec viewtv-api-1 python -m worker.organization_windows_cli status)
if($LASTEXITCODE -ne 0 -or $state.Count -ne 1) {
    throw 'La API no responde al modo futuro.'
}
$api=$state[0]|ConvertFrom-Json
if($api.estado -cne 'listo' -or $api.modo -cne 'general' -or
    $api.after_id -ne 3 -or $null -ne $api.allowed_download_id) {
    throw 'La API no limita el histórico hasta la ID 3.'
}
$original=Join-Path $root 'aprobacion.json'
$publisher=Join-Path (Join-Path $root 'bin') 'viewtv_windows_publicador_0013.ps1'
if(-not [IO.File]::Exists($original) -or -not [IO.File]::Exists($publisher)) {
    throw 'Publicador o autorización no instalado.'
}
. $publisher -Mode Library
$current=Get-ViewtvPolicy
if($current.mode -cne 'single' -or
    $current.after_id -ne 2 -or $current.allowed_download_id -ne 3) {
    throw 'El estado de autorización anterior no coincide.'
}
$dir=[IO.DirectoryInfo]::new($root)
if(($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'La carpeta de autorización está redirigida.'
}
$temporary=Join-Path $root ('.aprobacion-general-'+[Guid]::NewGuid().ToString('N')+'.tmp')
$previous=Join-Path $root ('aprobacion.antes-general-'+
    (Get-Date -Format 'yyyyMMdd-HHmmss')+'.json')
$newPolicy=[ordered]@{
    mode='general'
    after_id=3
    allowed_download_id=$null
} | ConvertTo-Json -Compress
[IO.File]::WriteAllText($temporary,$newPolicy,[Text.Encoding]::UTF8)
try {
    [IO.File]::Replace($temporary,$original,$previous,$true)
} finally {
    if([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
}
$checked=Get-ViewtvPolicy
if($checked.mode -cne 'general' -or $checked.after_id -ne 3 -or
    $null -ne $checked.allowed_download_id) {
    throw 'La política nueva no superó el control de ACL y límites.'
}
Write-Output 'WINDOWS_PUBLICACION_GENERAL_SOLO_ID_MAYOR_3=OK'
Write-Output 'WINDOWS_PUBLICACION_RESPALDO_ANTERIOR_CONSERVADO=SI'
Write-Output 'WINDOWS_TAREA_TODAVIA_DESHABILITADA=SI'
