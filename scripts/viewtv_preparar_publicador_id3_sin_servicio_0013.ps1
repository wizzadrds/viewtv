# Prepara una autorización NTFS SINGLE para la descarga #3.
# No registra servicios ni inicia procesos; nunca publica multimedia aquí.
[CmdletBinding()]
param(
    [switch]$AuthorizeSingle,
    [string]$VerifiedBackup='/home/viewtv/viewtv-backups/publicacion-id3-pre-20261121-235826.tar.gz',
    [string]$ExpectedSha256='e9b9b9d738b0a84adcfae1600043b0daba0583926fe037f6554dcee55d39262f'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if (-not $AuthorizeSingle) { throw 'Requiere aprobación expresa SOLO ID3.' }
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Requiere un administrador local autorizado.'
}
if ($VerifiedBackup -cne '/home/viewtv/viewtv-backups/publicacion-id3-pre-20261121-235826.tar.gz' -or
    $ExpectedSha256 -cne 'e9b9b9d738b0a84adcfae1600043b0daba0583926fe037f6554dcee55d39262f') {
    throw 'El respaldo aprobado no coincide.'
}
$sha=@(& wsl.exe -d Ubuntu-24.04 -- sha256sum $VerifiedBackup)
if ($LASTEXITCODE -ne 0 -or $sha.Count -ne 1 -or
    -not $sha[0].StartsWith($ExpectedSha256+' ')) {
    throw 'Huella del tar.gz no verificada.'
}
$archive=@(& wsl.exe -d Ubuntu-24.04 -- tar -tzf $VerifiedBackup)
if ($LASTEXITCODE -ne 0 -or $archive -notcontains 'api-resultados-predeploy-20261121-235826.db') {
    throw 'El respaldo no contiene la SQLite esperada.'
}
if ([IO.DriveInfo]::new('C').DriveFormat -cne 'NTFS') {
    throw 'Volumen de publicación no es NTFS.'
}
foreach($path in @('C:\VIEWTV','C:\VIEWTV\media',
    'C:\VIEWTV\media\descargas_temporales','C:\VIEWTV\media\Peliculas')) {
    $dir=[IO.DirectoryInfo]::new($path)
    if (-not $dir.Exists -or
        ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Carpeta multimedia ausente o redirigida.'
    }
}
$service=Get-Service -Name 'ViewtvPublicador0013' -ErrorAction SilentlyContinue
if ($service) { throw 'Ya existe un servicio publicador: revisar.' }
$root='C:\VIEWTV\publicador'
if ([IO.Directory]::Exists($root) -or [IO.File]::Exists($root)) {
    throw 'Ya existe directorio del publicador: no sobrescribir.'
}
$source=Join-Path $PSScriptRoot 'viewtv_windows_publicador_0013.ps1'
if (-not [IO.File]::Exists($source)) {
    throw 'Script de publicación faltante.'
}
function Set-PrivateAcl([string]$Path) {
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $user=$identity.User
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
[IO.Directory]::CreateDirectory($root)|Out-Null
Set-PrivateAcl $root
$bin=Join-Path $root 'bin'
$journal=Join-Path $root 'journal'
foreach($dir in @($bin,$journal)) {
    [IO.Directory]::CreateDirectory($dir)|Out-Null
    Set-PrivateAcl $dir
}
$target=Join-Path $bin 'viewtv_windows_publicador_0013.ps1'
[IO.File]::Copy($source,$target,$false)
$policy=[ordered]@{mode='single';after_id=2;allowed_download_id=3}|ConvertTo-Json -Compress
[IO.File]::WriteAllText((Join-Path $root 'aprobacion.json'),$policy,[Text.Encoding]::UTF8)
# No persistir credenciales ni crear servicio LocalSystem.
Write-Output 'PUBLICADOR_ID3_DIRECTORIO_PRIVADO_PREPARADO=SI'
Write-Output 'AUTORIZACION_WINDOWS_SOLO_ID3=SI'
Write-Output 'SERVICIO_WINDOWS_INSTALADO=NO'
