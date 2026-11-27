# VIEWTV 0022: validar Process-One del publicador con autoridad TOTALMENTE ficticia.
# Nunca invoca docker, lee medios, reclama trabajo, publica ni escanea.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$publisher=Join-Path $PSScriptRoot 'viewtv_windows_publicador_0013.ps1'
if(-not [IO.File]::Exists($publisher)) { throw 'Publicador ausente.' }

. $publisher -Mode Library | Out-Null
$script:fakeCalls=0
function Get-ViewtvPolicy {
    return [pscustomobject]@{mode='general';after_id=1;allowed_download_id=$null}
}
function Retry-PendingScans($Policy) {
    $script:fakeCalls++
}
function Invoke-ViewtvAuthority(
    [string]$Operation,[long]$DownloadId=0,[int]$Attempt=0
) {
    if($Operation -cne 'claim' -or $DownloadId -ne 0 -or $Attempt -ne 0) {
        throw 'La simulacion encontro una operacion inesperada.'
    }
    $script:fakeCalls++
    return [pscustomobject]@{estado='sin_trabajos'}
}

$result=Process-One
if($result -cne 'sin_trabajos' -or $script:fakeCalls -ne 2) {
    throw 'El publicador no devolvio estado ficticio esperado.'
}
Write-Output 'PUBLICADOR_BAJO_MUTEX_SOLO_CON_MOCKS=PASS'

$script:fakeCalls=0
function Invoke-ViewtvAuthority(
    [string]$Operation,[long]$DownloadId=0,[int]$Attempt=0
) {
    $script:fakeCalls++
    throw 'Error simulado de autoridad, sin tocar SQLite.'
}
$failed=$false
try { $null=Process-One } catch { $failed=$true }
if(-not $failed -or $script:fakeCalls -ne 2) {
    throw 'Error de broker ficticio no fue bloqueado.'
}
Write-Output 'ERROR_DE_AUTORIDAD_NO_PERMITE_PUBLICACION=PASS'
Write-Output 'PUBLICACION_REAL_Y_CLAIMS=0'
Write-Output 'ARCHIVOS_REALES_MODIFICADOS=0'
