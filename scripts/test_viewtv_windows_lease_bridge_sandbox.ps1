# Prueba cruzada PowerShell Windows -> WSL SQLite -> journal -> NTFS.
# Solo sandboxes GUID creados en esta ejecución. Sin redes ni datos reales.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$public = [IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
$temp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
if ($public -ine 'C:\Users\Public') { throw 'Sandbox de Windows obligatorio.' }
$root = Join-Path $public ('viewtv-win-sandbox-' + [Guid]::NewGuid().ToString('N'))
$journal = Join-Path $temp ('viewtv-broker-journal-' + [Guid]::NewGuid().ToString('N'))
$rootMarker = Join-Path $root '.viewtv-win-sandbox-only'
$journalMarker = Join-Path $journal '.viewtv-journal-only'
$rootValue = 'VIEWTV_WINDOWS_SANDBOX_ONLY_V1' + [char]10
$journalValue = 'VIEWTV_WINDOWS_JOURNAL_SANDBOX_V1' + [char]10
$keyPath = $null
$fixtures = @()
$results = [ordered]@{}
$bridge = Join-Path $PSScriptRoot 'viewtv_windows_lease_bridge_sandbox.ps1'
. (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')
$repo = '/home/viewtv/projects/viewtv-broker-0013-20261119'
$python = '/home/viewtv/projects/viewtv/backend/.venv/bin/python'
$environment = 'PYTHONPATH=' + $repo + '/backend:' + $repo

function Invoke-Fixture([string]$action, [string]$db = '') {
    if ($action -eq 'create') {
        $raw = @(& wsl.exe -d Ubuntu-24.04 -e /usr/bin/env $environment $python -m worker.organization_lease_gate_fixture_sandbox create)
    } else {
        $raw = @(& wsl.exe -d Ubuntu-24.04 -e /usr/bin/env $environment $python -m worker.organization_lease_gate_fixture_sandbox $action --database $db)
    }
    if ($LASTEXITCODE -ne 0 -or $raw.Count -ne 1) {
        throw 'No se pudo configurar o limpiar el sandbox SQLite ficticio.'
    }
    return ($raw[0] | ConvertFrom-Json)
}
function New-Stage([int]$id, [string]$final) {
    $name = '.viewtv-stage-' + $id
    $dir = Join-Path $root $name
    [IO.Directory]::CreateDirectory($dir) | Out-Null
    [IO.File]::WriteAllText((Join-Path $dir 'Video ficticio.mkv'), 'video de prueba ' + $id)
    [IO.File]::WriteAllText((Join-Path $dir 'Video ficticio.es.srt'), 'subtitulo de prueba ' + $id)
    $approval = New-ViewtvTestApproval -SandboxRoot $root -StageName $name -FinalName $final -KeyPath $keyPath
    return [pscustomobject]@{Stage=$name; Final=$final; Approval=$approval}
}
function Invoke-Bridge($plan, $fixture, [hashtable]$patch = @{}) {
    $args = @{
        SandboxRoot=$root; JournalRoot=$journal; KeyPath=$keyPath
        StageName=$plan.Stage; FinalName=$plan.Final; ApprovalName=$plan.Approval
        LeaseDatabase=$fixture.database; DownloadId=[int]$fixture.download_id
        WorkerId=[string]$fixture.worker_id; Attempt=[int]$fixture.attempt
        TorrentHash=[string]$fixture.torrent_hash
    }
    foreach ($key in $patch.Keys) { $args[$key] = $patch[$key] }
    return (& $bridge @args | ConvertFrom-Json)
}
function Should-Fail([scriptblock]$action) {
    $rejected = $false
    try { & $action | Out-Null } catch { $rejected = $true }
    if (-not $rejected) { throw 'Una operación de riesgo no se rechazó.' }
}
function Assert-NotPublished($plan) {
    if (-not [IO.Directory]::Exists((Join-Path $root $plan.Stage)) -or
        [IO.Directory]::Exists((Join-Path $root $plan.Final))) {
        throw 'Una autorización denegada publicó o alteró el staging.'
    }
    $id = $plan.Stage.Substring('.viewtv-stage-'.Length)
    if ([IO.File]::Exists((Join-Path $journal ('.viewtv-intent-' + $id + '.json')))) {
        throw 'Se emitió intención durable pese a la denegación del lease.'
    }
}

try {
    if ([IO.Directory]::Exists($root) -or [IO.Directory]::Exists($journal)) {
        throw 'Sandbox aleatorio ya existente.'
    }
    [IO.Directory]::CreateDirectory($root) | Out-Null
    [IO.Directory]::CreateDirectory($journal) | Out-Null
    # ACL de diario fuera del volumen compartido con Docker.
    $who = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $system = [Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid, $null
    )
    $admins = [Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid, $null
    )
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $inherit = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
               [Security.AccessControl.InheritanceFlags]::ObjectInherit
    foreach ($sid in @($who, $system, $admins)) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $sid, [Security.AccessControl.FileSystemRights]::FullControl,
            $inherit, [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow
        ))
    }
    [IO.Directory]::SetAccessControl($journal, $acl)
    [IO.File]::WriteAllText($rootMarker, $rootValue)
    [IO.File]::WriteAllText($journalMarker, $journalValue)
    $keyPath = New-ViewtvTestKey

    $f1 = Invoke-Fixture 'create'
    $fixtures += $f1
    $p1 = New-Stage 1 'Publicada con lease'
    $videoSha = (Get-FileHash -LiteralPath (Join-Path (Join-Path $root $p1.Stage) 'Video ficticio.mkv') -Algorithm SHA256).Hash
    $ok = Invoke-Bridge $p1 $f1
    if ($ok.estado -ne 'publicada_verificada_sin_confirmar_sqlite' -or
        (Get-FileHash -LiteralPath (Join-Path (Join-Path $root $p1.Final) 'Video ficticio.mkv') -Algorithm SHA256).Hash -ne $videoSha -or
        [IO.Directory]::Exists((Join-Path $root $p1.Stage))) {
        throw 'La publicación con lease válido no fue verificada.'
    }
    $results['publicacion_gated_y_sha256'] = 'correcto'

    $again = Invoke-Bridge $p1 $f1
    if ($again.estado -ne 'reutilizacion_bloqueada') {
        throw 'Se admitió un segundo movimiento.'
    }
    $results['replay_mismo_staging'] = 'bloqueado'

    $p2 = New-Stage 2 'Otra identidad'
    $denied = Invoke-Bridge $p2 $f1 @{WorkerId='intruso'}
    if ($denied.estado -ne 'denegada_por_lease') { throw 'Otro worker obtuvo permiso.' }
    Assert-NotPublished $p2
    $results['worker_incorrecto'] = 'denegado'

    $p3 = New-Stage 3 'Intento obsoleto'
    $denied = Invoke-Bridge $p3 $f1 @{Attempt=2}
    if ($denied.estado -ne 'denegada_por_lease') { throw 'Un intento incorrecto pasó.' }
    Assert-NotPublished $p3
    $results['intento_incorrecto'] = 'denegado'

    $p4 = New-Stage 4 'Torrent diferente'
    $denied = Invoke-Bridge $p4 $f1 @{TorrentHash=('b' * 40)}
    if ($denied.estado -ne 'denegada_por_lease') { throw 'Otro hash pasó.' }
    Assert-NotPublished $p4
    $results['torrent_incorrecto'] = 'denegado'

    $p5 = New-Stage 5 'Ruta no autorizada'
    $denied = Invoke-Bridge $p5 $f1 @{LeaseDatabase='/tmp/otra-base.sqlite3'}
    if ($denied.estado -ne 'denegada_por_lease') { throw 'Se aceptó una ruta ajena.' }
    Assert-NotPublished $p5
    $results['ruta_db_fuera_sandbox'] = 'denegada'

    # A valid lease cannot replace an existing target; the journal remains
    # for human reconciliation after the failure.
    $p6 = New-Stage 6 $p1.Final
    Should-Fail { Invoke-Bridge $p6 $f1 }
    if (-not [IO.Directory]::Exists((Join-Path $root $p6.Stage)) -or
        (Get-FileHash -LiteralPath (Join-Path (Join-Path $root $p1.Final) 'Video ficticio.mkv') -Algorithm SHA256).Hash -ne $videoSha) {
        throw 'Se modificó el destino preexistente.'
    }
    $results['colision_sin_sobrescribir'] = 'correcto'

    $f2 = Invoke-Fixture 'create'
    $fixtures += $f2
    $p7 = New-Stage 7 'Lease perdido antes del diario'
    $denied = Invoke-Bridge $p7 $f2 @{SimulateLeaseLossAfterFirstCheck=$true}
    if ($denied.estado -ne 'denegada_por_lease' -or
        $denied.codigo -ne 'lease_no_vigente_antes_de_mover') {
        throw 'La revalidación anterior al movimiento no bloqueó el lease perdido.'
    }
    Assert-NotPublished $p7
    $results['lease_perdido_entre_consultas'] = 'sin_publicar'

    $f3 = Invoke-Fixture 'create'
    $fixtures += $f3
    $p8 = New-Stage 8 'Lease perdido después de publicar'
    $needsReview = Invoke-Bridge $p8 $f3 @{SimulateLeaseLossAfterMove=$true}
    if ($needsReview.estado -ne 'requiere_revision' -or
        -not [IO.Directory]::Exists((Join-Path $root $p8.Final)) -or
        [IO.Directory]::Exists((Join-Path $root $p8.Stage))) {
        throw 'Una publicación ambigua se confirmó con lease perdido.'
    }
    $results['lease_perdido_despues_move'] = 'revision_sin_confirmar'

    $null = Invoke-Fixture 'expire' $f1.database
    $p9 = New-Stage 9 'Lease ya caducado'
    $denied = Invoke-Bridge $p9 $f1
    if ($denied.estado -ne 'denegada_por_lease') {
        throw 'Lease caducado obtuvo una publicación nueva.'
    }
    Assert-NotPublished $p9
    $results['lease_caducado_previamente'] = 'denegado'

    $f4 = Invoke-Fixture 'create'
    $fixtures += $f4
    $null = Invoke-Fixture 'reassign' $f4.database
    $p10 = New-Stage 10 'Propietario cambiado'
    $denied = Invoke-Bridge $p10 $f4
    if ($denied.estado -ne 'denegada_por_lease') {
        throw 'Se aceptó una tarea reasignada.'
    }
    Assert-NotPublished $p10
    $results['lease_reasignado'] = 'denegado'

    $f5 = Invoke-Fixture 'create'
    $fixtures += $f5
    $null = Invoke-Fixture 'revoke' $f5.database
    $p11 = New-Stage 11 'Verificación revocada'
    $denied = Invoke-Bridge $p11 $f5
    if ($denied.estado -ne 'denegada_por_lease') {
        throw 'Se aceptó una verificación revocada.'
    }
    Assert-NotPublished $p11
    $results['verificacion_revocada'] = 'denegada'

    $results | ConvertTo-Json -Compress
} finally {
    foreach ($f in $fixtures) {
        # This helper validates exact /tmp GUID name, marker and two test files.
        $null = Invoke-Fixture 'cleanup' $f.database
    }
    if ([IO.Directory]::Exists($root) -and
        [IO.Path]::GetDirectoryName($root) -ieq $public -and
        [IO.Path]::GetFileName($root) -cmatch '^viewtv-win-sandbox-[0-9a-f]{32}$' -and
        ([IO.DirectoryInfo]::new($root).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
        [IO.File]::Exists($rootMarker) -and
        [IO.File]::ReadAllText($rootMarker) -ceq $rootValue) {
        [IO.Directory]::Delete($root, $true)
    }
    if ([IO.Directory]::Exists($journal) -and
        [IO.Path]::GetDirectoryName($journal) -ieq $temp -and
        [IO.Path]::GetFileName($journal) -cmatch '^viewtv-broker-journal-[0-9a-f]{32}$' -and
        ([IO.DirectoryInfo]::new($journal).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
        [IO.File]::Exists($journalMarker) -and
        [IO.File]::ReadAllText($journalMarker) -ceq $journalValue) {
        [IO.Directory]::Delete($journal, $true)
    }
    if ($keyPath -and [IO.File]::Exists($keyPath)) {
        $keyFolder = [IO.Path]::GetDirectoryName($keyPath)
        if ([IO.Path]::GetDirectoryName($keyFolder) -ieq $temp -and
            [IO.Path]::GetFileName($keyFolder) -cmatch '^viewtv-test-key-[0-9a-f]{32}$') {
            [IO.Directory]::Delete($keyFolder, $true)
        }
    }
}
