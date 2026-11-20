# VIEWTV 0013 — Local Windows named-pipe admission prototype, SANDBOX ONLY.
# No NTFS publication, no real qBittorrent, no SQLite production or service.
[CmdletBinding()]
param(
    [ValidateSet('Library','Server','Client')][string]$Mode='Library',
    [string]$PipeName,
    [string]$JournalRoot,
    [string]$KeyPath,
    [string]$EnvelopeText,
    [switch]$RequireSandboxLease,
    [string]$LeaseDatabase,
    [switch]$RequireSandboxTorrent,
    [string]$TorrentFixtureUrl,
    [switch]$TestCrashAfterDownloadClaim,
    [int]$AcceptTimeoutMs=5000,
    [int]$ReadTimeoutMs=4000
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_pipe_response_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_pipe_io_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_pipe_first_instance_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_pipe_lease_auth_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_pipe_torrent_auth_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_v3_journal_audit_sandbox.ps1')

function Assert-ViewtvBrokerTestJournal([string]$path) {
    $temp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
    $root = [IO.Path]::GetFullPath($path).TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($root) -ine $temp -or
        [IO.Path]::GetFileName($root) -cnotmatch '^viewtv-pipe-broker-[a-f0-9]{32}$' -or
        -not [IO.Directory]::Exists($root) -or
        ([IO.DirectoryInfo]::new($root).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Diario de autorización fuera de sandbox.'
    }
    $marker=Join-Path $root '.viewtv-pipe-only'
    if (-not [IO.File]::Exists($marker) -or
        ([IO.FileInfo]::new($marker).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        [IO.File]::ReadAllText($marker) -cne ('VIEWTV_PIPE_BROKER_TEST_ONLY_V1'+[char]10)) {
        throw 'Marcador de diario no válido.'
    }
    $acl=Get-Acl -LiteralPath $root
    $me=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null).Value
    $admins=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null).Value
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if (-not $acl.AreAccessRulesProtected -or $rules.Count -ne 3) {
        throw 'ACL de diario demasiado amplia.'
    }
    foreach($entry in $rules) {
        if ($entry.IsInherited -or $entry.AccessControlType -ne 'Allow' -or
            @($me,$system,$admins) -cnotcontains $entry.IdentityReference.Value) {
            throw 'ACL de diario no confinada.'
        }
    }
    return $root
}
function New-ViewtvBrokerTestEnvelope([string]$PayloadText,[string]$TestKeyPath) {
    $key=Assert-TestKeyPath $TestKeyPath
    $h=[Security.Cryptography.HMACSHA256]::new($key)
    try {
        $mac=[Convert]::ToBase64String(
            $h.ComputeHash([Text.Encoding]::UTF8.GetBytes($PayloadText)))
    } finally { $h.Dispose() }
    return ([ordered]@{payload=$PayloadText;signature=$mac} |
        ConvertTo-Json -Compress)
}
function Reserve-ViewtvBrokerTestClaim([string]$Path,[byte[]]$Bytes) {
    # Caller has already authenticated the envelope and verified the marked
    # broker-only journal. CreateNew is the inter-process serialization point.
    # Never delete a partial claim: after a crash it must fail closed.
    $stream=$null
    try {
        $stream=[IO.FileStream]::new(
            $Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,
            [IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough)
        $stream.Write($Bytes,0,$Bytes.Length)
        $stream.Flush($true)
        return 'reservada'
    } catch [IO.IOException] {
        if([IO.File]::Exists($Path)){return 'replay_bloqueado'}
        return 'requiere_revision'
    } catch {
        return 'requiere_revision'
    } finally {
        if($null -ne $stream){$stream.Dispose()}
    }
}
function Test-ViewtvBrokerTestMessage([string]$Raw,[string]$TestKeyPath,[string]$Root,[string]$LeaseDatabase='',[string]$TorrentFixtureUrl='',[bool]$TestCrashAfterDownloadClaim=$false) {
    # The caller must have validated Root + ACL BEFORE touching the ledger.
    if ([Text.Encoding]::UTF8.GetByteCount($Raw) -gt 8192) {
        return 'no_autorizada'
    }
    try {
        $outer=$Raw | ConvertFrom-Json
        if (@($outer.PSObject.Properties.Name).Count -ne 2 -or
            $outer.payload -isnot [string] -or
            $outer.signature -isnot [string] -or
            @($outer.PSObject.Properties.Name) -cnotcontains 'payload' -or
            @($outer.PSObject.Properties.Name) -cnotcontains 'signature') {
            return 'no_autorizada'
        }
        $key=Assert-TestKeyPath $TestKeyPath
        $h=[Security.Cryptography.HMACSHA256]::new($key)
        try {
            $expected=$h.ComputeHash([Text.Encoding]::UTF8.GetBytes($outer.payload))
        } finally { $h.Dispose() }
        $actual=[Convert]::FromBase64String($outer.signature)
        if ($actual.Length -ne $expected.Length) { return 'no_autorizada' }
        $difference=0
        for($i=0;$i -lt $actual.Length;$i++){
            $difference=$difference -bor ($expected[$i] -bxor $actual[$i])
        }
        if ($difference -ne 0) { return 'no_autorizada' }
        $intent=$outer.payload | ConvertFrom-Json
        $expectedKeys=@('version','download_id','attempt','worker','sandbox',
          'stage','final','manifest_sha256','nonce','expires_utc')
        if($LeaseDatabase){$expectedKeys+=,'torrent_hash'}
        if (@($intent.PSObject.Properties.Name).Count -ne $expectedKeys.Count) {
            return 'no_autorizada'
        }
        foreach($keyName in $expectedKeys) {
            if (@($intent.PSObject.Properties.Name) -cnotcontains $keyName) {
                return 'no_autorizada'
            }
        }
        $expiry=[DateTime]::ParseExact([string]$intent.expires_utc,'o',
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
        $now=[DateTime]::UtcNow
        $idNumeric=($intent.download_id -is [int] -or
            $intent.download_id -is [long])
        $attemptNumeric=($intent.attempt -is [int] -or
            $intent.attempt -is [long])
        $expectedVersion=$(if($TorrentFixtureUrl){3}elseif($LeaseDatabase){2}else{1})
        if ($intent.version -ne $expectedVersion -or
            -not $idNumeric -or
            -not $attemptNumeric -or
            [long]$intent.download_id -le 0 -or
            [long]$intent.attempt -notin @(1,2,3) -or
            [string]$intent.worker -cnotmatch '^[A-Za-z0-9_-]{1,128}$' -or
            [string]$intent.sandbox -cnotmatch '^viewtv-win-sandbox-[a-f0-9]{32}$' -or
            [string]$intent.stage -cnotmatch '^\.viewtv-stage-[1-9][0-9]{0,9}$' -or
            [string]$intent.final -cnotmatch '^[A-Za-z0-9][A-Za-z0-9 .()_-]{0,100}$' -or
            [string]$intent.final -match '[. ]$' -or
            [string]$intent.final -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:[ .]|$)' -or
            [string]$intent.manifest_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
            [string]$intent.nonce -cnotmatch '^[a-f0-9]{32}$' -or
            $expiry -le $now -or $expiry -gt $now.AddMinutes(5)) {
            return 'no_autorizada'
        }
        # In strict v3 mode a single corrupt/orphaned journal entry stops
        # ALL new admissions in this journal across process restarts.
        # The audit only reads: it NEVER removes, truncates or fixes claims.
        if($TorrentFixtureUrl){
            try {
                $null=Assert-ViewtvSandboxV3JournalHealthy $Root $TestKeyPath
            } catch {
                return 'requiere_revision'
            }
        }
        # Lease gate is mandatory for v2/v3 admission before reservation;
        # the v3 fake-torrent gate follows it. Any failure reserves nothing.
        if($LeaseDatabase -and (
            [string]$intent.torrent_hash -cnotmatch '^(?:[a-f0-9]{40}|[a-f0-9]{64})$' -or
            -not (Test-ViewtvBrokerSandboxLease $LeaseDatabase `
                ([long]$intent.download_id) ([string]$intent.worker) `
                ([int]$intent.attempt) ([string]$intent.torrent_hash)))){
            return 'no_autorizada'
        }
        # Dual-gate sandbox mode: the server decides the fixture source.
        # A valid lease alone cannot authorize a claim in v3 mode.
        if($TorrentFixtureUrl){
            $guid=([string]$intent.sandbox).Substring('viewtv-win-sandbox-'.Length)
            if(-not (Test-ViewtvBrokerSandboxTorrent $TorrentFixtureUrl $guid `
                ([long]$intent.download_id) ([string]$intent.torrent_hash))){
                return 'no_autorizada'
            }
        }
        $nonceFile=Join-Path $Root ('.viewtv-nonce-'+[string]$intent.nonce+'.json')
        $downloadFile=Join-Path $Root (
            '.viewtv-download-'+[long]$intent.download_id+'.json')
        # A reused nonce may refer to a *different* download. Reject it
        # before consuming another download claim if already visible.
        # This early check is advisory; the later CreateNew is authoritative.
        if([IO.File]::Exists($nonceFile)){return 'replay_bloqueado'}
        # The download claim MUST be first: after a crash between files, a
        # missing nonce can never authorize another attempt for this download.
        # Never remove a partial claim on errors; require manual review.
        $downloadClaim=[ordered]@{
            version=$expectedVersion
            download_id=[long]$intent.download_id
            attempt=[int]$intent.attempt
            worker=[string]$intent.worker
            sandbox=[string]$intent.sandbox
            stage=[string]$intent.stage
            final=[string]$intent.final
            manifest_sha256=[string]$intent.manifest_sha256
            nonce=[string]$intent.nonce
            reserved_utc=$now.ToString('o')
        }
        if($LeaseDatabase){
            $downloadClaim['torrent_hash']=[string]$intent.torrent_hash
        }
        if($TorrentFixtureUrl){
            # Sign the exact canonical admission record with domain
            # separation; only the test broker's key may issue it.
            $body=$downloadClaim|ConvertTo-Json -Compress
            $downloadClaim['claim_hmac']=Get-ViewtvV3ClaimHmac $body $TestKeyPath
        }
        $downloadRecord=$downloadClaim | ConvertTo-Json -Compress
        $downloadState=Reserve-ViewtvBrokerTestClaim $downloadFile (
            [Text.Encoding]::UTF8.GetBytes($downloadRecord))
        if($downloadState -cne 'reservada'){return $downloadState}
        if($TestCrashAfterDownloadClaim){
            # Destructive fault injection ONLY in a separate, marked
            # v3 test-server process. The flushed download reservation
            # survives; the nonce is intentionally never written.
            # Never enable in a normal broker or interactive PowerShell.
            [Environment]::Exit(73)
        }
        # Nonce remains a second, independent replay gate. A failure here
        # leaves the download claimed (conservative, never automatically
        # retried or refunded).
        $nonceRecord=[ordered]@{
            version=1
            nonce=[string]$intent.nonce
            manifest_sha256=[string]$intent.manifest_sha256
            download_id=[long]$intent.download_id
            attempt=[int]$intent.attempt
            reserved_utc=$now.ToString('o')
        } | ConvertTo-Json -Compress
        $nonceState=Reserve-ViewtvBrokerTestClaim $nonceFile (
            [Text.Encoding]::UTF8.GetBytes($nonceRecord))
        if($nonceState -cne 'reservada'){return $nonceState}
        return 'intencion_registrada_sin_publicar'
    } catch {
        return 'no_autorizada'
    }
}
function New-ViewtvBrokerPipeAcl {
    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null)
    $admins=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null)
    $acl=[IO.Pipes.PipeSecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    foreach($entry in @(
        @($sid,[IO.Pipes.PipeAccessRights]::ReadWrite),
        @($system,[IO.Pipes.PipeAccessRights]::FullControl),
        @($admins,[IO.Pipes.PipeAccessRights]::FullControl)
    )) {
        $acl.AddAccessRule([IO.Pipes.PipeAccessRule]::new(
            $entry[0],$entry[1],[Security.AccessControl.AccessControlType]::Allow))
    }
    return $acl
}
if($TestCrashAfterDownloadClaim -and
   ($Mode -cne 'Server' -or -not $RequireSandboxLease -or
    -not $RequireSandboxTorrent -or -not $LeaseDatabase -or
    -not $TorrentFixtureUrl)){
    throw 'La interrupción de prueba solo se permite en servidor v3 de sandbox.'
}
if($Mode -eq 'Library'){ return }
if($Mode -ne 'Server' -and ($RequireSandboxLease -or $LeaseDatabase -or
    $RequireSandboxTorrent -or $TorrentFixtureUrl)){
    throw 'El lease solo puede configurarlo el servidor de prueba.'
}
if($Mode -eq 'Server'){
    if(($RequireSandboxLease -and
       $LeaseDatabase -cnotmatch '^/tmp/viewtv-lease-gate-[a-f0-9]{32}/organization\.sqlite3$') -or
       (-not $RequireSandboxLease -and $LeaseDatabase) -or
       ($RequireSandboxTorrent -and (-not $RequireSandboxLease -or
           $TorrentFixtureUrl -cnotmatch '^http://127\.0\.0\.1:([0-9]{5})$')) -or
       (-not $RequireSandboxTorrent -and $TorrentFixtureUrl)){
        throw 'Configuración de lease incompleta o fuera de sandbox.'
    }
}
if($Mode -eq 'Server' -and $RequireSandboxTorrent) {
    $urlMatch=[regex]::Match($TorrentFixtureUrl,
        '^http://127\.0\.0\.1:([0-9]{5})$')
    if(-not $urlMatch.Success -or
       [int]$urlMatch.Groups[1].Value -lt 49152 -or
       [int]$urlMatch.Groups[1].Value -gt 65535){
        throw 'Fuente HTTP del torrent fuera del sandbox de loopback.'
    }
}
if ($PipeName -cnotmatch '^viewtv-test-pipe-[a-f0-9]{32}$') {
    throw 'Nombre de tubería fuera de sandbox.'
}
if($Mode -eq 'Client') {
    # Never trust a response unless the client can authenticate its HMAC.
    $null=Assert-TestKeyPath $KeyPath
    $pipe=[IO.Pipes.NamedPipeClientStream]::new(
        '.',$PipeName,[IO.Pipes.PipeDirection]::InOut,
        [IO.Pipes.PipeOptions]::Asynchronous)
    try {
        $pipe.Connect(5000)
        $writer=[IO.BinaryWriter]::new($pipe,[Text.UTF8Encoding]::new($false),$true)
        $reader=[IO.BinaryReader]::new($pipe,[Text.Encoding]::UTF8,$true)
        try {
            $challenge=New-ViewtvBrokerTestChallenge
            $writer.Write($challenge)
            $bytes=[Text.Encoding]::UTF8.GetBytes($EnvelopeText)
            $writer.Write([int]$bytes.Length)
            # For an oversize request the server rejects using the prefix
            # alone. Do not fill the pipe beyond its bounded buffer.
            if($bytes.Length -le 8192){
                $writer.Write($bytes)
            }
            $writer.Flush()
            $sizeBuffer=Read-ViewtvPipeTestExact $pipe 4 4000
            $size=[BitConverter]::ToInt32($sizeBuffer,0)
            if($size -lt 2 -or $size -gt 2048) {
                throw 'Respuesta de broker inválida.'
            }
            $reply=Read-ViewtvPipeTestExact $pipe $size 4000
            if($reply.Length -ne $size) {throw 'Respuesta incompleta.'}
            $authenticated=Assert-ViewtvBrokerTestSignedResponse (
                [Text.Encoding]::UTF8.GetString($reply)) $challenge $(
                if($bytes.Length -le 8192){$EnvelopeText}else{''}
            ) $KeyPath
            $authenticated | ConvertTo-Json -Compress
        } finally { $writer.Dispose(); $reader.Dispose() }
    } finally { $pipe.Dispose() }
    return
}
if ($AcceptTimeoutMs -lt 250 -or $AcceptTimeoutMs -gt 15000 -or
    $ReadTimeoutMs -lt 250 -or $ReadTimeoutMs -gt 15000) {
    throw 'Timeouts de broker fuera del rango permitido.'
}
$root=Assert-ViewtvBrokerTestJournal $JournalRoot
$null=Assert-TestKeyPath $KeyPath
$security=New-ViewtvBrokerPipeAcl
# Native CreateNamedPipeW with FILE_FLAG_FIRST_PIPE_INSTANCE:
# refuse starting if another process owns this pipe name already.
$pipe=New-ViewtvBrokerNativeFirstPipe $PipeName $security
try {
    $actualAcl=$pipe.GetAccessControl()
    $rules=@($actualAcl.GetAccessRules(
        $true,$true,[Security.Principal.SecurityIdentifier]))
    $me=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null).Value
    $admins=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null).Value
    if (-not $actualAcl.AreAccessRulesProtected -or $rules.Count -ne 3) {
        throw 'DACL de tubería incorrecta.'
    }
    foreach($entry in $rules){
        if($entry.IsInherited -or $entry.AccessControlType -ne 'Allow' -or
           @($me,$system,$admins) -cnotcontains $entry.IdentityReference.Value){
            throw 'Identidad de tubería no autorizada.'
        }
    }
    if (-not $pipe.WaitForConnectionAsync().Wait($AcceptTimeoutMs)) {
        return  # No connection -> no nonce, no publication, no live process.
    }
    $reader=[IO.BinaryReader]::new($pipe,[Text.Encoding]::UTF8,$true)
    $writer=[IO.BinaryWriter]::new($pipe,[Text.UTF8Encoding]::new($false),$true)
    try {
        $challenge=Read-ViewtvPipeTestExact $pipe 32 $ReadTimeoutMs
        $frame=Read-ViewtvPipeTestFrame $pipe $ReadTimeoutMs
        $state='no_autorizada'
        $request=''
        if(-not $frame.TooLargeOrInvalid) {
            $request=[Text.Encoding]::UTF8.GetString($frame.Data)
            $state=Test-ViewtvBrokerTestMessage $request $KeyPath $root $(if($RequireSandboxLease){$LeaseDatabase}else{''}) $(if($RequireSandboxTorrent){$TorrentFixtureUrl}else{''}) ([bool]$TestCrashAfterDownloadClaim)
        }
        $answer=New-ViewtvBrokerTestSignedResponse $state $challenge $request $KeyPath
        $bytes=[Text.Encoding]::UTF8.GetBytes($answer)
        $writer.Write([int]$bytes.Length)
        $writer.Write($bytes)
        $writer.Flush()
    } finally { $reader.Dispose(); $writer.Dispose() }
} catch [TimeoutException] {
    # An idle or partial client is dropped without reserving a nonce.
    return
} catch [IO.EndOfStreamException] {
    return
} finally { $pipe.Dispose() }
