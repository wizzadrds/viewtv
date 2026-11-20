# VIEWTV 0013 — pin the signed NTFS plan to a durable v3 pipe admission.
# Marked GUID test journals ONLY. Read-only, no publication or prod database.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Assert-ViewtvV3ClaimAcl([string]$Path,[bool]$Directory) {
    $current=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $admin=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null).Value
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null).Value
    $item=if($Directory){[IO.DirectoryInfo]::new($Path)}else{[IO.FileInfo]::new($Path)}
    if(-not $item.Exists -or
       ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
        throw 'Entrada del diario ausente o redirigida.'
    }
    $acl=if($Directory){[IO.Directory]::GetAccessControl($Path)}
        else {[IO.File]::GetAccessControl($Path)}
    $owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if($owner -notin @($admin,$current) -or
       ($Directory -and -not $acl.AreAccessRulesProtected)){
        throw 'Diario sin propiedad o DACL privada.'
    }
    $expected=@($current,$admin,$system)|Select-Object -Unique
    $rules=@($acl.GetAccessRules($true,$true,
        [Security.Principal.SecurityIdentifier]))
    if($rules.Count -ne @($expected).Count){
        throw 'Número de ACE inseguro en diario o registro.'
    }
    $seen=@{}
    foreach($r in $rules){
        $sid=$r.IdentityReference.Value
        if($sid -notin $expected -or $seen.ContainsKey($sid) -or
           $r.AccessControlType -ne 'Allow' -or
           ($Directory -and $r.IsInherited) -or
           ($r.FileSystemRights -band
             [Security.AccessControl.FileSystemRights]::FullControl) -ne
             [Security.AccessControl.FileSystemRights]::FullControl){
            throw 'Diario o registro accesible por identidad ajena.'
        }
        $seen[$sid]=$true
    }
    return $true
}

function Assert-ViewtvV3ClaimFile([string]$Root,[string]$Name,
                                 [int]$MinLength,[int]$MaxLength){
    $path=Join-Path $Root $Name
    if([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($path)) -ine $Root){
        throw 'Registro fuera del diario.'
    }
    $info=[IO.FileInfo]::new($path)
    if(-not $info.Exists -or $info.Length -lt $MinLength -or
       $info.Length -gt $MaxLength){
        throw 'Registro de reserva ausente o incompleto.'
    }
    $null=Assert-ViewtvV3ClaimAcl $path $false
    return [IO.File]::ReadAllText($path,[Text.Encoding]::UTF8)
}

