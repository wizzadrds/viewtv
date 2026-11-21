# Ensayo de integración del publicador candidato 0013.
# ÚNICAMENTE archivos sintéticos bajo C:\Users\Public\viewtv-win-sandbox-GUID.
# Autoridad, cola y qBittorrent simulados; nunca llama docker ni toca C:\VIEWTV.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Public=[IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
if ($Public -ine 'C:\Users\Public' -or -not [IO.Directory]::Exists($Public)) {
    throw 'Windows Public esperado no disponible; no ensayar.'
}
$root=Join-Path $Public ('viewtv-win-sandbox-'+[Guid]::NewGuid().ToString('N'))
if ([IO.Directory]::Exists($root)) { throw 'Sandbox preexistente.' }
[IO.Directory]::CreateDirectory($root)|Out-Null
[IO.File]::WriteAllText((Join-Path $root '.viewtv-win-sandbox-only'),
    "VIEWTV_WINDOWS_SANDBOX_ONLY_V1`n")
try {
    $scriptPath=Join-Path $PSScriptRoot 'viewtv_windows_publicador_0013.ps1'
    . $scriptPath -Mode Library
    $Media=Join-Path $root 'media'
    $SourceRoot=Join-Path $Media 'descargas_temporales'
    $Movies=Join-Path $Media 'Peliculas'
    $Broker=Join-Path $root 'publicador'
    $Journal=Join-Path $Broker 'journal'
    foreach ($dir in @($SourceRoot,$Movies,$Journal)) {
        [IO.Directory]::CreateDirectory($dir)|Out-Null
    }
    $original=Join-Path $SourceRoot 'Vídeo [4k] (2025)'
    [IO.Directory]::CreateDirectory($original)|Out-Null
    $source=Join-Path $original 'Vídeo [Esp].mkv'
    [IO.File]::WriteAllBytes($source,[Text.Encoding]::UTF8.GetBytes(
        'VIDEO_FICTICIO_PUBLICADOR_0013_NTFS'))
    $outside=Join-Path $original 'Publicidad.url'
    [IO.File]::WriteAllText($outside,'URL_FICTICIA_NO_PUBLICAR')
    $size=[long]([IO.FileInfo]::new($source)).Length
    $script:ClaimId=3
    $script:Claimed=$false
    $script:ConfirmedIds=@{}
    $script:FailConfirmOnce=$false
    $script:ApprovedIntent=[pscustomobject]@{
        version=1
        download_id=3
        attempt=1
        worker_id='publicador-windows-0013'
        torrent_hash=('a'*40)
        lease_expires_utc=[DateTime]::UtcNow.AddMinutes(2).ToString('o')
        library='Peliculas'
        files=@([pscustomobject]@{
            source_relative='Vídeo [4k] (2025)/Vídeo [Esp].mkv'
            destination_relative='Peliculas/Ficticia (2025)/Ficticia (2025).mkv'
            size_bytes=$size
        })
    }
    function Get-ViewtvPolicy {
        return [pscustomobject]@{
            mode='single'; after_id=2; allowed_download_id=[int]$script:ClaimId
        }
    }
    function Invoke-ViewtvAuthority([string]$Operation,[long]$DownloadId=0,
                                     [int]$Attempt=0) {
        switch ($Operation) {
            'status' {
                return [pscustomobject]@{
                    estado='listo'
                    modo='single'
                    after_id=2
                    allowed_download_id=[int]$script:ClaimId
                }
            }
            'claim' {
                if ($script:Claimed) {
                    return [pscustomobject]@{estado='sin_trabajos'}
                }
                $script:Claimed=$true
                return [pscustomobject]@{
                    estado='reclamada';download_id=[long]$script:ClaimId;attempt=1
                }
            }
            'prepare' {
                return [pscustomobject]@{
                    estado='preparada';intent=$script:ApprovedIntent
                }
            }
            'renew' { return [pscustomobject]@{estado='renovada'} }
            'confirm' {
                if($script:FailConfirmOnce) {
                    $script:FailConfirmOnce=$false
                    return [pscustomobject]@{estado='lease_perdido'}
                }
                $script:ConfirmedIds[[string]$DownloadId]=$true
                return [pscustomobject]@{estado='organizada'}
            }
            'verify-source' {
                return [pscustomobject]@{
                    estado='fuente_verificada'
                    torrent_hash=$script:ApprovedIntent.torrent_hash
                    files=@([pscustomobject]@{
                        source_relative='Vídeo [4k] (2025)/Vídeo [Esp].mkv'
                        size_bytes=$size
                    })
                }
            }
            'scan' {
                if($script:ConfirmedIds.ContainsKey([string]$DownloadId)) {
                    return [pscustomobject]@{estado='escaneo_solicitado'}
                }
                return [pscustomobject]@{estado='rechazada'}
            }
            default { throw 'Operación no prevista por el ensayo.' }
        }
    }
    Assert-AuthorityReady (Get-ViewtvPolicy)
    $first=Process-One
    if ($first -cne 'publicada') { throw 'No publicó la carpeta ficticia.' }
    $final=Join-Path $Movies 'Ficticia (2025)\Ficticia (2025).mkv'
    if (-not [IO.File]::Exists($final) -or
        ([IO.FileInfo]::new($final)).Length -ne $size -or
        -not [IO.File]::Exists($source) -or
        [IO.File]::Exists((Join-Path $Movies 'Ficticia (2025)\Publicidad.url')) -or
        -not [IO.File]::Exists((Join-Path $Journal 'download-3.json')) -or
        -not [IO.File]::Exists((Join-Path $Journal 'scan-3.ok'))) {
        throw 'La publicación o su diario no coinciden con el contrato.'
    }
    $second=Process-One
    if ($second -cne 'sin_trabajos') { throw 'Reintentó una publicación.' }

    # Recuperación tras corte entre movimiento NTFS y confirmación SQLite:
    # nuevo intento reconoce journal+destino, NO vuelve a crear enlaces.
    $script:ClaimId=5
    $script:Claimed=$false
    $script:FailConfirmOnce=$true
    $script:ApprovedIntent=[pscustomobject]@{
        version=1;download_id=5;attempt=1;worker_id='publicador-windows-0013'
        torrent_hash=('c'*40)
        lease_expires_utc=[DateTime]::UtcNow.AddMinutes(2).ToString('o')
        library='Peliculas'
        files=@([pscustomobject]@{
            source_relative='Vídeo [4k] (2025)/Vídeo [Esp].mkv'
            destination_relative='Peliculas/Recuperada (2025)/Recuperada (2025).mkv'
            size_bytes=$size
        })
    }
    $interrupted=$false
    try {$null=Process-One} catch {$interrupted=$true}
    $restored=Join-Path $Movies 'Recuperada (2025)\Recuperada (2025).mkv'
    if (-not $interrupted -or -not [IO.File]::Exists($restored) -or
        -not [IO.File]::Exists((Join-Path $Journal 'download-5.json')) -or
        [IO.File]::Exists((Join-Path $Journal 'scan-5.ok'))) {
        throw 'Fallo al simular la publicación antes de confirmar.'
    }
    $script:Claimed=$false
    $reconciled=Process-One
    if($reconciled -cne 'reconciliada' -or
        -not [IO.File]::Exists((Join-Path $Journal 'scan-5.ok')) -or
        [IO.File]::ReadAllText($restored) -cne
        'VIDEO_FICTICIO_PUBLICADOR_0013_NTFS') {
        throw 'No concilió la publicación tras perder la confirmación.'
    }

    $script:ClaimId=4
    $script:Claimed=$false
    $script:ApprovedIntent=[pscustomobject]@{
        version=1
        download_id=4
        attempt=1
        worker_id='publicador-windows-0013'
        torrent_hash=('b'*40)
        lease_expires_utc=[DateTime]::UtcNow.AddMinutes(2).ToString('o')
        library='Peliculas'
        files=@([pscustomobject]@{
            source_relative='Vídeo [4k] (2025)/Vídeo [Esp].mkv'
            destination_relative='Peliculas/Ficticia (2025)/Ficticia (2025).mkv'
            size_bytes=$size
        })
    }
    $blocked=$false
    try { $null=Process-One } catch { $blocked=$true }
    if (-not $blocked -or
        [IO.File]::Exists((Join-Path $Journal 'download-4.json')) -or
        [IO.File]::ReadAllText($final) -cne 'VIDEO_FICTICIO_PUBLICADOR_0013_NTFS') {
        throw 'La colisión no quedó bloqueada antes de crear el diario.'
    }
    Write-Output 'PUBLICADOR_WINDOWS_0013_SANDBOX_PASS=1'
    Write-Output 'EVIDENCIA=hardlink_NTFS,DirectoryMove,journal,scan,origen_intacto,no_url,no_sobrescritura'
} finally {
    $marker=Join-Path $root '.viewtv-win-sandbox-only'
    if ([IO.Directory]::Exists($root) -and
        [IO.Path]::GetDirectoryName($root) -ieq $Public -and
        [IO.Path]::GetFileName($root) -cmatch '^viewtv-win-sandbox-[a-f0-9]{32}$' -and
        [IO.File]::Exists($marker) -and
        [IO.File]::ReadAllText($marker) -ceq "VIEWTV_WINDOWS_SANDBOX_ONLY_V1`n") {
        [IO.Directory]::Delete($root,$true)
    }
}
