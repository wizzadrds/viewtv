# Windows restricted-token ACL test — only NEW GUID sandbox in Windows Public.
# No local account, persistent service, or real production ACL changes.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_restricted_token_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_pipe_broker_sandbox.ps1')

$public=[IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
if($public -ine 'C:\Users\Public'){throw 'Raíz de ensayo no autorizada.'}
$root=Join-Path $public ('viewtv-win-sandbox-'+[Guid]::NewGuid().ToString('N'))
$mark='VIEWTV_WINDOWS_SANDBOX_ONLY_V1'+[char]10
$marker=Join-Path $root '.viewtv-win-sandbox-only'
$restrictedSid=[Security.Principal.SecurityIdentifier]::new(
  [Security.Principal.WellKnownSidType]::RestrictedCodeSid,$null)
$currentSid=[Security.Principal.WindowsIdentity]::GetCurrent().User
$systemSid=[Security.Principal.SecurityIdentifier]::new(
  [Security.Principal.WellKnownSidType]::LocalSystemSid,$null)
$adminSid=[Security.Principal.SecurityIdentifier]::new(
  [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null)
$all=[Security.AccessControl.FileSystemRights]::FullControl
$read=[Security.AccessControl.FileSystemRights]::ReadAndExecute
$modify=[Security.AccessControl.FileSystemRights]::Modify
$allow=[Security.AccessControl.AccessControlType]::Allow
$inherit=[Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
  [Security.AccessControl.InheritanceFlags]::ObjectInherit
$propagate=[Security.AccessControl.PropagationFlags]::None
$token=[IntPtr]::Zero
$results=[ordered]@{}

function New-FolderAcl([bool]$IncludeRestricted,[Security.AccessControl.FileSystemRights]$Access) {
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    foreach($sid in @($currentSid,$systemSid,$adminSid)){
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $sid,$all,$inherit,$propagate,$allow))
    }
    if($IncludeRestricted) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $restrictedSid,$Access,$inherit,$propagate,$allow))
    }
    return $acl
}
function Set-TestFileAcl([string]$File,[Security.AccessControl.FileSystemRights]$Access) {
    $acl=[Security.AccessControl.FileSecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    foreach($sid in @($currentSid,$systemSid,$adminSid)){
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $sid,$all,$allow))
    }
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
        $restrictedSid,$Access,$allow))
    [IO.File]::SetAccessControl($File,$acl)
}
function Set-BrokerOwner([string]$Path,[bool]$Directory) {
    if($Directory){
        $security=[IO.Directory]::GetAccessControl($Path)
        $security.SetOwner($adminSid)
        [IO.Directory]::SetAccessControl($Path,$security)
        $actual=[IO.Directory]::GetAccessControl($Path).GetOwner(
            [Security.Principal.SecurityIdentifier])
    } else {
        $security=[IO.File]::GetAccessControl($Path)
        $security.SetOwner($adminSid)
        [IO.File]::SetAccessControl($Path,$security)
        $actual=[IO.File]::GetAccessControl($Path).GetOwner(
            [Security.Principal.SecurityIdentifier])
    }
    if($actual.Value -cne $adminSid.Value){throw 'No se protegió propietario.'}
}
function Expect-Access([string]$Label,[string]$Operation,[string]$Path,
                       [string]$Expected,[string]$Value='dato de prueba') {
    $args=@{Token=$token;Root=$root;Operation=$Operation;Path=$Path;Text=$Value}
    $actual=Invoke-ViewtvRestrictedSandboxOperation @args
    if($actual -cne $Expected){
        throw ('Frontera ACL no validada: '+$Label+'; resultado='+$actual)
    }
    $results[$Label]=$actual
}
try {
    if([IO.Directory]::Exists($root) -or [IO.File]::Exists($root)){
        throw 'Carpeta de sandbox preexistente.'
    }
    [IO.Directory]::CreateDirectory($root)|Out-Null
    [IO.Directory]::SetAccessControl($root,(New-FolderAcl $true $read))
    Set-BrokerOwner $root $true
    [IO.File]::WriteAllText($marker,$mark)

    $stage=Join-Path $root '.viewtv-stage-1'
    $vault=Join-Path $root 'broker-private'
    [IO.Directory]::CreateDirectory($stage)|Out-Null
    [IO.Directory]::CreateDirectory($vault)|Out-Null
    [IO.Directory]::SetAccessControl($stage,(New-FolderAcl $true $modify))
    [IO.Directory]::SetAccessControl($vault,(New-FolderAcl $false $read))
    $secret=Join-Path $vault 'clave-ficticia.bin'
    $journal=Join-Path $vault 'registro-de-intencion.json'
    [IO.File]::WriteAllText($secret,'SOLO_PRUEBA_NO_CREDENCIAL_REAL')
    [IO.File]::WriteAllText($journal,'{"solo_prueba":true}')
    foreach($folder in @($stage,$vault)){ Set-BrokerOwner $folder $true }
    foreach($file in @($secret,$journal)){ Set-BrokerOwner $file $false }

    $token=[ViewtvSandboxRestrictedToken]::Create()
    if([ViewtvSandboxRestrictedToken]::StillAdministrator($token)){
        throw 'El token restringido conserva el rol Administradores.'
    }
    $results['token_sin_rol_administrador']='verificado'
    $video=Join-Path $stage 'video-ficticio.mkv'
    Expect-Access 'copia_escribe_staging' 'write' $video 'allowed' 'video_sintetico_inicial'
    Expect-Access 'copia_lee_staging' 'read' $video 'allowed'
    Expect-Access 'copia_no_lee_clave' 'read' $secret 'denied'
    Expect-Access 'copia_no_lee_diario' 'read' $journal 'denied'
    Expect-Access 'copia_no_modifica_diario' 'write' $journal 'denied'
    Expect-Access 'copia_no_publica_carpeta' 'mkdir' (Join-Path $root 'DestinoNoPermitido') 'denied'
    Expect-Access 'copia_no_cambia_acl_raiz' 'diracl' $root 'denied'
    Expect-Access 'copia_no_cambia_acl_clave' 'fileacl' $secret 'denied'
    if([IO.Directory]::Exists((Join-Path $root 'DestinoNoPermitido'))){
        throw 'Se creó un destino por el token restringido.'
    }

    # Only the normal broker test identity may change these DACLs.
    $before=(Get-FileHash -LiteralPath $video -Algorithm SHA256).Hash
    [IO.Directory]::SetAccessControl($stage,(New-FolderAcl $true $read))
    Set-TestFileAcl $video $read
    Set-BrokerOwner $video $false
    Expect-Access 'sellado_no_cambia_acl_video' 'fileacl' $video 'denied'
    Expect-Access 'sellado_no_cambia_acl_staging' 'diracl' $stage 'denied'
    Expect-Access 'sellado_no_escribe_video' 'write' $video 'denied' 'contenido_inyectado'
    Expect-Access 'sellado_no_crea_subtitulos' 'write' (Join-Path $stage 'falso.es.srt') 'denied' 'subtitulo_inyectado'
    Expect-Access 'sellado_sigue_leyendo_video' 'read' $video 'allowed'
    if((Get-FileHash -LiteralPath $video -Algorithm SHA256).Hash -cne $before){
        throw 'El vídeo cambió durante la prueba de sellado.'
    }

    # Full token performs NTFS Directory.Move without restricted user rights.
    $final=Join-Path $root 'Resultado ficticio'
    [IO.Directory]::Move($stage,$final)
    if([IO.Directory]::Exists($stage) -or
       -not [IO.File]::Exists((Join-Path $final 'video-ficticio.mkv')) -or
       (Get-FileHash -LiteralPath (Join-Path $final 'video-ficticio.mkv') -Algorithm SHA256).Hash -cne $before){
        throw 'El movimiento NTFS de la carpeta sellada no conservó el contenido.'
    }
    $results['broker_mueve_staging_sellado']='correcto'
    Expect-Access 'copia_no_modifica_publicado' 'write' (Join-Path $final 'video-ficticio.mkv') 'denied' 'alterado'

    # Important negative test: permissions sealed AFTER a handle was opened
    # do not revoke the previously granted WRITE access in that handle.
    $openStage=Join-Path $root '.viewtv-stage-2'
    [IO.Directory]::CreateDirectory($openStage)|Out-Null
    [IO.Directory]::SetAccessControl($openStage,(New-FolderAcl $true $modify))
    Set-BrokerOwner $openStage $true
    $openFile=Join-Path $openStage 'abierto.mkv'
    Expect-Access 'escritura_previa_a_sellado' 'write' $openFile 'allowed' 'ORIGINAL'
    $initialHash=(Get-FileHash -LiteralPath $openFile -Algorithm SHA256).Hash
    $held=[ViewtvSandboxRestrictedToken]::OpenWriteHandle($token,$openFile)
    try {
        [IO.Directory]::SetAccessControl($openStage,(New-FolderAcl $true $read))
        Set-TestFileAcl $openFile $read
        Set-BrokerOwner $openFile $false
        Expect-Access 'apertura_nueva_denegada_con_handle_antiguo' 'write' $openFile 'denied' 'OTRA'
        $mutated=[Text.Encoding]::UTF8.GetBytes('CAMBIADO')
        $held.Position=0
        $held.Write($mutated,0,$mutated.Length)
        $held.Flush()
        # Get-FileHash itself can fail with sharing violation while a write
        # handle exists: compare SHA only AFTER safely closing the handle.
        $moveRefused=$false
        try {
            [IO.Directory]::Move($openStage,(Join-Path $root 'NoMoverConHandle'))
        } catch [IO.IOException] { $moveRefused=$true }
        if(-not $moveRefused) { throw 'Mover una carpeta con un handle abierto no falló.' }
        $results['handle_abierto_bloquea_move']='demostrado'
    } finally { $held.Dispose() }
    if((Get-FileHash -LiteralPath $openFile -Algorithm SHA256).Hash -ceq $initialHash){
        throw 'El ensayo no reprodujo el acceso de escritura preexistente.'
    }
    $results['handle_preabierto_ignora_sellado']='demostrado'

    $pipeName='viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')
    $pipeServer=New-ViewtvBrokerNativeFirstPipe $pipeName (New-ViewtvBrokerPipeAcl)
    try {
        $pipeResult=[ViewtvSandboxRestrictedToken]::ProbePipe($token,$pipeName)
        if($pipeResult -cne 'denied'){
            throw ('La identidad restringida pudo abrir el pipe: '+$pipeResult)
        }
        $results['copia_no_abre_pipe_de_broker']='denied'
    } finally { $pipeServer.Dispose() }
    if(@((Get-ChildItem -LiteralPath $vault -Force)).Count -ne 2){
        throw 'La prueba alteró el diario o la clave.'
    }
    $results | ConvertTo-Json -Compress
} finally {
    if($token -ne [IntPtr]::Zero){
        [ViewtvSandboxRestrictedToken]::DisposeToken($token)
    }
    if([IO.Directory]::Exists($root) -and
       [IO.Path]::GetDirectoryName($root) -ieq $public -and
       [IO.Path]::GetFileName($root) -cmatch '^viewtv-win-sandbox-[0-9a-f]{32}$' -and
       ([IO.DirectoryInfo]::new($root).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
       [IO.File]::Exists($marker) -and
       [IO.File]::ReadAllText($marker) -ceq $mark){
        foreach($item in (Get-ChildItem -LiteralPath $root -Force -Recurse)){
            if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
                throw 'No se eliminará un sandbox que contiene enlaces.'
            }
        }
        [IO.Directory]::Delete($root,$true)
    }
}