function Assert-ViewtvSandboxPinnedV3Admission(
    [string]$JournalRoot,[long]$DownloadId,[int]$Attempt,[string]$Worker,
    [string]$Sandbox,[string]$Stage,[string]$Final,[string]$TorrentHash,
    [string]$ApprovalSha256,[string]$ApprovalNonce
) {
    $temp=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
    $root=[IO.Path]::GetFullPath($JournalRoot).TrimEnd('\')
    if([IO.Path]::GetDirectoryName($root) -ine $temp -or
       [IO.Path]::GetFileName($root) -cnotmatch '^viewtv-pipe-broker-[a-f0-9]{32}$' -or
       $DownloadId -le 0 -or $Attempt -notin @(1,2,3) -or
       $Worker -cnotmatch '^[A-Za-z0-9_-]{1,128}$' -or
       $Sandbox -cnotmatch '^viewtv-win-sandbox-[a-f0-9]{32}$' -or
       $Stage -cnotmatch '^\.viewtv-stage-[1-9][0-9]{0,9}$' -or
       $Final -cnotmatch '^[A-Za-z0-9][A-Za-z0-9 .()_-]{0,100}$' -or
       $TorrentHash -cnotmatch '^(?:[a-f0-9]{40}|[a-f0-9]{64})$' -or
       $ApprovalSha256 -cnotmatch '^[a-f0-9]{64}$' -or
       $ApprovalNonce -cnotmatch '^[a-f0-9]{32}$'){
        throw 'Identidad de reserva v3 o raíz fuera de sandbox.'
    }
    $null=Assert-ViewtvV3ClaimAcl $root $true
    $marker=Assert-ViewtvV3ClaimFile $root '.viewtv-pipe-only' 32 64
    if($marker -cne ('VIEWTV_PIPE_BROKER_TEST_ONLY_V1'+[char]10)){
        throw 'Marcador de diario no coincide.'
    }
    $claimFile='.viewtv-download-'+$DownloadId+'.json'
    $nonceFile='.viewtv-nonce-'+$ApprovalNonce+'.json'
    $rawClaim=Assert-ViewtvV3ClaimFile $root $claimFile 150 2048
    $rawNonce=Assert-ViewtvV3ClaimFile $root $nonceFile 100 1024
    try {
        $claim=$rawClaim|ConvertFrom-Json
        $nonce=$rawNonce|ConvertFrom-Json
        $claimFields=@('version','download_id','attempt','worker','sandbox',
          'stage','final','manifest_sha256','nonce','reserved_utc','torrent_hash')
        $nonceFields=@('version','nonce','manifest_sha256','download_id',
          'attempt','reserved_utc')
        if(@($claim.PSObject.Properties.Name).Count -ne $claimFields.Count -or
           @($nonce.PSObject.Properties.Name).Count -ne $nonceFields.Count){
            throw 'Registro parcial o campos inesperados.'
        }
        foreach($key in $claimFields){
            if($claim.PSObject.Properties.Name -cnotcontains $key){
                throw 'Falta campo del registro de descarga.'
            }
        }
        foreach($key in $nonceFields){
            if($nonce.PSObject.Properties.Name -cnotcontains $key){
                throw 'Falta campo del registro de nonce.'
            }
        }
        if($claim.version -isnot [int] -or $claim.version -ne 3 -or
           $nonce.version -isnot [int] -or $nonce.version -ne 1 -or
           $claim.download_id -isnot [int] -and $claim.download_id -isnot [long] -or
           $nonce.download_id -isnot [int] -and $nonce.download_id -isnot [long] -or
           $claim.attempt -isnot [int] -or $nonce.attempt -isnot [int] -or
           [long]$claim.download_id -ne $DownloadId -or
           [long]$nonce.download_id -ne $DownloadId -or
           $claim.attempt -ne $Attempt -or $nonce.attempt -ne $Attempt -or
           $claim.worker -cne $Worker -or
           $claim.sandbox -cne $Sandbox -or
           $claim.stage -cne $Stage -or $claim.final -cne $Final -or
           $claim.torrent_hash -cne $TorrentHash -or
           $claim.manifest_sha256 -cne $ApprovalSha256 -or
           $nonce.manifest_sha256 -cne $ApprovalSha256 -or
           $claim.nonce -cne $ApprovalNonce -or
           $nonce.nonce -cne $ApprovalNonce -or
           $claim.reserved_utc -isnot [string] -or
           $nonce.reserved_utc -cne $claim.reserved_utc){
            throw 'El diario no coincide con el plan, lease e intento.'
        }
        $timestamp=[DateTime]::ParseExact([string]$claim.reserved_utc,'o',
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
        $now=[DateTime]::UtcNow
        if($timestamp -gt $now.AddSeconds(5) -or $timestamp -lt $now.AddMinutes(-5)){
            throw 'Reserva v3 demasiado antigua o con fecha futura.'
        }
        $canonicalClaim=([ordered]@{
            version=3
            download_id=[long]$claim.download_id
            attempt=[int]$claim.attempt
            worker=[string]$claim.worker
            sandbox=[string]$claim.sandbox
            stage=[string]$claim.stage
            final=[string]$claim.final
            manifest_sha256=[string]$claim.manifest_sha256
            nonce=[string]$claim.nonce
            reserved_utc=[string]$claim.reserved_utc
            torrent_hash=[string]$claim.torrent_hash
        } | ConvertTo-Json -Compress)
        $canonicalNonce=([ordered]@{
            version=1
            nonce=[string]$nonce.nonce
            manifest_sha256=[string]$nonce.manifest_sha256
            download_id=[long]$nonce.download_id
            attempt=[int]$nonce.attempt
            reserved_utc=[string]$nonce.reserved_utc
        } | ConvertTo-Json -Compress)
        if($rawClaim -cne $canonicalClaim -or $rawNonce -cne $canonicalNonce){
            throw 'Registro de admisión v3 no canónico.'
        }
        return $true
    } catch {
        throw ('La reserva durable v3 no autoriza publicar: '+$_.Exception.Message)
    }
}
