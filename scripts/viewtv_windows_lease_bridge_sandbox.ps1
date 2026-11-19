# VIEWTV - Windows -> WSL lease preflight, only test sandboxes.
# NOT authenticated production broker. The old journal remains callable without
# this wrapper. Never use this flow to publish real media or confirm SQLite.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SandboxRoot,
    [Parameter(Mandatory=$true)][string]$StageName,
    [Parameter(Mandatory=$true)][string]$FinalName,
    [Parameter(Mandatory=$true)][string]$ApprovalName,
    [Parameter(Mandatory=$true)][string]$KeyPath,
    [Parameter(Mandatory=$true)][string]$JournalRoot,
    [Parameter(Mandatory=$true)][string]$LeaseDatabase,
    [Parameter(Mandatory=$true)][int]$DownloadId,
    [Parameter(Mandatory=$true)][string]$WorkerId,
    [Parameter(Mandatory=$true)][int]$Attempt,
    [Parameter(Mandatory=$true)][string]$TorrentHash,
    [switch]$SimulateLeaseLossAfterFirstCheck,
    [switch]$SimulateLeaseLossAfterMove
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Pinned to the exact WSL test worktree, not an arbitrary caller-supplied
# module or interpreter. No PowerShell -> Linux command string interpolation.
$repo = '/home/viewtv/projects/viewtv-broker-0013-20261119'
$python = '/home/viewtv/projects/viewtv/backend/.venv/bin/python'
$environment = 'PYTHONPATH=' + $repo + '/backend:' + $repo

function Denied([string]$code) {
    return [pscustomobject]@{
        estado = 'denegada_por_lease'
        codigo = $code
        publicacion_iniciada = $false
    }
}

# Refuse unwanted paths before launching WSL. The Python side separately
# checks directory marker, regular file and exact allowed path.
if ($LeaseDatabase -cnotmatch '^/tmp/viewtv-lease-gate-[a-f0-9]{32}/organization\.sqlite3$' -or
    $DownloadId -lt 1 -or $Attempt -lt 1 -or $Attempt -gt 3 -or
    $WorkerId -cnotmatch '^[a-zA-Z0-9_-]{1,128}$' -or
    $TorrentHash -cnotmatch '^([a-f0-9]{40}|[a-f0-9]{64})$') {
    Denied 'identidad_invalida' | ConvertTo-Json -Compress
    return
}

function Read-TestLease {
    try {
        $response = @(& wsl.exe -d Ubuntu-24.04 -e /usr/bin/env $environment $python -m worker.organization_lease_gate_cli_sandbox --database $LeaseDatabase --download-id $DownloadId --worker-id $WorkerId --attempt $Attempt --torrent-hash $TorrentHash)
        if ($LASTEXITCODE -ne 0 -or $response.Count -ne 1) { return $null }
        $parsed = $response[0] | ConvertFrom-Json
        if ($parsed.PSObject.Properties.Name -notcontains 'allowed' -or
            $parsed.PSObject.Properties.Name -notcontains 'code' -or
            $parsed.allowed -isnot [bool] -or $parsed.code -isnot [string]) {
            return $null
        }
        return $parsed
    } catch {
        return $null
    }
}

function Expire-FakeLease {
    # Fault injection ONLY for a signed, marked /tmp sandbox SQLite database.
    $null = & wsl.exe -d Ubuntu-24.04 -e /usr/bin/env $environment $python -m worker.organization_lease_gate_fixture_sandbox expire --database $LeaseDatabase
    if ($LASTEXITCODE -ne 0) { throw 'Fallo al simular pérdida de lease.' }
}

$initial = Read-TestLease
if ($null -eq $initial) {
    Denied 'verificacion_no_disponible' | ConvertTo-Json -Compress
    return
}
if (-not $initial.allowed) {
    Denied $initial.code | ConvertTo-Json -Compress
    return
}

if ($SimulateLeaseLossAfterFirstCheck) {
    Expire-FakeLease
}

# Recheck after any preflight delay, before invoking the sandbox-only journal.
# This still is not atomic with NTFS; a real broker needs a trustworthy
# independent authority and a lease-validation protocol at the move boundary.
$beforeMove = Read-TestLease
if ($null -eq $beforeMove -or -not $beforeMove.allowed) {
    Denied 'lease_no_vigente_antes_de_mover' | ConvertTo-Json -Compress
    return
}

$publication = & (Join-Path $PSScriptRoot 'viewtv_windows_broker_journal_sandbox.ps1') -SandboxRoot $SandboxRoot -StageName $StageName -FinalName $FinalName -ApprovalName $ApprovalName -KeyPath $KeyPath -JournalRoot $JournalRoot -Mode Publish | ConvertFrom-Json

# Never interpret a successful Windows move as an SQLite confirmation.
if ($publication.estado -ne 'publicada_verificada') {
    [pscustomobject]@{
        estado = $publication.estado
        codigo = 'sin_confirmacion_sqlite'
        publicacion_iniciada = $true
    } | ConvertTo-Json -Compress
    return
}

if ($SimulateLeaseLossAfterMove) {
    Expire-FakeLease
}
$after = Read-TestLease
if ($null -eq $after -or -not $after.allowed) {
    [pscustomobject]@{
        estado = 'requiere_revision'
        codigo = 'lease_no_vigente_despues_de_publicar'
        publicacion_iniciada = $true
    } | ConvertTo-Json -Compress
    return
}
[pscustomobject]@{
    estado = 'publicada_verificada_sin_confirmar_sqlite'
    codigo = 'lease_verificado_en_dos_fases'
    publicacion_iniciada = $true
} | ConvertTo-Json -Compress
