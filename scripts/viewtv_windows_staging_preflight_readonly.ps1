#Requires -Version 5.1
<#
.SYNOPSIS
Comprueba solamente metadatos de dos rutas fijas de Windows.
No crea directorios, enumera archivos ni modifica ACL/contenidos.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$checks = @(
    @{ Label = 'PARENT'; Path = 'C:\VIEWTV\media' },
    @{ Label = 'STAGING'; Path = 'C:\VIEWTV\media\descargas_temporales' }
)
$valid = $true

foreach ($check in $checks) {
    $item = Get-Item -LiteralPath $check.Path -Force -ErrorAction SilentlyContinue
    if ($null -eq $item) {
        Write-Output ('CHECK_' + $check.Label + '=NO_ACCESIBLE')
        $valid = $false
        continue
    }
    $directory = [bool]$item.PSIsContainer
    $reparse = [bool](($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
    Write-Output ('CHECK_' + $check.Label + '_DIRECTORIO=' + $directory)
    Write-Output ('CHECK_' + $check.Label + '_REPARSE=' + $reparse)
    if (-not $directory -or $reparse) {
        $valid = $false
    }
}
if ($valid) {
    Write-Output 'STAGING_PREFLIGHT=OK_SOLO_METADATA'
    exit 0
}
Write-Output 'STAGING_PREFLIGHT=REQUIERE_REVISION'
exit 2
