# VIEWTV 0018: evidencia de identidad NTFS para un preflight global.
# EXCLUSIVAMENTE lectura. Sin funciones de borrado, pausa o manipulación.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$existing = Join-Path $PSScriptRoot 'viewtv_windows_retirada_auditoria_0016.ps1'
if (-not [IO.File]::Exists($existing)) { throw 'Auditoría base no encontrada.' }

# La auditoría 0016 define las funciones Win32 y valida raíces de medios.
. $existing -Mode Audit | Out-Null

$proofs = @()
$seenFolders = @{}
$seenHashes = @{}
foreach ($path in @([IO.Directory]::GetFiles($JournalRoot,'download-*.json'))) {
    $info = [IO.FileInfo]::new($path)
    if ($info.Name -cnotmatch '^download-([1-9][0-9]*)\.json$') { continue }
    $downloadId = [long]$Matches[1]
    $verified = $false
    $reason = 'validacion_incompleta'
    $contentHash = ''
    $linkCount = 0
    try {
        $validated = Test-Journal $info
        $journal = [IO.File]::ReadAllBytes($path)
        $digest = [Security.Cryptography.SHA256]::Create()
        try {
            $contentHash=[BitConverter]::ToString(
                $digest.ComputeHash($journal)).Replace('-','').ToLowerInvariant()
        } finally { $digest.Dispose() }
        $record=[Text.Encoding]::UTF8.GetString($journal)|ConvertFrom-Json
        if ([string]$record.stage_name -cnotmatch
            ('^\.viewtv-publicando-'+$downloadId+'-[a-f0-9]{32}$')) {
            throw 'Etapa del publicador inválida.'
        }
        $stage=[IO.Path]::Combine($MovieRoot,[string]$record.stage_name)
        if([IO.Directory]::Exists($stage) -or [IO.File]::Exists($stage)) {
            throw 'Quedan operaciones de publicación pendientes.'
        }
        foreach($item in @($record.intent.files)) {
            $src=Resolve-UnderRoot $SourceRoot ([string]$item.source_relative)
            $dst=Resolve-UnderRoot $MediaRoot ([string]$item.destination_relative)
            $finger=File-Fingerprint $src
            $fingerTarget=File-Fingerprint $dst
            if ($finger.links -ne 2 -or $fingerTarget.links -ne 2 -or
                $finger.volume -ne $fingerTarget.volume -or
                $finger.high -ne $fingerTarget.high -or
                $finger.low -ne $fingerTarget.low) {
                throw 'El archivo no tiene exactamente dos enlaces.'
            }
        }
        $folderKey = ([string]$validated.folder).ToLowerInvariant()
        $hashKey = [string]$record.intent.torrent_hash
        if ($seenFolders.ContainsKey($folderKey) -or
            $seenHashes.ContainsKey($hashKey)) {
            throw 'Directorio o torrent compartido por varias publicaciones.'
        }
        $seenFolders[$folderKey] = $true
        $seenHashes[$hashKey] = $true
        $linkCount=@($record.intent.files).Count
        $verified=$true
        $reason='identidad_ntfs_verificada'
    } catch {
        # Nunca divulgar rutas, títulos, hashes o errores internos.
        $verified=$false
        $reason='identidad_no_verificable'
        $contentHash=''
    }
    $proofs += [pscustomobject]@{
        download_id=$downloadId
        ntfs_verified=$verified
        journal_sha256=$contentHash
        archivos=$linkCount
        reason=$reason
    }
}
$output=[pscustomobject]@{
    version=1
    modo='solo_lectura'
    evidencias=@($proofs)
    retiradas_ejecutadas=0
    originales_modificados=0
}
ConvertTo-Json -InputObject $output -Compress -Depth 8
