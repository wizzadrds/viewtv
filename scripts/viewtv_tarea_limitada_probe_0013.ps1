# Sondeo sin modificaciones en descarga, SQLite, Docker ni bibliotecas.
# Debe ejecutarse con token de usuario INTERACTIVO y NO elevado.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$principal=[Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent())
if($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'TAREA_ELEVADA_NO_AUTORIZADA'
}
$root='C:\VIEWTV\publicador'
$journal=Join-Path $root 'journal'
$pub=Join-Path (Join-Path $root 'bin') 'viewtv_windows_publicador_0013.ps1'
if(-not [IO.File]::Exists($pub)) { throw 'SCRIPT_PUBLICADOR_NO_EXISTE' }
. $pub -Mode Library
$p=Get-ViewtvPolicy
if($p.mode -cne 'single' -or $p.after_id -ne 2 -or
    $p.allowed_download_id -ne 3) { throw 'POLITICA_DE_PRUEBA_INESPERADA' }
$status=@(& docker.exe exec viewtv-api-1 python -m worker.organization_windows_cli status)
if($LASTEXITCODE -ne 0 -or $status.Count -ne 1 -or
    ($status[0] | ConvertFrom-Json).estado -cne 'deshabilitado') {
    throw 'DOCKER_API_NO_ACCESIBLE_DESDE_USUARIO_LIMITADO'
}
$mount=@(& docker.exe inspect --format '{{range .Mounts}}{{println .Destination .RW}}{{end}}' viewtv-api-1)
if($LASTEXITCODE -ne 0 -or
    @($mount | Where-Object { $_ -ceq '/media false' }).Count -ne 1) {
    throw 'MONTAJE_API_MEDIA_INSEGURO'
}
$target=Join-Path $journal 'tarea-limitada-probe-0013.json'
if([IO.File]::Exists($target)) { throw 'SONDEO_PREVIO_EXISTE' }
$data=[ordered]@{
    resultado='SONDEO_LIMITADO_OK'
    elevada=$false
    acceso_docker=$true
    medios_solo_lectura=$true
    politica_windows='single'
    fecha_utc=[DateTime]::UtcNow.ToString('o')
} | ConvertTo-Json -Compress
[IO.File]::WriteAllText($target,$data,[Text.Encoding]::UTF8)
Write-Output 'SONDEO_LIMITADO_OK'
