# Instalación explícita: NO ejecutar hasta el backup consistente 0013
# y la aprobación de la ID de prueba. No modifica carpetas multimedia.
[CmdletBinding()]
param(
    [ValidateSet('Status','InstallSingle','Stop','Unregister')][string]$Mode='Status',
    [int]$AllowedDownloadId=0,
    [int]$AfterId=2,
    [string]$VerifiedBackup='',
    [string]$ExpectedSha256='',
    [switch]$AppControlServiceAuthorized
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ServiceName='ViewtvPublicador0013'
$Root='C:\VIEWTV\publicador'
$Bin=Join-Path $Root 'bin'
$Journal=Join-Path $Root 'journal'

function Assert-Admin {
    $p=[Security.Principal.WindowsPrincipal]::new(
        [Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'La instalación requiere sesión administrativa.'
    }
}
function Assert-Backup {
    if ($VerifiedBackup -cnotmatch '^/home/viewtv/viewtv-backups/[a-z0-9-]+-[0-9]{8}-[0-9]{6}\.tar\.gz$' -or
        $ExpectedSha256 -cnotmatch '^[a-f0-9]{64}$') {
        throw 'Respaldo verificable requerido antes de instalar.'
    }
    $sha=@(& wsl.exe -d Ubuntu-24.04 -- sha256sum $VerifiedBackup)
    if ($LASTEXITCODE -ne 0 -or $sha.Count -ne 1 -or
        -not $sha[0].StartsWith($ExpectedSha256+' ')) {
        throw 'La huella SHA256 del respaldo no coincide.'
    }
    $null=@(& wsl.exe -d Ubuntu-24.04 -- tar -tzf $VerifiedBackup)
    if ($LASTEXITCODE -ne 0) {
        throw 'No se puede leer el respaldo tar.gz.'
    }
}
function Set-PrivateViewtvAcl([string]$Path) {
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $user=[Security.Principal.WindowsIdentity]::GetCurrent().User
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null)
    $admins=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null)
    foreach($sid in @($user,$system,$admins)) {
        $rule=[Security.AccessControl.FileSystemAccessRule]::new(
            $sid,[Security.AccessControl.FileSystemRights]::FullControl,
            [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
            [Security.AccessControl.InheritanceFlags]::ObjectInherit,
            [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow)
        $acl.AddAccessRule($rule)
    }
    [IO.Directory]::SetAccessControl($Path,$acl)
}
if($Mode -eq 'Status') {
    $service=Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if($null -eq $service) { 'SERVICIO_NO_INSTALADO' }
    else { 'SERVICIO_'+$service.Status.ToString().ToUpperInvariant() }
    return
}
Assert-Admin
if($Mode -eq 'Stop') {
    & sc.exe stop $ServiceName
    if($LASTEXITCODE -notin @(0,1062)) { throw 'No se pudo detener el servicio.' }
    return
}
if($Mode -eq 'Unregister') {
    $service=Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if($service -and $service.Status -ne 'Stopped') {
        throw 'Detener el servicio antes de retirarlo.'
    }
    & sc.exe delete $ServiceName
    if($LASTEXITCODE -ne 0) { throw 'No se pudo retirar el registro SCM.' }
    # Mantener diario, políticas, scripts y medios: nunca borrar ni restaurar
    # una base de producción automáticamente.
    return
}
if($Mode -ne 'InstallSingle' -or $AllowedDownloadId -le $AfterId -or
    $AfterId -lt 1) {
    throw 'Se requiere una única ID nueva aprobada.'
}
if (-not $AppControlServiceAuthorized) {
    # El ensayo SCM sobre un ejecutable sintético devolvió 4551:
    # una directiva de Control de aplicaciones impidió arrancarlo.
    # No probar otras rutas para sortear la directiva ni instalar
    # un servicio real sin aprobación de la política de Windows.
    throw 'Se requiere habilitación administrativa en Control de aplicaciones.'
}
Assert-Backup
if([IO.Directory]::Exists($Root) -or
    $null -ne (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)) {
    throw 'Instalación previa existente: no sobrescribir.'
}
$media=[IO.DirectoryInfo]::new('C:\VIEWTV\media')
if(-not $media.Exists -or
    ($media.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
    [IO.DriveInfo]::new('C').DriveFormat -cne 'NTFS') {
    throw 'Raíz multimedia Windows no autorizada.'
}
$compiler='C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if(-not [IO.File]::Exists($compiler)) { throw 'Compilador Windows no disponible.' }
$sourcePS=Join-Path $PSScriptRoot 'viewtv_windows_publicador_0013.ps1'
$sourceCS=Join-Path $PSScriptRoot 'ViewtvPublicadorServicio0013.cs'
foreach($source in @($sourcePS,$sourceCS)) {
    if(-not [IO.File]::Exists($source)) { throw 'Falta código revisado.' }
}
[IO.Directory]::CreateDirectory($Root) | Out-Null
Set-PrivateViewtvAcl $Root
[IO.Directory]::CreateDirectory($Bin) | Out-Null
Set-PrivateViewtvAcl $Bin
[IO.Directory]::CreateDirectory($Journal) | Out-Null
Set-PrivateViewtvAcl $Journal
[IO.File]::Copy($sourcePS,(Join-Path $Bin 'viewtv_windows_publicador_0013.ps1'),$false)
[IO.File]::Copy($sourceCS,(Join-Path $Bin 'ViewtvPublicadorServicio0013.cs'),$false)
$approval=[ordered]@{
    mode='single'
    after_id=$AfterId
    allowed_download_id=$AllowedDownloadId
} | ConvertTo-Json -Compress
[IO.File]::WriteAllText((Join-Path $Root 'aprobacion.json'),$approval,
    [Text.Encoding]::UTF8)
$exe=Join-Path $Bin 'ViewtvPublicadorServicio0013.exe'
& $compiler /nologo /target:exe /reference:System.ServiceProcess.dll ("/out:"+$exe) (
    Join-Path $Bin 'ViewtvPublicadorServicio0013.cs')
if($LASTEXITCODE -ne 0) { throw 'No se compiló el servicio Windows.' }
# Por defecto DEMAND; no arrancar sin API+worker 0013 y prueba de origen.
& sc.exe create $ServiceName 'binPath=' $exe 'start=' 'demand' 'obj=' 'LocalSystem'
if($LASTEXITCODE -ne 0) { throw 'No se registró el servicio.' }
'WINDOWS_PUBLICADOR_0013_INSTALADO_DETENIDO'
