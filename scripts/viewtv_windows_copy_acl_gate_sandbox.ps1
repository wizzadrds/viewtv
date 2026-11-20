# VIEWTV 0013 — verify copy SID revoked before and after sandbox NTFS handoff.
# Read-only ACL gate. Not a production identity/authorization authority.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_restricted_token_sandbox.ps1')

function Assert-ViewtvSandboxCopySid(
    [string]$CopySid,[string]$BrokerSid
) {
    if($CopySid -cnotmatch '^S-1-5-21-[0-9]+-[0-9]+-[0-9]+-[0-9]+$'){
        throw 'SID copiador obligatorio y de tipo cuenta local.'
    }
    $actual=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    if([string]::IsNullOrWhiteSpace($BrokerSid)){
        $BrokerSid=$actual
    }
    try {
        $copy=[Security.Principal.SecurityIdentifier]::new($CopySid)
        $broker=[Security.Principal.SecurityIdentifier]::new($BrokerSid)
    } catch {
        throw 'SID no interpretable.'
    }
    $admin=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null).Value
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null).Value
    if($copy.Value -in @($actual,$broker.Value,$admin,$system)){
        throw 'El SID copiador coincide con una identidad de publicación.'
    }
    return $broker.Value
}

function Assert-ViewtvSandboxNoCopyAce(
    [string]$Root,[string]$Path,[bool]$Directory,
    [string]$CopySid,[string]$BrokerSid,
    [bool]$AllowCopyReadOnRoot=$false
) {
    $broker=Assert-ViewtvSandboxCopySid $CopySid $BrokerSid
    $path=Assert-ViewtvRestrictedSandboxPath $Root $Path
    $attributes=[IO.File]::GetAttributes($path)
    if(($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        ((($attributes -band [IO.FileAttributes]::Directory) -ne 0) -ne $Directory)){
        throw 'Entrada no regular o redirigida: ACL no demostrada.'
    }
    $acl=if($Directory) {
        [IO.Directory]::GetAccessControl($path)
    } else {
        [IO.File]::GetAccessControl($path)
    }
    $admin=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null).Value
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null).Value
    $restricted=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::RestrictedCodeSid,$null).Value
    $current=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    if(-not $acl.AreAccessRulesProtected -or
       $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne $admin){
        throw 'DACL u owner no sellados.'
    }
    $allowed=@($admin,$system,$current,$broker,$restricted)
    if($AllowCopyReadOnRoot){$allowed+=,$CopySid}
    $seen=@{}
    $rules=@($acl.GetAccessRules($true,$true,
        [Security.Principal.SecurityIdentifier]))
    if($rules.Count -lt 3 -or $rules.Count -gt 6){
        throw 'Número de ACE no autorizado.'
    }
    foreach($rule in $rules){
        $sid=$rule.IdentityReference.Value
        if($sid -notin $allowed -or
           $rule.IsInherited -or
           $rule.AccessControlType -ne 'Allow' -or
           $seen.ContainsKey($sid)){
            throw 'SID copiador o ACE inesperada en objeto NTFS.'
        }
        $seen[$sid]=$true
        $rights=[int]$rule.FileSystemRights
        if($sid -ceq $CopySid -or $sid -ceq $restricted) {
            $readBits=[int][Security.AccessControl.FileSystemRights]::ReadAndExecute
            $allowedRead=$readBits -bor
                [int][Security.AccessControl.FileSystemRights]::Synchronize
            if(($rights -band $readBits) -ne $readBits -or
               (($rights -band (-bnot $allowedRead)) -ne 0)){
                throw 'Un SID de copia tiene derechos excesivos.'
            }
        } else {
            $full=[int][Security.AccessControl.FileSystemRights]::FullControl
            if(($rights -band $full) -ne $full){
                throw 'Autoridad del broker no controlada.'
            }
        }
    }
    foreach($sid in @($admin,$system,$current,$broker) |
        Select-Object -Unique){
        if(-not $seen.ContainsKey($sid)){
            throw 'Falta ACE obligatoria de broker o administración.'
        }
    }
}

function Assert-ViewtvSandboxHandoffCopyGate(
    [string]$SandboxRoot,[string]$Folder,
    [string]$CopySid,[string]$BrokerSid
) {
    $root=[IO.Path]::GetFullPath($SandboxRoot).TrimEnd('\')
    $root=Assert-ViewtvRestrictedSandboxPath $root $root
    $folder=Assert-ViewtvRestrictedSandboxPath $root $Folder
    # Copy must traverse root to reach its own temporary staging, but
    # never receive write/delete rights over root or published objects.
    Assert-ViewtvSandboxNoCopyAce $root $root $true $CopySid $BrokerSid $true
    Assert-ViewtvSandboxNoCopyAce $root $folder $true $CopySid $BrokerSid
    $entries=@([IO.Directory]::GetFileSystemEntries($folder))
    if($entries.Count -lt 1 -or $entries.Count -gt 20){
        throw 'Cantidad de archivos de prueba no admitida.'
    }
    foreach($entry in $entries){
        Assert-ViewtvSandboxNoCopyAce $root $entry $false $CopySid $BrokerSid
        $info=[IO.FileInfo]::new($entry)
        if(-not $info.Exists -or $info.Length -le 0 -or
           $info.Length -gt 33554432){
            throw 'Entrada de staging insegura.'
        }
    }
    return $entries.Count
}
