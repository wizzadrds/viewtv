# VIEWTV 0013 — broker-private handoff via two NTFS renames; GUID SANDBOX ONLY.
# Not a production broker: an independent Windows SID is mandatory.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_quiescence_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_copy_acl_gate_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_pinned_identity_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_final_gate_sandbox.ps1')

function Assert-ViewtvSandboxHandoffVault([string]$Root,[string]$BrokerSid) {
    $vault=Assert-ViewtvRestrictedSandboxPath $Root (Join-Path $Root '.viewtv-broker-handoff')
    $info=[IO.DirectoryInfo]::new($vault)
    if(-not $info.Exists -or
       ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
        throw 'No hay cámara privada de broker en sandbox.'
    }
    $acl=[IO.Directory]::GetAccessControl($vault)
    $admin=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null).Value
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null).Value
    $current=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    if(-not $acl.AreAccessRulesProtected -or
       $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne $admin){
        throw 'ACL o propiedad de cámara privada sin protección.'
    }
    $rules=@($acl.GetAccessRules($true,$true,
        [Security.Principal.SecurityIdentifier]))
    $expected=@($admin,$system,$current,$BrokerSid) | Select-Object -Unique
    if($rules.Count -ne @($expected).Count){
        throw 'Reglas inesperadas en cámara de broker.'
    }
    foreach($r in $rules){
        if($r.IsInherited -or $r.AccessControlType -ne 'Allow' -or
           $r.IdentityReference.Value -notin $expected -or
           ($r.FileSystemRights -band
             [Security.AccessControl.FileSystemRights]::FullControl) -ne
             [Security.AccessControl.FileSystemRights]::FullControl){
            throw 'La cámara permite identidad distinta a la del broker de prueba.'
        }
    }
    return $vault
}

function Get-ViewtvSandboxHandoffFingerprint([string]$Folder) {
    $stamp=[ordered]@{carpeta=[ViewtvSandboxNtfsIdentity]::Fingerprint($Folder,$false)}
    $entries=@([IO.Directory]::GetFileSystemEntries($Folder))
    if($entries.Count -lt 1 -or $entries.Count -gt 20){
        throw 'Conjunto de archivos incorrecto tras handoff.'
    }
    foreach($entry in @($entries | Sort-Object)){
        $name=[IO.Path]::GetFileName($entry)
        $stamp[$name]=[ViewtvSandboxNtfsIdentity]::Fingerprint($entry,$true)
    }
    return ($stamp | ConvertTo-Json -Compress)
}

