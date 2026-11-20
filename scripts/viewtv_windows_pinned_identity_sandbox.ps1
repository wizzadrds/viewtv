# VIEWTV 0013 — read a broker-private, ACL-protected copy SID.
# Test GUID sandbox ONLY. No production service, identity provisioning or writes.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_copy_acl_gate_sandbox.ps1')

function Get-ViewtvSandboxPinnedCopySid([string]$SandboxRoot,[string]$Vault) {
    $root=[IO.Path]::GetFullPath($SandboxRoot).TrimEnd('\')
    $root=Assert-ViewtvRestrictedSandboxPath $root $root
    $vault=Assert-ViewtvRestrictedSandboxPath $root $Vault
    if([IO.Path]::GetDirectoryName($vault) -ine $root -or
       [IO.Path]::GetFileName($vault) -cne '.viewtv-broker-handoff'){
        throw 'Cámara no reconocida para identidad del copiador.'
    }
    $actualBroker=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $admin=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null).Value
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null).Value
    $permitted=@($admin,$system,$actualBroker) | Select-Object -Unique
    # Verify the PARENT independently, before believing bytes from a file.
    $vaultInfo=[IO.DirectoryInfo]::new($vault)
    if(-not $vaultInfo.Exists -or
       ($vaultInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
        throw 'Cámara privada inexistente o redirigida.'
    }
    $vaultAcl=[IO.Directory]::GetAccessControl($vault)
    if(-not $vaultAcl.AreAccessRulesProtected -or
       $vaultAcl.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne $admin){
        throw 'Cámara privada sin propietario o DACL protegidos.'
    }
    $vaultRules=@($vaultAcl.GetAccessRules($true,$true,
        [Security.Principal.SecurityIdentifier]))
    if($vaultRules.Count -ne @($permitted).Count){
        throw 'ACL no exclusiva de cámara privada.'
    }
    $seen=@{}
    foreach($rule in $vaultRules){
        $sid=$rule.IdentityReference.Value
        if($sid -notin $permitted -or $rule.IsInherited -or
           $rule.AccessControlType -ne 'Allow' -or
           $seen.ContainsKey($sid) -or
           ($rule.FileSystemRights -band
              [Security.AccessControl.FileSystemRights]::FullControl) -ne
              [Security.AccessControl.FileSystemRights]::FullControl){
            throw 'Identidad desconocida en cámara privada.'
        }
        $seen[$sid]=$true
    }
    $file=Assert-ViewtvRestrictedSandboxPath $root (
        Join-Path $vault '.viewtv-copy-identity.json')
    $info=[IO.FileInfo]::new($file)
    if(-not $info.Exists -or $info.Length -lt 100 -or $info.Length -gt 1024 -or
       ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
        throw 'Registro de identidad ausente, redirigido o excesivo.'
    }
    $acl=[IO.File]::GetAccessControl($file)
    if(-not $acl.AreAccessRulesProtected -or
       $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne $admin){
        throw 'ACL o propietario del registro no válidos.'
    }
    $rules=@($acl.GetAccessRules($true,$true,
        [Security.Principal.SecurityIdentifier]))
    if($rules.Count -ne @($permitted).Count){
        throw 'Registro no privado o ACE adicionales.'
    }
    $seen=@{}
    foreach($rule in $rules){
        $sid=$rule.IdentityReference.Value
        if($sid -notin $permitted -or $rule.IsInherited -or
           $rule.AccessControlType -ne 'Allow' -or
           $seen.ContainsKey($sid) -or
           ($rule.FileSystemRights -band
              [Security.AccessControl.FileSystemRights]::FullControl) -ne
              [Security.AccessControl.FileSystemRights]::FullControl){
            throw 'El copiador u otra identidad puede alterar el registro.'
        }
        $seen[$sid]=$true
    }
    # The file is fixed and created by a trusted TEST initializer. Requests
    # carry no SID and cannot tell this reader to look up another file.
    $body=[IO.File]::ReadAllText($file,[Text.Encoding]::UTF8)
    try {
        $item=$body | ConvertFrom-Json
        $expectedKeys=@('version','sandbox','copy_sid','broker_sid','expires_utc')
        if(@($item.PSObject.Properties.Name).Count -ne $expectedKeys.Count){
            throw 'Campos inesperados.'
        }
        foreach($key in $expectedKeys){
            if($item.PSObject.Properties.Name -cnotcontains $key){
                throw 'Campo obligatorio ausente.'
            }
        }
        if($item.version -isnot [int] -or $item.version -ne 1 -or
           $item.sandbox -cne [IO.Path]::GetFileName($root) -or
           $item.broker_sid -cne $actualBroker){
            throw 'Registro no emitido para este sandbox o broker.'
        }
        $copySid=[string]$item.copy_sid
        $null=Assert-ViewtvSandboxCopySid $copySid $actualBroker
        $expires=[DateTime]::ParseExact([string]$item.expires_utc,'o',
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
        $now=[DateTime]::UtcNow
        if($expires -le $now -or $expires -gt $now.AddHours(1)){
            throw 'Registro caducado o con vigencia demasiado larga.'
        }
        $canonical=([ordered]@{
            version=1
            sandbox=[string]$item.sandbox
            copy_sid=$copySid
            broker_sid=$actualBroker
            expires_utc=[string]$item.expires_utc
        } | ConvertTo-Json -Compress)
        if($body -cne $canonical){
            throw 'Registro no canónico, duplicado o modificado.'
        }
        # Validate the resulting SID against the ACL of the vault as well.
        Assert-ViewtvSandboxNoCopyAce $root $vault $true $copySid $actualBroker
        return $copySid
    } catch {
        throw ('Identidad del copiador no verificable: '+$_.Exception.Message)
    }
}
