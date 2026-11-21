# Comprobación posterior de la publicación ID3: solo lectura.
# No modifica permisos, no repite claim ni toca datos o torrents ajenos.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$publicador='C:\VIEWTV\publicador\bin\viewtv_windows_publicador_0013.ps1'
if (-not [IO.File]::Exists($publicador)) {
    throw 'No existe el publicador instalado para ID3.'
}
. $publicador -Mode Library
$policy=Get-ViewtvPolicy
if ($policy.mode -cne 'single' -or $policy.after_id -ne 2 -or
    $policy.allowed_download_id -ne 3) {
    throw 'La política de Windows no coincide con la descarga 3.'
}
$journalPath=Join-Path $Journal 'download-3.json'
$receiptPath=Join-Path $Journal 'scan-3.ok'
foreach($file in @($journalPath,$receiptPath)) {
    $item=[IO.FileInfo]::new($file)
    if (-not $item.Exists -or $item.Length -le 0 -or $item.Length -gt 16384 -or
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Diario o comprobante no autorizado.'
    }
}
$record=[IO.File]::ReadAllText($journalPath) | ConvertFrom-Json
$receipt=[IO.File]::ReadAllText($receiptPath) | ConvertFrom-Json
if ($record.version -ne 1 -or $record.download_id -ne 3 -or
    $record.intent.download_id -ne 3 -or $receipt.id -ne 3 -or
    [string]$record.manifest_sha256 -cne (Get-PlanHash $record.intent)) {
    throw 'Identidad del diario o del comprobante de escaneo incongruente.'
}
$items=@($record.intent.files)
if ($items.Count -ne 1 -or $record.intent.library -cne 'Peliculas' -or
    [string]$record.intent.files[0].destination_relative -notmatch '^Peliculas/') {
    throw 'Manifiesto de película no esperado.'
}
$folder=([string]$items[0].destination_relative).Split('/')[1]
Assert-Leaf $folder
if ($folder -cne [string]$record.folder) {
    throw 'La carpeta publicada no coincide con el diario.'
}
Verify-Published $record.intent $folder
$source=Resolve-Source ([string]$items[0].source_relative) ([long]$items[0].size_bytes)
$filename=([string]$items[0].destination_relative).Split('/')[-1]
$destination=Join-Path (Join-Path $Movies $folder) $filename
$hardlinks=@(& fsutil.exe hardlink list $destination)
if ($LASTEXITCODE -ne 0 -or $hardlinks.Count -lt 2) {
    throw 'El archivo no tiene el enlace duro NTFS esperado.'
}
$staged=@([IO.Directory]::GetDirectories($Movies,'.viewtv-publicando-3-*'))
if ($staged.Count -ne 0) {
    throw 'Queda un staging de publicación ambiguo.'
}
Write-Output 'DESCARGA_3_ORIGEN_CONSERVADO=SI'
Write-Output 'DESCARGA_3_VIDEO_PUBLICADO_EN_NTFS=SI'
Write-Output 'ENLACE_DURO_NTFS_VERIFICADO=SI'
Write-Output 'DESCARGA_3_DIARIO_Y_RECIBO_SCAN=SI'
Write-Output 'DESCARGA_3_STAGING_RESIDUAL=NO'
