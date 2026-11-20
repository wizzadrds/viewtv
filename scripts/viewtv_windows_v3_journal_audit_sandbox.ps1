# VIEWTV 0013 — read-only, fail-closed audit of a whole v3 admission journal.
# A single GUID journal survives process restarts. NOT global production state.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_v3_claim_gate_sandbox.ps1')

function Assert-ViewtvSandboxV3JournalHealthy([string]$JournalRoot,[string]$TestKeyPath) {
    $temp=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
    $root=[IO.Path]::GetFullPath($JournalRoot).TrimEnd('\')
    if([IO.Path]::GetDirectoryName($root) -ine $temp -or
       [IO.Path]::GetFileName($root) -cnotmatch '^viewtv-pipe-broker-[a-f0-9]{32}$'){
        throw 'Auditoría v3 fuera de un diario GUID de prueba.'
    }
    $null=Assert-ViewtvV3ClaimAcl $root $true
    $mark=Assert-ViewtvV3ClaimFile $root '.viewtv-pipe-only' 32 64
    if($mark -cne ('VIEWTV_PIPE_BROKER_TEST_ONLY_V1'+[char]10)){
        throw 'Marcador incorrecto; detener admisiones.'
    }
    $entries=@(Get-ChildItem -LiteralPath $root -Force)
    if($entries.Count -gt 129){
        throw 'Demasiados registros: requiere conciliación antes de admitir.'
    }
    $claims=@{}
    $nonces=@{}
    foreach($entry in $entries){
        if($entry.PSIsContainer -or
           ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
            throw 'Hay subdirectorios o enlaces no autorizados en el diario.'
        }
        $name=$entry.Name
        if($name -ceq '.viewtv-pipe-only'){continue}
        if($name -cmatch '^\.viewtv-download-([1-9][0-9]{0,18})\.json$'){
            $id=[long]::Parse($Matches[1],
               [Globalization.CultureInfo]::InvariantCulture)
            if($claims.ContainsKey($id)){throw 'Reserva repetida para una descarga.'}
            $claims[$id]=$name
        } elseif($name -cmatch '^\.viewtv-nonce-([a-f0-9]{32})\.json$'){
            $nonce=$Matches[1]
            if($nonces.ContainsKey($nonce)){throw 'Nonce duplicado.'}
            $nonces[$nonce]=$name
        } else {
            throw 'Archivo inesperado en diario v3, requiere revisión.'
        }
    }
    if($claims.Count -ne $nonces.Count){
        throw 'Admisión v3 parcial: descarga/nonce huérfano.'
    }
    $used=@{}
    foreach($id in $claims.Keys){
        $raw=Assert-ViewtvV3ClaimFile $root $claims[$id] 150 2048
        $claim=$raw|ConvertFrom-Json
        if($claim -isnot [pscustomobject] -or
           $claim.nonce -isnot [string] -or
           $claim.nonce -cnotmatch '^[a-f0-9]{32}$' -or
           -not $nonces.ContainsKey($claim.nonce) -or
           $used.ContainsKey($claim.nonce)){
            throw 'Reserva v3 con nonce inexistente, repetido o no válido.'
        }
        # A complete older claim is legal history, but not reusable for
        # publication: only this audit skips the five-minute age limit.
        $null=Assert-ViewtvSandboxPinnedV3Admission $root $id (
            [int]$claim.attempt) ([string]$claim.worker) (
            [string]$claim.sandbox) ([string]$claim.stage) (
            [string]$claim.final) ([string]$claim.torrent_hash) (
            [string]$claim.manifest_sha256) ([string]$claim.nonce) $TestKeyPath $true
        $used[$claim.nonce]=$true
    }
    if($used.Count -ne $nonces.Count){
        throw 'Existe un nonce sin una reserva de descarga.'
    }
    return $true
}
