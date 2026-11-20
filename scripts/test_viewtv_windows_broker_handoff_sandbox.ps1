# VIEWTV 0013 — two-step private NTFS handoff test; NEW GUID sandbox ONLY.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_restricted_token_sandbox.ps1')
$publisher=Join-Path $PSScriptRoot 'viewtv_windows_publish_sandbox.ps1'

$public=[IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
if($public -ine 'C:\Users\Public'){throw 'Raíz inesperada.'}
$root=Join-Path $public ('viewtv-win-sandbox-'+[Guid]::NewGuid().ToString('N'))
$marker=Join-Path $root '.viewtv-win-sandbox-only'
$key=$null
$token=[IntPtr]::Zero
$result=[ordered]@{}
$current=[Security.Principal.WindowsIdentity]::GetCurrent().User
$admin=[Security.Principal.SecurityIdentifier]::new(
    [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null)
$system=[Security.Principal.SecurityIdentifier]::new(
    [Security.Principal.WellKnownSidType]::LocalSystemSid,$null)
$restricted=[Security.Principal.SecurityIdentifier]::new(
    [Security.Principal.WellKnownSidType]::RestrictedCodeSid,$null)
$allow=[Security.AccessControl.AccessControlType]::Allow
$full=[Security.AccessControl.FileSystemRights]::FullControl
$read=[Security.AccessControl.FileSystemRights]::ReadAndExecute

function Protect-StageItem([string]$Path,[bool]$Folder,[bool]$ForCopy) {
    $acl=if($Folder){[Security.AccessControl.DirectorySecurity]::new()
          } else {[Security.AccessControl.FileSecurity]::new()}
    $acl.SetAccessRuleProtection($true,$false)
    foreach($sid in @($current,$admin,$system)){
        $rule=if($Folder){
            [Security.AccessControl.FileSystemAccessRule]::new(
                $sid,$full,[Security.AccessControl.InheritanceFlags]::None,
                [Security.AccessControl.PropagationFlags]::None,$allow)
        } else {
            [Security.AccessControl.FileSystemAccessRule]::new($sid,$full,$allow)
        }
        $acl.AddAccessRule($rule)
    }
    if($ForCopy){
        $rule=if($Folder){
            [Security.AccessControl.FileSystemAccessRule]::new(
                $restricted,$read,[Security.AccessControl.InheritanceFlags]::None,
                [Security.AccessControl.PropagationFlags]::None,$allow)
        } else {
            [Security.AccessControl.FileSystemAccessRule]::new($restricted,$read,$allow)
        }
        $acl.AddAccessRule($rule)
    }
    $acl.SetOwner($admin)
    if($Folder){[IO.Directory]::SetAccessControl($Path,$acl)}
    else {[IO.File]::SetAccessControl($Path,$acl)}
}
function New-TestStage([int]$Id,[string]$FinalName) {
    $stageName='.viewtv-stage-'+$Id
    $folder=Join-Path $root $stageName
    [IO.Directory]::CreateDirectory($folder)|Out-Null
    $video=Join-Path $folder 'ficticio.mkv'
    [IO.File]::WriteAllBytes($video,[Text.Encoding]::UTF8.GetBytes(
        ('ficticio'+$Id)*1024))
    $hash=(Get-FileHash -LiteralPath $video -Algorithm SHA256).Hash
    $approval=New-ViewtvTestApproval $root $stageName $FinalName $key
    Protect-StageItem $video $false $true
    Protect-StageItem $folder $true $true
    return [pscustomobject]@{
        stage=$stageName; folder=$folder; video=$video;
        final=$FinalName; approval=$approval; hash=$hash
    }
}
function Publish-TestStage($s) {
    & $publisher -SandboxRoot $root -StageName $s.stage -FinalName $s.final -ApprovalName $s.approval -KeyPath $key -BrokerHandoff
}
function Check([bool]$condition,[string]$reason) {
    if(-not $condition){throw $reason}
}
try {
    Check (-not [IO.Directory]::Exists($root)) 'GUID preexistente.'
    [IO.Directory]::CreateDirectory($root)|Out-Null
    [IO.File]::WriteAllText($marker,('VIEWTV_WINDOWS_SANDBOX_ONLY_V1'+[char]10))
    $key=New-ViewtvTestKey
    $vault=Join-Path $root '.viewtv-broker-handoff'
    [IO.Directory]::CreateDirectory($vault)|Out-Null
    # Validate fail-closed when the broker private parent is unsealed.
    $bad=New-TestStage 1 'ResultadoUno'
    $refused=$false
    try { Publish-TestStage $bad | Out-Null } catch { $refused=$true }
    Check $refused 'Se aceptó cámara de broker sin ACL protegida.'
    Check ([IO.Directory]::Exists($bad.folder)) 'Movió antes de sellar cámara.'
    $result['vault_sin_proteger']='rechazado'
    Protect-StageItem $vault $true $false

    # Distinct restricted token must not read or write the private parent.
    $token=[ViewtvSandboxRestrictedToken]::Create()
    $denied=Invoke-ViewtvRestrictedSandboxOperation $token $root 'mkdir' (Join-Path $vault 'intruso')
    Check ($denied -ceq 'denied') 'Copia pudo crear en cámara de broker.'
    $result['copia_no_escribe_escrow']='denied'

    # Two consecutive renames and verification after the private handoff.
    Publish-TestStage $bad | Out-Null
    $destination=Join-Path $root $bad.final
    Check (-not [IO.Directory]::Exists($bad.folder)) 'Staging no entregado.'
    Check ([IO.File]::Exists((Join-Path $destination 'ficticio.mkv'))) 'Sin publicación.'
    Check ((Get-FileHash -LiteralPath (Join-Path $destination 'ficticio.mkv') -Algorithm SHA256).Hash -ceq $bad.hash) 'Hash final cambiado.'
    Check (-not [IO.Directory]::Exists((Join-Path $vault '.viewtv-handoff-1'))) 'Escrow residual inesperado.'
    $result['handoff_y_publicacion_ntfs']='correcto'

    # Old writer from before ACL sealing: rename must NOT occur.
    $stageName='.viewtv-stage-2'
    $secondPath=Join-Path $root $stageName
    [IO.Directory]::CreateDirectory($secondPath)|Out-Null
    $video=Join-Path $secondPath 'ficticio.mkv'
    [IO.File]::WriteAllText($video,'contenido_inicial')
    $approval=New-ViewtvTestApproval $root $stageName 'ResultadoDos' $key
    $writer=[IO.File]::Open($video,[IO.FileMode]::Open,
        [IO.FileAccess]::Write,
        ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    try {
        Protect-StageItem $video $false $true
        Protect-StageItem $secondPath $true $true
        $blocked=$false
        try {
            & $publisher -SandboxRoot $root -StageName $stageName -FinalName 'ResultadoDos' -ApprovalName $approval -KeyPath $key -BrokerHandoff | Out-Null
        } catch {$blocked=$true}
        Check $blocked 'Se aceptó escritor preabierto.'
        Check ([IO.Directory]::Exists($secondPath)) 'El escritor no bloqueó la entrega.'
        Check (-not [IO.Directory]::Exists((Join-Path $vault '.viewtv-handoff-2'))) 'Escrow incorrecto.'
        $result['escritor_preabierto']='rechazado'
    } finally {$writer.Dispose()}
    & $publisher -SandboxRoot $root -StageName $stageName -FinalName 'ResultadoDos' -ApprovalName $approval -KeyPath $key -BrokerHandoff | Out-Null
    $result['cierre_y_reintento_de_prueba']='correcto'

    # Signed manifest tampered BEFORE handoff must fail and preserve stage.
    $tampered=New-TestStage 3 'ResultadoTres'
    [IO.File]::WriteAllText($tampered.video,'contenido_manipulado')
    $blocked=$false
    try {Publish-TestStage $tampered | Out-Null} catch {$blocked=$true}
    Check $blocked 'Manifest manipulado aceptado.'
    Check ([IO.Directory]::Exists($tampered.folder)) 'Handoff de datos alterados.'
    $result['sha_modificado_antes_de_entrega']='rechazado'

    $result | ConvertTo-Json -Compress
} finally {
    if($token -ne [IntPtr]::Zero){[ViewtvSandboxRestrictedToken]::DisposeToken($token)}
    if($key -and [IO.File]::Exists($key) -and
       [IO.Path]::GetFileName($key) -ceq 'key.bin' -and
       [IO.Path]::GetFileName([IO.Path]::GetDirectoryName($key)) -cmatch '^viewtv-test-key-[0-9a-f]{32}$' -and
       [IO.Path]::GetDirectoryName([IO.Path]::GetDirectoryName($key)) -ieq $env:TEMP){
        [IO.Directory]::Delete([IO.Path]::GetDirectoryName($key),$true)
    }
    if([IO.Directory]::Exists($root) -and
       [IO.Path]::GetDirectoryName($root) -ieq $public -and
       [IO.Path]::GetFileName($root) -cmatch '^viewtv-win-sandbox-[0-9a-f]{32}$' -and
       ([IO.DirectoryInfo]::new($root).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
       [IO.File]::Exists($marker) -and
       [IO.File]::ReadAllText($marker) -ceq ('VIEWTV_WINDOWS_SANDBOX_ONLY_V1'+[char]10)){
        foreach($item in (Get-ChildItem -LiteralPath $root -Recurse -Force)){
            if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
                throw 'Sandbox con enlaces, no se borra'
            }
        }
        [IO.Directory]::Delete($root,$true)
    }
}