function Invoke-ViewtvSandboxBrokerHandoff(
    [string]$SandboxRoot,[string]$StageName,[string]$FinalName,
    [string]$ApprovalName,[string]$KeyPath,
    [bool]$RequireFinalAuthority=$false
) {
    $root=[IO.Path]::GetFullPath($SandboxRoot).TrimEnd('\')
    if($StageName -cnotmatch '^\.viewtv-stage-[1-9][0-9]{0,9}$'){
        throw 'Staging incorrecto'
    }
    # The worker/client cannot select the identity against which ACLs are
    # checked. Load it from a broker-private record bound to this sandbox.
    $broker=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $stage=Assert-ViewtvRestrictedSandboxPath $root (Join-Path $root $StageName)
    $final=Assert-ViewtvRestrictedSandboxPath $root (Join-Path $root $FinalName)
    $vault=Assert-ViewtvSandboxHandoffVault $root $broker
    $CopySid=Get-ViewtvSandboxPinnedCopySid $root $vault
    $handoffName='.viewtv-handoff-'+$StageName.Substring('.viewtv-stage-'.Length)
    $escrow=Assert-ViewtvRestrictedSandboxPath $root (Join-Path $vault $handoffName)
    if([IO.Directory]::Exists($escrow) -or [IO.File]::Exists($escrow) -or
       [IO.Directory]::Exists($final) -or [IO.File]::Exists($final)){
        throw 'Colisión; no reintentar publicación.'
    }
    # The pinned SID comes from the private registry, not from the caller.
    # Production still requires a separate persistent broker process.
    $null=Assert-ViewtvSandboxHandoffCopyGate $root $stage $CopySid $broker
    $quiet=Test-ViewtvSandboxQuiescence $root $StageName
    if($quiet.estado -cne 'sin_handles_detectados'){
        throw 'No se ha demostrado cierre de escritores.'
    }
    if(-not (Assert-ViewtvTestApproval -SandboxRoot $root -StageName $StageName -FinalName $FinalName -ApprovalName $ApprovalName -KeyPath $KeyPath -Location Stage)){
        throw 'Intención firmada no válida.'
    }
    $envelope=[IO.File]::ReadAllText((Join-Path $root $ApprovalName)) |
        ConvertFrom-Json
    $plan=$envelope.payload | ConvertFrom-Json
    $identity=[string]$plan.stage_identity
    $declared=@($plan.files)
    if($declared.Count -ne $quiet.archivos){
        throw 'Manifiesto inconsistente.'
    }
    # Strict LABORATORY mode: revalidate the broker-private lease and the
    # marked fake torrent immediately before FIRST NTFS rename. Old sandbox
    # mode deliberately remains available for historical regression tests.
    if($RequireFinalAuthority){
        $null=Assert-ViewtvSandboxFinalGate $root $vault $StageName $FinalName $ApprovalName $KeyPath
    }
    # First rename is NOT a publication: it hands the sealed directory to
    # a broker-only parent. On tested NTFS, preopened writer handles make
    # Directory.Move fail, including when ACL sealing succeeded.
    # Never automatically retry if the result was ambiguous.
    [IO.Directory]::Move($stage,$escrow)
    # From this point forward a distinct copy SID MUST lack traverse/write
    # permissions on the private parent. Same SID test is NOT production.
    if((Get-ViewtvSandboxPinnedCopySid $root $vault) -cne $CopySid){
        throw 'La identidad privada cambió durante la entrega; requiere revisión.'
    }
    $null=Assert-ViewtvSandboxHandoffCopyGate $root $escrow $CopySid $broker
    $escrowEntries=@([IO.Directory]::GetFileSystemEntries($escrow))
    if($escrowEntries.Count -ne $declared.Count){
        throw 'Handoff incompleto; requiere revisión.'
    }
    foreach($entry in $declared){
        $name=[string]$entry.name
        if($name -match '[<>:"/\\|?*\x00-\x1f]' -or
           $name -in @('.','..') -or $name.StartsWith('.')){
            throw 'Nombre inesperado; requiere revisión.'
        }
        $file=Assert-ViewtvRestrictedSandboxPath $root (Join-Path $escrow $name)
        Assert-ViewtvTestQuiescenceAcl $file $false
        $info=[IO.FileInfo]::new($file)
        if(-not $info.Exists -or $info.Length -ne [long]$entry.size -or
           $info.Length -le 0 -or $info.Length -gt 33554432 -or
           (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne [string]$entry.sha256){
            throw 'Contenido alterado después de handoff; requiere revisión.'
        }
    }
    Assert-ViewtvTestQuiescenceAcl $escrow $true
    if((Get-ViewtvSandboxHandoffFingerprint $escrow) -cne $identity){
        throw 'Identidad NTFS alterada después de handoff; requiere revisión.'
    }
    $expires=[DateTime]::Parse([string]$plan.expires_utc).ToUniversalTime()
    if($expires -le [DateTime]::UtcNow){
        throw 'Intención caducó en cámara privada.'
    }
    if([IO.Directory]::Exists($final) -or [IO.File]::Exists($final)){
        throw 'Destino ocupado antes de movimiento final.'
    }
    # Second rename is publication; the copy identity has had no access
    # since the first rename. On failure preserve escrow/final for review.
    # Check pinned identity and ACL gate again before the final rename.
    if((Get-ViewtvSandboxPinnedCopySid $root $vault) -cne $CopySid){
        throw 'Identidad privada cambiada antes de publicar; requiere revisión.'
    }
    $null=Assert-ViewtvSandboxHandoffCopyGate $root $escrow $CopySid $broker
    # The lease or HTTP state may have changed while the files were in
    # escrow. Failure leaves escrow in place for manual reconciliation.
    if($RequireFinalAuthority){
        $null=Assert-ViewtvSandboxFinalGate $root $vault $StageName $FinalName $ApprovalName $KeyPath
    }
    [IO.Directory]::Move($escrow,$final)
    $null=Assert-ViewtvSandboxHandoffCopyGate $root $final $CopySid $broker
}
