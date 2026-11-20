# VIEWTV 0013 — pre-rename lease + fake-torrent authority (GUID sandbox only).
# The config is broker-private (never read URL/DB from copy worker payload).
# NOT a production authority, API, broker service or NTFS/SQLite transaction.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_copy_acl_gate_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_pipe_lease_auth_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_pipe_torrent_auth_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_v3_claim_gate_sandbox.ps1')

function Assert-ViewtvSandboxFinalGate(
    [string]$SandboxRoot,[string]$Vault,[string]$StageName,
    [string]$FinalName,[string]$ApprovalName,[string]$KeyPath
) {
    $root=[IO.Path]::GetFullPath($SandboxRoot).TrimEnd('\')
    $root=Assert-ViewtvRestrictedSandboxPath $root $root
    $vault=Assert-ViewtvRestrictedSandboxPath $root $Vault
    if([IO.Path]::GetDirectoryName($vault) -ine $root -or
       [IO.Path]::GetFileName($vault) -cne '.viewtv-broker-handoff'){
        throw 'Cámara de broker no reconocida.'
    }
    $broker=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $file=Assert-ViewtvRestrictedSandboxPath $root (
        Join-Path $vault '.viewtv-final-authority.json')
    $info=[IO.FileInfo]::new($file)
    if(-not $info.Exists -or $info.Length -lt 280 -or $info.Length -gt 2048 -or
       ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
        throw 'Configuración final privada ausente o insegura.'
    }
    # Fail-closed on ANY extra ACE, inherited rule, invalid owner or no full
    # control for current broker, SYSTEM and Administrators.
    $acl=[IO.File]::GetAccessControl($file)
    $admin=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null).Value
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null).Value
    $permitted=@($admin,$system,$broker) | Select-Object -Unique
    $rules=@($acl.GetAccessRules($true,$true,
        [Security.Principal.SecurityIdentifier]))
    if(-not $acl.AreAccessRulesProtected -or
       $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne $admin -or
       $rules.Count -ne @($permitted).Count){
        throw 'La configuración del gate no es privada.'
    }
    $seen=@{}
    foreach($rule in $rules){
        $sid=$rule.IdentityReference.Value
        if($sid -notin $permitted -or $seen.ContainsKey($sid) -or
           $rule.IsInherited -or $rule.AccessControlType -ne 'Allow' -or
           ($rule.FileSystemRights -band
             [Security.AccessControl.FileSystemRights]::FullControl) -ne
             [Security.AccessControl.FileSystemRights]::FullControl){
            throw 'Configuración final alterable por una identidad ajena.'
        }
        $seen[$sid]=$true
    }
    $raw=[IO.File]::ReadAllText($file,[Text.Encoding]::UTF8)
    try {
        $item=$raw | ConvertFrom-Json
        $keys=@('version','sandbox','broker_sid','stage','final',
          'download_id','attempt','worker','torrent_hash',
          'approval_sha256','journal_root','lease_database','torrent_fixture_url',
          'expires_utc')
        if(@($item.PSObject.Properties.Name).Count -ne $keys.Count){
            throw 'Campos de autoridad inesperados.'
        }
        foreach($name in $keys){
            if($item.PSObject.Properties.Name -cnotcontains $name){
                throw 'Falta un campo de autoridad obligatorio.'
            }
        }
        $now=[DateTime]::UtcNow
        $end=[DateTime]::ParseExact([string]$item.expires_utc,'o',
           [Globalization.CultureInfo]::InvariantCulture,
           [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
        if($item.version -isnot [int] -or $item.version -ne 1 -or
           $item.sandbox -cne [IO.Path]::GetFileName($root) -or
           $item.broker_sid -cne $broker -or
           $item.stage -cne $StageName -or
           $item.final -cne $FinalName -or
           $item.download_id -isnot [int] -or
           $item.download_id -le 0 -or
           $item.attempt -isnot [int] -or
           $item.attempt -notin @(1,2,3) -or
           [string]$item.worker -cnotmatch '^[A-Za-z0-9_-]{1,128}$' -or
           [string]$item.torrent_hash -cnotmatch '^(?:[a-f0-9]{40}|[a-f0-9]{64})$' -or
           [string]$item.approval_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
           [string]$item.journal_root -cnotmatch '^.*\\viewtv-pipe-broker-[a-f0-9]{32}$' -or
           [string]$item.lease_database -cnotmatch '^/tmp/viewtv-lease-gate-[a-f0-9]{32}/organization\.sqlite3$' -or
           [string]$item.torrent_fixture_url -cnotmatch '^http://127\.0\.0\.1:([0-9]{5})$' -or
           $end -le $now -or $end -gt $now.AddMinutes(31)){
            throw 'Campos de autoridad no vinculados al trabajo.'
        }
        $urlMatch=[regex]::Match([string]$item.torrent_fixture_url,
            '^http://127\.0\.0\.1:([0-9]{5})$')
        if(-not $urlMatch.Success -or
           [int]$urlMatch.Groups[1].Value -lt 49152 -or
           [int]$urlMatch.Groups[1].Value -gt 65535){
            throw 'Origen HTTP no permitido.'
        }
        $canonical=([ordered]@{
            version=1
            sandbox=[string]$item.sandbox
            broker_sid=[string]$item.broker_sid
            stage=[string]$item.stage
            final=[string]$item.final
            download_id=[int]$item.download_id
            attempt=[int]$item.attempt
            worker=[string]$item.worker
            torrent_hash=[string]$item.torrent_hash
            approval_sha256=[string]$item.approval_sha256
            journal_root=[string]$item.journal_root
            lease_database=[string]$item.lease_database
            torrent_fixture_url=[string]$item.torrent_fixture_url
            expires_utc=[string]$item.expires_utc
        } | ConvertTo-Json -Compress)
        if($raw -cne $canonical){
            throw 'Configuración no canónica, posiblemente manipulada.'
        }
        if($ApprovalName -cnotmatch '^\.viewtv-approval-[1-9][0-9]{0,9}\.json$' -or
           $ApprovalName -cne ('.viewtv-approval-'+
            $StageName.Substring('.viewtv-stage-'.Length)+'.json')){
            throw 'Nombre de autorización no coincide.'
        }
        $approvalPath=Assert-ViewtvRestrictedSandboxPath $root (
            Join-Path $root $ApprovalName)
        $approval=[IO.File]::ReadAllText($approvalPath) | ConvertFrom-Json
        if($approval.payload -isnot [string] -or
           $approval.signature -isnot [string]){
            throw 'Sobre firmado no reconocible.'
        }
        $sha=[Security.Cryptography.SHA256]::Create()
        try {
            $digest=[BitConverter]::ToString($sha.ComputeHash(
                [Text.Encoding]::UTF8.GetBytes($approval.payload))
            ).Replace('-','').ToLowerInvariant()
        } finally {$sha.Dispose()}
        if($digest -cne [string]$item.approval_sha256){
            throw 'Plan firmado no coincide con la identidad del lease.'
        }
        # The HMAC plan is verified by the publisher before handoff.
        # The protected config alone is NOT an admission. Require BOTH
        # durable v3 records, including exact plan SHA, signed nonce,
        # identity, worker, attempt, torrent hash and original file ACLs.
        $signedPlan=$approval.payload | ConvertFrom-Json
        if([string]$signedPlan.nonce -cnotmatch '^[a-f0-9]{32}$'){
            throw 'Nonce firmado inválido o ausente.'
        }
        $null=Assert-ViewtvSandboxPinnedV3Admission (
            [string]$item.journal_root) ([long]$item.download_id) (
            [int]$item.attempt) ([string]$item.worker) (
            [string]$item.sandbox) ([string]$StageName) (
            [string]$FinalName) ([string]$item.torrent_hash) (
            [string]$item.approval_sha256) ([string]$signedPlan.nonce)
        if(-not (Test-ViewtvBrokerSandboxLease (
            [string]$item.lease_database) ([long]$item.download_id) (
            [string]$item.worker) ([int]$item.attempt) (
            [string]$item.torrent_hash))){
            throw 'Lease de sandbox no vigente justo antes de mover.'
        }
        $guid=([string]$item.sandbox).Substring('viewtv-win-sandbox-'.Length)
        if(-not (Test-ViewtvBrokerSandboxTorrent (
            [string]$item.torrent_fixture_url) $guid (
            [long]$item.download_id) ([string]$item.torrent_hash))){
            throw 'Identidad del torrent ficticio no válida antes de mover.'
        }
        return $true
    } catch {
        throw ('Gate final denegado: '+$_.Exception.Message)
    }
}
