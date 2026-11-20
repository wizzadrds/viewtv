# VIEWTV 0013 — Local Windows named-pipe admission prototype, SANDBOX ONLY.
# No NTFS publication, no qBittorrent, no SQLite production, no Windows service.
[CmdletBinding()]
param(
    [ValidateSet('Library','Server','Client')][string]$Mode='Library',
    [string]$PipeName,
    [string]$JournalRoot,
    [string]$KeyPath,
    [string]$EnvelopeText
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')

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
function Test-ViewtvBrokerTestMessage([string]$Raw,[string]$TestKeyPath,[string]$Root) {
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
        if ($intent.version -ne 1 -or
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
        $nonceFile=Join-Path $Root ('.viewtv-nonce-'+[string]$intent.nonce+'.json')
        # Reserve an authenticated nonce exclusively before acknowledging it.
        # Durable retry rejection survives even if the broker crashes after claim.
        $message=[ordered]@{
            version=1
            nonce=[string]$intent.nonce
            manifest_sha256=[string]$intent.manifest_sha256
            download_id=[long]$intent.download_id
            attempt=[int]$intent.attempt
            reserved_utc=$now.ToString('o')
        } | ConvertTo-Json -Compress
        $bytes=[Text.Encoding]::UTF8.GetBytes($message)
        try {
            $stream=[IO.FileStream]::new(
                $nonceFile,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,
                [IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough)
        } catch [IO.IOException] {
            if ([IO.File]::Exists($nonceFile)) { return 'replay_bloqueado' }
            return 'requiere_revision'
        }
        try {
            $stream.Write($bytes,0,$bytes.Length)
            $stream.Flush($true)
        } finally {
            $stream.Dispose()
        }
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
if($Mode -eq 'Library'){ return }
if ($PipeName -cnotmatch '^viewtv-test-pipe-[a-f0-9]{32}$') {
    throw 'Nombre de tubería fuera de sandbox.'
}
if($Mode -eq 'Client') {
    $pipe=[IO.Pipes.NamedPipeClientStream]::new(
        '.',$PipeName,[IO.Pipes.PipeDirection]::InOut)
    try {
        $pipe.Connect(5000)
        $writer=[IO.BinaryWriter]::new($pipe,[Text.UTF8Encoding]::new($false),$true)
        $reader=[IO.BinaryReader]::new($pipe,[Text.Encoding]::UTF8,$true)
        try {
            $bytes=[Text.Encoding]::UTF8.GetBytes($EnvelopeText)
            $writer.Write([int]$bytes.Length)
            # For an oversize request the server rejects using the prefix
            # alone. Do not fill the pipe beyond its bounded buffer.
            if($bytes.Length -le 8192){
                $writer.Write($bytes)
            }
            $writer.Flush()
            $size=$reader.ReadInt32()
            if($size -lt 2 -or $size -gt 256) {
                throw 'Respuesta de broker inválida.'
            }
            $reply=$reader.ReadBytes($size)
            if($reply.Length -ne $size) {throw 'Respuesta incompleta.'}
            [Text.Encoding]::UTF8.GetString($reply)
        } finally { $writer.Dispose(); $reader.Dispose() }
    } finally { $pipe.Dispose() }
    return
}
$root=Assert-ViewtvBrokerTestJournal $JournalRoot
$null=Assert-TestKeyPath $KeyPath
$security=New-ViewtvBrokerPipeAcl
$pipe=[IO.Pipes.NamedPipeServerStream]::new(
    $PipeName,[IO.Pipes.PipeDirection]::InOut,1,
    [IO.Pipes.PipeTransmissionMode]::Byte,[IO.Pipes.PipeOptions]::None,
    4096,4096,$security)
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
    $pipe.WaitForConnection()
    $reader=[IO.BinaryReader]::new($pipe,[Text.Encoding]::UTF8,$true)
    $writer=[IO.BinaryWriter]::new($pipe,[Text.UTF8Encoding]::new($false),$true)
    try {
        $size=$reader.ReadInt32()
        $state='no_autorizada'
        if($size -ge 2 -and $size -le 8192){
            $raw=$reader.ReadBytes($size)
            if($raw.Length -eq $size){
                $state=Test-ViewtvBrokerTestMessage (
                    [Text.Encoding]::UTF8.GetString($raw)) $KeyPath $root
            }
        }
        $answer=[ordered]@{estado=$state;publicacion_iniciada=$false} |
            ConvertTo-Json -Compress
        $bytes=[Text.Encoding]::UTF8.GetBytes($answer)
        $writer.Write([int]$bytes.Length)
        $writer.Write($bytes)
        $writer.Flush()
    } finally { $reader.Dispose(); $writer.Dispose() }
} finally { $pipe.Dispose() }
