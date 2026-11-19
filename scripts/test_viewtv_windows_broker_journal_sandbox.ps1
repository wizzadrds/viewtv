# VIEWTV: failure/replay tests of a Windows-only durable publication journal.
# Test-only. Creates and deletes ONLY its own marked GUID roots.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$public = [IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
$temp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
if ($public -ine 'C:\Users\Public') { throw 'Sandbox Windows obligatorio.' }
$root = Join-Path $public ('viewtv-win-sandbox-' + [Guid]::NewGuid().ToString('N'))
$journal = Join-Path $temp ('viewtv-broker-journal-' + [Guid]::NewGuid().ToString('N'))
$rootMarker = Join-Path $root '.viewtv-win-sandbox-only'
$journalMarker = Join-Path $journal '.viewtv-journal-only'
$rootMarkerValue = 'VIEWTV_WINDOWS_SANDBOX_ONLY_V1' + [char]10
$journalMarkerValue = 'VIEWTV_WINDOWS_JOURNAL_SANDBOX_V1' + [char]10
$keyPath = $null
$broker = Join-Path $PSScriptRoot 'viewtv_windows_broker_journal_sandbox.ps1'
. (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')
$results = [ordered]@{}

function New-TestStage([int]$number, [string]$final, [int]$expiry = 5) {
    $stageName = '.viewtv-stage-' + $number
    $stage = Join-Path $root $stageName
    [IO.Directory]::CreateDirectory($stage) | Out-Null
    $video = 'Video ficticio.mkv'
    $subtitle = 'Video ficticio.es.srt'
    [IO.File]::WriteAllText((Join-Path $stage $video), 'video ' + $number)
    [IO.File]::WriteAllText((Join-Path $stage $subtitle), 'subtitulo ' + $number)
    $hash = (Get-FileHash -LiteralPath (Join-Path $stage $video) -Algorithm SHA256).Hash
    $approval = New-ViewtvTestApproval -SandboxRoot $root -StageName $stageName -FinalName $final -KeyPath $keyPath -ExpiryMinutes $expiry
    return [pscustomobject]@{
        Stage = $stageName
        Final = $final
        Approval = $approval
        Hash = $hash
    }
}
function Invoke-TestBroker($job, [string]$mode = 'Publish', [string]$crash = '') {
    $args = @{
        SandboxRoot = $root; StageName = $job.Stage; FinalName = $job.Final
        ApprovalName = $job.Approval; KeyPath = $keyPath; JournalRoot = $journal
        Mode = $mode
    }
    if ($crash -eq 'AfterClaim') { $args.SimulateCrashAfterClaim = $true }
    if ($crash -eq 'AfterMove') { $args.SimulateCrashAfterMove = $true }
    $output = & $broker @args
    if ($null -ne $output) { return ($output | ConvertFrom-Json) }
}
function Must-Fail([scriptblock]$action) {
    $failed = $false
    try { & $action | Out-Null } catch { $failed = $true }
    if (-not $failed) { throw 'Una operación insegura no fue rechazada.' }
}
function Test-JournalRootMarker([string]$path, [string]$expectedParent, [string]$pattern, [string]$markerPath, [string]$value) {
    return (
        [IO.Directory]::Exists($path) -and
        [IO.Path]::GetDirectoryName($path) -ieq $expectedParent -and
        [IO.Path]::GetFileName($path) -cmatch $pattern -and
        ([IO.DirectoryInfo]::new($path).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
        [IO.File]::Exists($markerPath) -and
        [IO.File]::ReadAllText($markerPath) -ceq $value
    )
}

try {
    if ([IO.Directory]::Exists($root) -or [IO.Directory]::Exists($journal)) {
        throw 'Raíz aleatoria preexistente.'
    }
    [IO.Directory]::CreateDirectory($root) | Out-Null
    [IO.Directory]::CreateDirectory($journal) | Out-Null

    $me = [Security.Principal.WindowsIdentity]::GetCurrent().User
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
    foreach ($sid in @($me, $system, $admins)) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $sid, [Security.AccessControl.FileSystemRights]::FullControl,
            $inherit, [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow
        ))
    }
    [IO.Directory]::SetAccessControl($journal, $acl)
    if (-not (Get-Acl -LiteralPath $journal).AreAccessRulesProtected) {
        throw 'ACL del diario no confinada.'
    }
    [IO.File]::WriteAllText($rootMarker, $rootMarkerValue)
    [IO.File]::WriteAllText($journalMarker, $journalMarkerValue)
    $keyPath = New-ViewtvTestKey

    # Full publication and byte integrity.
    $job1 = New-TestStage 1 'Pelicula de diario'
    $answer = Invoke-TestBroker $job1
    if ($answer.estado -ne 'publicada_verificada' -or
        [IO.Directory]::Exists((Join-Path $root $job1.Stage)) -or
        (Get-FileHash -LiteralPath (Join-Path $root 'Pelicula de diario\Video ficticio.mkv') -Algorithm SHA256).Hash -ne $job1.Hash) {
        throw 'Publicación de grupo no confirmada.'
    }
    $results['primera_publicacion'] = 'verificada'

    # Same intent may be observed but NEVER moved twice.
    $again = Invoke-TestBroker $job1
    if ($again.estado -ne 'reutilizacion_bloqueada' -or
        $again.conciliacion -ne 'publicada_verificada') { throw 'Replay no bloqueado.' }
    $results['replay_despues_publicar'] = 'bloqueado'

    # Crash AFTER durable claim but BEFORE move.
    $job2 = New-TestStage 2 'Sin publicar'
    Must-Fail { Invoke-TestBroker $job2 'Publish' 'AfterClaim' }
    $check = Invoke-TestBroker $job2 'Reconcile'
    if ($check.estado -ne 'pendiente_de_publicacion' -or
        -not [IO.Directory]::Exists((Join-Path $root $job2.Stage)) -or
        [IO.Directory]::Exists((Join-Path $root $job2.Final))) {
        throw 'El crash previo perdió staging.'
    }
    $retry = Invoke-TestBroker $job2
    if ($retry.estado -ne 'reutilizacion_bloqueada' -or
        $retry.conciliacion -ne 'pendiente_de_publicacion') {
        throw 'Se repitió una publicación tras corte previo.'
    }
    $results['corte_despues_registro'] = 'conciliado_sin_repetir'

    # Crash AFTER Directory.Move but BEFORE caller gets a result.
    $job3 = New-TestStage 3 'Publicado sin respuesta'
    Must-Fail { Invoke-TestBroker $job3 'Publish' 'AfterMove' }
    $check = Invoke-TestBroker $job3 'Reconcile'
    $retry = Invoke-TestBroker $job3
    if ($check.estado -ne 'publicada_verificada' -or
        $retry.estado -ne 'reutilizacion_bloqueada' -or
        -not [IO.Directory]::Exists((Join-Path $root $job3.Final))) {
        throw 'El crash tras mover no se concilió.'
    }
    $results['corte_despues_move'] = 'conciliado_sin_repetir'

    # Changed signed plan after journal creation; never accept old intent.
    $job4 = New-TestStage 4 'Diario alterado'
    Must-Fail { Invoke-TestBroker $job4 'Publish' 'AfterClaim' }
    $recordPath = Join-Path $journal '.viewtv-intent-4.json'
    $record = [IO.File]::ReadAllText($recordPath) | ConvertFrom-Json
    $record.approval_sha256 = ('0' * 64)
    [IO.File]::WriteAllText($recordPath, ($record | ConvertTo-Json -Compress))
    $check = Invoke-TestBroker $job4 'Reconcile'
    $retry = Invoke-TestBroker $job4
    if ($check.estado -ne 'requiere_revision' -or
        $retry.estado -ne 'reutilizacion_bloqueada' -or
        [IO.Directory]::Exists((Join-Path $root $job4.Final))) {
        throw 'Diario alterado fue aceptado.'
    }
    $results['diario_corrupto'] = 'requiere_revision'

    # Already occupied destination; existing content untouched and journal retained.
    $job5 = New-TestStage 5 'Pelicula de diario'
    Must-Fail { Invoke-TestBroker $job5 }
    if (-not [IO.File]::Exists((Join-Path $journal '.viewtv-intent-5.json')) -or
        -not [IO.Directory]::Exists((Join-Path $root $job5.Stage)) -or
        (Get-FileHash -LiteralPath (Join-Path $root 'Pelicula de diario\Video ficticio.mkv') -Algorithm SHA256).Hash -ne $job1.Hash) {
        throw 'La colisión alteró contenido preexistente.'
    }
    $results['colision_destino'] = 'sin_sobrescritura'

    # Expired approval cannot create a durable intent.
    $job6 = New-TestStage 6 'Caducada' -1
    Must-Fail { Invoke-TestBroker $job6 }
    if ([IO.File]::Exists((Join-Path $journal '.viewtv-intent-6.json'))) {
        throw 'El diario registró una autorización caducada.'
    }
    $results['caducidad'] = 'sin_intencion'

    # No journal means no evidence of publication, read-only review.
    $job7 = New-TestStage 7 'Sin diario'
    $check = Invoke-TestBroker $job7 'Reconcile'
    if ($check.estado -ne 'requiere_revision' -or
        [IO.File]::Exists((Join-Path $journal '.viewtv-intent-7.json'))) {
        throw 'Se inventó una intención inexistente.'
    }
    $results['sin_diario'] = 'requiere_revision'

    # A forged or redirected journal root is rejected before any Move.
    Must-Fail {
        & $broker -SandboxRoot $root -StageName $job7.Stage -FinalName $job7.Final -ApprovalName $job7.Approval -KeyPath $keyPath -JournalRoot $temp | Out-Null
    }
    if ([IO.Directory]::Exists((Join-Path $root $job7.Final))) {
        throw 'La raíz de diario no autorizada publicó contenido.'
    }
    $results['ruta_diario_fuera_raiz'] = 'rechazada'

    # A durable journal must bind the SAME nonce as the signed approval.
    $job8 = New-TestStage 8 'Nonce cambiado'
    Must-Fail { Invoke-TestBroker $job8 'Publish' 'AfterClaim' }
    $noncePath = Join-Path $journal '.viewtv-intent-8.json'
    $nonceRecord = [IO.File]::ReadAllText($noncePath) | ConvertFrom-Json
    $nonceRecord.nonce = '0' * 32
    [IO.File]::WriteAllText($noncePath, ($nonceRecord | ConvertTo-Json -Compress))
    $nonceCheck = Invoke-TestBroker $job8 'Reconcile'
    if ($nonceCheck.estado -ne 'requiere_revision' -or
        [IO.Directory]::Exists((Join-Path $root $job8.Final))) {
        throw 'Se aceptó un nonce discordante.'
    }
    $results['nonce_diario_diferente'] = 'requiere_revision'

    # Two independent native Windows processes compete for the SAME stage.
    # Exactly one may claim the durable journal; neither may overwrite.
    $job9 = New-TestStage 9 'Carrera exclusiva'
    $jobs = @()
    try {
        for ($i = 0; $i -lt 2; $i++) {
            $jobs += Start-Job -ArgumentList @(
                $broker, $root, $journal, $keyPath,
                $job9.Stage, $job9.Final, $job9.Approval
            ) -ScriptBlock {
                param($scriptPath, $sandboxPath, $journalPath, $secretPath, $stage, $final, $approval)
                & $scriptPath -SandboxRoot $sandboxPath -StageName $stage -FinalName $final -ApprovalName $approval -KeyPath $secretPath -JournalRoot $journalPath -Mode Publish
            }
        }
        $null = $jobs | Wait-Job
        $responses = @()
        foreach ($windowsJob in $jobs) {
            if ($windowsJob.State -ne 'Completed') {
                $child = @($windowsJob.ChildJobs)[0]
                $reason = if ($child.JobStateInfo.Reason) { $child.JobStateInfo.Reason.GetType().Name + ': ' + $child.JobStateInfo.Reason.Message } else { 'sin razón registrada' }
                throw ('Proceso de carrera falló: ' + $reason)
            }
            $responses += (Receive-Job -Job $windowsJob -ErrorAction Stop | ConvertFrom-Json)
        }
        $successful = @($responses | Where-Object { $_.estado -eq 'publicada_verificada' })
        $blocked = @($responses | Where-Object {
            $_.estado -in @('reutilizacion_bloqueada', 'operacion_en_curso')
        })
        if ($successful.Count -ne 1 -or $blocked.Count -ne 1 -or
            -not [IO.File]::Exists((Join-Path $journal '.viewtv-intent-9.json')) -or
            [IO.Directory]::Exists((Join-Path $root $job9.Stage)) -or
            (Get-FileHash -LiteralPath (Join-Path $root 'Carrera exclusiva\Video ficticio.mkv') -Algorithm SHA256).Hash -ne $job9.Hash) {
            throw 'La carrera no mantuvo una sola publicación íntegra.'
        }
        $results['colision_simultanea_mismo_staging'] = 'una_publicacion'
    } finally {
        foreach ($windowsJob in $jobs) {
            if ($windowsJob.State -eq 'Running') { $null = $windowsJob | Stop-Job }
            $windowsJob | Remove-Job -Force
        }
    }

    $results | ConvertTo-Json -Compress
} finally {
    if (Test-JournalRootMarker $root $public '^viewtv-win-sandbox-[0-9a-f]{32}$' $rootMarker $rootMarkerValue) {
        [IO.Directory]::Delete($root, $true)
    }
    if (Test-JournalRootMarker $journal $temp '^viewtv-broker-journal-[0-9a-f]{32}$' $journalMarker $journalMarkerValue) {
        [IO.Directory]::Delete($journal, $true)
    }
    if ($keyPath -and [IO.File]::Exists($keyPath)) {
        $keyDirectory = [IO.Path]::GetDirectoryName($keyPath)
        if ([IO.Path]::GetDirectoryName($keyDirectory) -ieq $temp -and
            [IO.Path]::GetFileName($keyDirectory) -cmatch '^viewtv-test-key-[0-9a-f]{32}$') {
            [IO.Directory]::Delete($keyDirectory, $true)
        }
    }
}
