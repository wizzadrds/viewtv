# VIEWTV - Journal of test-only Windows publications; NOT a production broker.
# Creates an exclusive durable intent before Directory.Move; never retries a claimed intent.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SandboxRoot,
    [Parameter(Mandatory=$true)][string]$StageName,
    [Parameter(Mandatory=$true)][string]$FinalName,
    [Parameter(Mandatory=$true)][string]$ApprovalName,
    [Parameter(Mandatory=$true)][string]$KeyPath,
    [Parameter(Mandatory=$true)][string]$JournalRoot,
    [ValidateSet('Publish','Reconcile')][string]$Mode = 'Publish',
    [switch]$SimulateCrashAfterClaim,
    [switch]$SimulateCrashAfterMove
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')

function Assert-TestJournalRoot([string]$location) {
    $temp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
    $root = [IO.Path]::GetFullPath($location).TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($root) -ine $temp -or
        [IO.Path]::GetFileName($root) -cnotmatch '^viewtv-broker-journal-[a-f0-9]{32}$' -or
        -not [IO.Directory]::Exists($root)) {
        throw 'Diario fuera del sandbox de pruebas.'
    }
    $info = [IO.DirectoryInfo]::new($root)
    if (($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Diario redirigido.'
    }
    $marker = [IO.FileInfo]::new((Join-Path $root '.viewtv-journal-only'))
    if (-not $marker.Exists -or
        ($marker.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        [IO.File]::ReadAllText($marker.FullName) -cne ("VIEWTV_WINDOWS_JOURNAL_SANDBOX_V1" + [char]10)) {
        throw 'Marcador del diario inválido.'
    }
    $acl = Get-Acl -LiteralPath $root
    if (-not $acl.AreAccessRulesProtected) {
        throw 'El diario no tiene ACL protegida.'
    }
    $me = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $system = [Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid, $null
    ).Value
    $admins = [Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid, $null
    ).Value
    $allowed = @($me, $system, $admins)
    $rules = @($acl.GetAccessRules(
        $true, $true, [Security.Principal.SecurityIdentifier]
    ))
    if ($rules.Count -ne 3) {
        throw 'El diario debe tener exactamente tres identidades ACL.'
    }
    foreach ($rule in $rules) {
        if ($rule.IsInherited -or
            $rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            $allowed -cnotcontains $rule.IdentityReference.Value) {
            throw 'ACL del diario no confinada.'
        }
    }
    return $root
}

function Assert-TestSandbox([string]$location) {
    $public = [IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
    $root = [IO.Path]::GetFullPath($location).TrimEnd('\')
    if ($public -ine 'C:\Users\Public' -or
        [IO.Path]::GetDirectoryName($root) -ine $public -or
        [IO.Path]::GetFileName($root) -cnotmatch '^viewtv-win-sandbox-[0-9a-f]{32}$' -or
        -not [IO.Directory]::Exists($root)) {
        throw 'Solo se admiten sandboxes nuevos de Windows.'
    }
    $info = [IO.DirectoryInfo]::new($root)
    if (($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Sandbox redirigido.'
    }
    $marker = [IO.FileInfo]::new((Join-Path $root '.viewtv-win-sandbox-only'))
    if (-not $marker.Exists -or
        ($marker.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        [IO.File]::ReadAllText($marker.FullName) -cne ("VIEWTV_WINDOWS_SANDBOX_ONLY_V1" + [char]10)) {
        throw 'Sandbox sin marcador válido.'
    }
    return $root
}

function Get-IntentDigest([string]$approvalPath) {
    $bytes = [IO.File]::ReadAllBytes($approvalPath)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Read-Journal([string]$path, [string]$expectedStage, [string]$digest, [string]$expectedSandbox, [string]$expectedNonce) {
    $info = [IO.FileInfo]::new($path)
    if (-not $info.Exists -or $info.Length -lt 2 -or $info.Length -gt 4096 -or
        ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Registro de diario inválido.'
    }
    $record = [IO.File]::ReadAllText($path) | ConvertFrom-Json
    if ($record.version -ne 1 -or $record.stage -cne $expectedStage -or
        $record.approval_sha256 -cne $digest -or
        $record.sandbox -cne $expectedSandbox -or
        [string]$record.nonce -cne $expectedNonce -or
        [string]$record.nonce -cnotmatch '^[a-f0-9]{32}$') {
        throw 'El registro durable no corresponde con el plan.'
    }
    return $record
}

$root = Assert-TestSandbox $SandboxRoot
$journal = Assert-TestJournalRoot $JournalRoot
if ($StageName -cnotmatch '^\.viewtv-stage-[1-9][0-9]{0,9}$' -or
    $ApprovalName -cne ('.viewtv-approval-' + $StageName.Substring('.viewtv-stage-'.Length) + '.json')) {
    throw 'Identidad de staging o autorización inválida.'
}
$approvalPath = Join-Path $root $ApprovalName
if (-not [IO.File]::Exists($approvalPath)) {
    throw 'No hay autorización firmada.'
}
$approvalInfo = [IO.FileInfo]::new($approvalPath)
if ($approvalInfo.Length -gt 32768 -or
    ($approvalInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'Autorización insegura.'
}
$envelope = [IO.File]::ReadAllText($approvalPath) | ConvertFrom-Json
$intent = $envelope.payload | ConvertFrom-Json
$nonce = [string]$intent.nonce
if ($nonce -cnotmatch '^[a-f0-9]{32}$') { throw 'Nonce inválido.' }
$stageId = $StageName.Substring('.viewtv-stage-'.Length)
$journalPath = Join-Path $journal ('.viewtv-intent-' + $stageId + '.json')
$digest = Get-IntentDigest $approvalPath

function Inspect-PublishedIntent {
    try {
        $null = Read-Journal $journalPath $StageName $digest ([IO.Path]::GetFileName($root)) $nonce
        $result = & (Join-Path $PSScriptRoot 'viewtv_windows_reconcile_sandbox.ps1') -SandboxRoot $root -StageName $StageName -FinalName $FinalName -ApprovalName $ApprovalName -KeyPath $KeyPath | ConvertFrom-Json
        return [pscustomobject]@{
            estado = [string]$result.estado
            motivo = [string]$result.motivo
            lectura_solamente = $true
            registro_durable = $true
        }
    } catch {
        return [pscustomobject]@{
            estado = 'requiere_revision'
            motivo = 'diario_o_plan_no_verificable'
            lectura_solamente = $true
            registro_durable = $true
        }
    }
}

if ($Mode -eq 'Reconcile') {
    if (-not [IO.File]::Exists($journalPath)) {
        [pscustomobject]@{estado='requiere_revision';motivo='sin_intencion_durable';lectura_solamente=$true;registro_durable=$false} | ConvertTo-Json -Compress
    } else {
        Inspect-PublishedIntent | ConvertTo-Json -Compress
    }
    return
}

# Process-local window: serialize the hash/Move critical section by a
# FileShare.None handle in the protected Windows journal directory. A contender
# MUST NOT hash the same stage while another process may be moving it.
$lockPath = Join-Path $journal ('.viewtv-lock-' + $stageId)
if ([IO.File]::Exists($lockPath)) {
    $lockInfo = [IO.FileInfo]::new($lockPath)
    if (($lockInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Bloqueo de diario redirigido.'
    }
}
try {
    $stageLock = [IO.FileStream]::new(
        $lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::None
    )
} catch [IO.IOException] {
    # Another process owns the exclusive handle. No stage reads and no Move.
    [pscustomobject]@{
        estado = 'operacion_en_curso'
        lectura_solamente = $true
    } | ConvertTo-Json -Compress
    return
}
try {
# A known journal entry permanently forbids a new movement. Reconciliation
# is read-only and NEVER turns a retry into an automatic publication.
if ([IO.File]::Exists($journalPath)) {
    $observed = Inspect-PublishedIntent
    [pscustomobject]@{
        estado = 'reutilizacion_bloqueada'
        conciliacion = $observed.estado
        lectura_solamente = $true
    } | ConvertTo-Json -Compress
    return
}
try {
    if (-not (Assert-ViewtvTestApproval -SandboxRoot $root -StageName $StageName -FinalName $FinalName -ApprovalName $ApprovalName -KeyPath $KeyPath -Location Stage)) {
        throw 'Autorización de publicación no válida.'
    }
} catch {
    # Another Windows process can move stage after our first journal check.
    # If it has claimed the journal, reconcile; never mistake this race
    # for permission to create a second intent or move an absent stage.
    if ([IO.File]::Exists($journalPath)) {
        $observed = Inspect-PublishedIntent
        [pscustomobject]@{
            estado = 'reutilizacion_bloqueada'
            conciliacion = $observed.estado
            lectura_solamente = $true
        } | ConvertTo-Json -Compress
        return
    }
    throw
}
# This is a test-only proof of intent. No SQLite lease, Windows service
# identity or independent authority is connected yet.
$record = [ordered]@{
    version = 1
    sandbox = [IO.Path]::GetFileName($root)
    stage = $StageName
    nonce = $nonce
    approval_sha256 = $digest
    created_utc = [DateTime]::UtcNow.ToString('o')
} | ConvertTo-Json -Compress
$bytes = [Text.Encoding]::UTF8.GetBytes($record)
try {
    $stream = [IO.FileStream]::new(
        $journalPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write,
        [IO.FileShare]::None, 4096, [IO.FileOptions]::WriteThrough
    )
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
} catch [IO.IOException] {
    # The competing process may have created the entry. Never issue Move.
    $observed = Inspect-PublishedIntent
    [pscustomobject]@{
        estado = 'reutilizacion_bloqueada'
        conciliacion = $observed.estado
        lectura_solamente = $true
    } | ConvertTo-Json -Compress
    return
}
if ($SimulateCrashAfterClaim) {
    throw 'CORTE_SIMULADO_DESPUES_DEL_REGISTRO'
}
$null = & (Join-Path $PSScriptRoot 'viewtv_windows_publish_sandbox.ps1') -SandboxRoot $root -StageName $StageName -FinalName $FinalName -ApprovalName $ApprovalName -KeyPath $KeyPath
if ($SimulateCrashAfterMove) {
    throw 'CORTE_SIMULADO_DESPUES_DE_MOVER'
}
$observed = Inspect-PublishedIntent
if ($observed.estado -ne 'publicada_verificada') {
    throw 'Publicación de resultado ambiguo: requiere revisión.'
}
[pscustomobject]@{
    estado = 'publicada_verificada'
    motor = 'Windows_Directory_Move'
    diario = 'persistido'
    conciliacion = 'solo_lectura'
} | ConvertTo-Json -Compress
} finally {
    $stageLock.Dispose()
}
