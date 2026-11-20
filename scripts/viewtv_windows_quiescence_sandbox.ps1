# VIEWTV 0013 — NTFS quiescence preflight; SANDBOX GUID ONLY.
# No publisher or broker integration. Fail closed on ANY ambiguous status.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_restricted_token_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_stage_identity_sandbox.ps1')

if (-not ('ViewtvSandboxExclusiveHandles' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class ViewtvSandboxExclusiveHandles {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true,
               EntryPoint="CreateFileW")]
    private static extern SafeFileHandle Open(
        string path, uint access, uint share, IntPtr security,
        uint mode, uint flags, IntPtr template);

    // Only for a short preflight; a held handle would prevent Directory.Move.
    // Share mode NONE refuses files/directories already held by others.
    public static int ExclusiveStatus(string path, bool directory) {
        // FILE_READ_ATTRIBUTES alone does not reliably conflict with an
        // existing writer. GENERIC_READ must participate in share checks.
        const uint GENERIC_READ = 0x80000000;
        const uint OPEN_EXISTING = 3;
        const uint FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000;
        const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;
        uint flags = FILE_FLAG_OPEN_REPARSE_POINT |
                     (directory ? FILE_FLAG_BACKUP_SEMANTICS : 0);
        using (SafeFileHandle h = Open(path, GENERIC_READ, 0,
                                      IntPtr.Zero, OPEN_EXISTING,
                                      flags, IntPtr.Zero)) {
            if (h == null || h.IsInvalid) {
                return Marshal.GetLastWin32Error();
            }
            return 0;
        }
    }
}
'@
}

function Assert-ViewtvTestQuiescenceAcl([string]$Path,[bool]$Directory) {
    $acl=if($Directory){
        [IO.Directory]::GetAccessControl($Path)
    } else {
        [IO.File]::GetAccessControl($Path)
    }
    $admin=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null).Value
    $restricted=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::RestrictedCodeSid,$null).Value
    $owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if(-not $acl.AreAccessRulesProtected -or $owner -cne $admin){
        throw 'ACL o propietario del staging no están sellados.'
    }
    $rules=@($acl.GetAccessRules($true,$true,
        [Security.Principal.SecurityIdentifier]))
    $restrictedRules=@($rules | Where-Object {
        $_.IdentityReference.Value -ceq $restricted
    })
    # Windows may add SYNCHRONIZE to READ_AND_EXECUTE ACEs; permit
    # that one harmless bit, never WRITE_DATA, DELETE or WRITE_DAC.
    $readBits=[int][Security.AccessControl.FileSystemRights]::ReadAndExecute
    $allowedBits=$readBits -bor
        [int][Security.AccessControl.FileSystemRights]::Synchronize
    $rights=if($restrictedRules.Count -eq 1){
        [int]$restrictedRules[0].FileSystemRights
    } else { 0 }
    if($restrictedRules.Count -ne 1 -or
       $restrictedRules[0].IsInherited -or
       $restrictedRules[0].AccessControlType -ne 'Allow' -or
       (($rights -band $readBits) -ne $readBits) -or
       (($rights -band (-bnot $allowedBits)) -ne 0)){
        throw 'El token de copia no está limitado a lectura.'
    }
    if(@($rules | Where-Object {
        $_.IsInherited -or $_.AccessControlType -ne 'Allow'
    }).Count -gt 0){
        throw 'ACL inesperada o heredada en staging.'
    }
}

function Test-ViewtvSandboxQuiescence(
    [string]$SandboxRoot,[string]$StageName
) {
    if($StageName -cnotmatch '^\.viewtv-stage-[1-9][0-9]{0,9}$'){
        throw 'Nombre de staging no autorizado.'
    }
    # Exception is a safe refusal as well; caller MUST treat as no consent.
    $root=[IO.Path]::GetFullPath($SandboxRoot).TrimEnd('\')
    $stage=Assert-ViewtvRestrictedSandboxPath $root (Join-Path $root $StageName)
    $result=[ordered]@{
        estado='requiere_revision'
        razon='no_demostrada_quiescencia'
        archivos=0
    }
    try {
        if(-not [IO.Directory]::Exists($stage)){
            return [pscustomobject]$result
        }
        Assert-ViewtvTestQuiescenceAcl $stage $true
        $fingerprint=Get-ViewtvTestStageFingerprint $root $StageName
        $files=@([IO.Directory]::GetFiles($stage))
        $entries=@([IO.Directory]::GetFileSystemEntries($stage))
        if($files.Count -ne $entries.Count -or
           $files.Count -lt 1 -or $files.Count -gt 20){
            return [pscustomobject]$result
        }
        foreach($file in $files){
            Assert-ViewtvRestrictedSandboxPath $root $file | Out-Null
            $info=[IO.FileInfo]::new($file)
            if(-not $info.Exists -or $info.Length -le 0 -or
                $info.Length -gt 33554432 -or
                ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
                return [pscustomobject]$result
            }
            Assert-ViewtvTestQuiescenceAcl $file $false
        }
        # After ACL sealing, attempt an exclusive *short* open of
        # directory AND all files. This detects the pre-existing handles
        # of the test's restricted writer; it is not an OS-wide barrier.
        if([ViewtvSandboxExclusiveHandles]::ExclusiveStatus($stage,$true) -ne 0){
            $result.razon='carpeta_con_handles_o_denegada'
            return [pscustomobject]$result
        }
        foreach($file in $files){
            if([ViewtvSandboxExclusiveHandles]::ExclusiveStatus($file,$false) -ne 0){
                $result.razon='archivo_con_handles_o_denegado'
                return [pscustomobject]$result
            }
        }
        $stable=Get-ViewtvTestStageFingerprint $root $StageName
        if($fingerprint -cne $stable){
            $result.razon='identidad_ntfs_cambiada'
            return [pscustomobject]$result
        }
        $result.estado='sin_handles_detectados'
        $result.razon='preflight_con_acl_sellada'
        $result.archivos=$files.Count
        return [pscustomobject]$result
    } catch {
        # Only the exception TYPE, never paths or secrets, leaves the sandbox.
        $result.razon='error_'+$_.Exception.GetType().Name
        return [pscustomobject]$result
    }
}
