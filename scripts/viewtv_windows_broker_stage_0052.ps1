# VIEWTV 0052. Maintenance-only side-by-side Windows health service.
# It cannot touch qBittorrent, Jellyfin, media, firewall or production ACLs.
[CmdletBinding()]
param(
    [ValidateSet('Probe','Install','Rollback')][string]$Mode='Probe',
    [switch]$ApprovedMaintenance
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$name='VIEWTV-Broker-0052'
$root='C:\ProgramData\VIEWTV-Broker-0052'
$bin=[IO.Path]::Combine($root,'bin')
$data=[IO.Path]::Combine($root,'data')
$exe=[IO.Path]::Combine($bin,'viewtv-broker-health-0052.exe')
$state=[IO.Path]::Combine($data,'state.txt')
$marker=[IO.Path]::Combine($root,'VIEWTV-0052-MARKER.txt')
$markText='VIEWTV_0052_PRIVATE_HEALTH_ONLY'
$src=[IO.Path]::Combine($PSScriptRoot,'viewtv_broker_health_service_0052.cs')
$pipeName='viewtv-0052-inert-health'
$createdRoot=$false

function Is-Admin {
    $who=[Security.Principal.WindowsIdentity]::GetCurrent()
    $p=[Security.Principal.WindowsPrincipal]::new($who)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Existing-Service {
    return @(Get-Service -Name $name -ErrorAction SilentlyContinue).Count -gt 0
}
function Check-Exit([string]$stage) {
    if($LASTEXITCODE -ne 0){throw ('Fallo: '+$stage)}
}
function No-Reparse([string]$path) {
    if([IO.Directory]::Exists($path)){
        $info=[IO.DirectoryInfo]::new($path)
    }elseif([IO.File]::Exists($path)){
        $info=[IO.FileInfo]::new($path)
    }else{
        return
    }
    if(($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
        throw 'Ruta redirigida; no operar.'
    }
}
function Check-Owned {
    if(-not [IO.File]::Exists($marker) -or
       [IO.File]::ReadAllText($marker) -cne $markText){
        throw 'Marca de propiedad ajena al broker.'
    }
    foreach($path in @($root,$bin,$data,$exe,$marker,$state)){
        No-Reparse $path
    }
    $roots=@([IO.Directory]::GetFileSystemEntries($root))
    if(@($roots|Where-Object {$_ -cnotin @($bin,$data,$marker)}).Count){
        throw 'Entrada desconocida en la carpeta raíz.'
    }
    foreach($sub in @($bin,$data)){
        if(-not [IO.Directory]::Exists($sub)){throw 'Carpeta privada ausente.'}
    }
    if(@([IO.Directory]::GetFileSystemEntries($bin) |
       Where-Object {$_ -cne $exe}).Count){
        throw 'Binario desconocido.'
    }
    if(@([IO.Directory]::GetFileSystemEntries($data) |
       Where-Object {$_ -cne $state}).Count){
        throw 'Dato desconocido.'
    }
}
function Cleanup-Owned {
    if(-not (Is-Admin)){throw 'Reversión requiere elevación.'}
    Check-Owned
    if(Existing-Service) {
        $svc=Get-Service -Name $name -ErrorAction Stop
        if($svc.Status -ne 'Stopped'){
            Stop-Service -Name $name -ErrorAction Stop
            $svc.WaitForStatus('Stopped',[TimeSpan]::FromSeconds(20))
        }
        & sc.exe delete $name | Out-Null
        Check-Exit 'eliminación del servicio aislado'
    }
    foreach($file in @($state,$exe,$marker)){
        if([IO.File]::Exists($file)){[IO.File]::Delete($file)}
    }
    [IO.Directory]::Delete($bin,$false)
    [IO.Directory]::Delete($data,$false)
    [IO.Directory]::Delete($root,$false)
    Write-Output 'BROKER_0052_REVERTIDO=SI'
}
function Set-AdminOnly([string]$path){
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $allow=[Security.AccessControl.AccessControlType]::Allow
    $inherit=[Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    $prop=[Security.AccessControl.PropagationFlags]::None
    foreach($type in @(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,
        [Security.Principal.WellKnownSidType]::LocalSystemSid
    )){
        $sid=[Security.Principal.SecurityIdentifier]::new($type,$null)
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $sid,[Security.AccessControl.FileSystemRights]::FullControl,
            $inherit,$prop,$allow))
    }
    [IO.Directory]::SetAccessControl($path,$acl)
}
function Set-PrivateDir([string]$path,
    [Security.Principal.SecurityIdentifier]$sid,
    [Security.AccessControl.FileSystemRights]$rights){
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $inherit=[Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    $prop=[Security.AccessControl.PropagationFlags]::None
    $allow=[Security.AccessControl.AccessControlType]::Allow
    $ids=@(
        [Security.Principal.SecurityIdentifier]::new(
          [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null),
        [Security.Principal.SecurityIdentifier]::new(
          [Security.Principal.WellKnownSidType]::LocalSystemSid,$null)
    )
    foreach($id in $ids) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
           $id,[Security.AccessControl.FileSystemRights]::FullControl,
           $inherit,$prop,$allow))
    }
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
        $sid,$rights,$inherit,$prop,$allow))
    [IO.Directory]::SetAccessControl($path,$acl)
}
function Set-PrivateExe([Security.Principal.SecurityIdentifier]$sid){
    $acl=[Security.AccessControl.FileSecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $allow=[Security.AccessControl.AccessControlType]::Allow
    foreach($type in @(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,
        [Security.Principal.WellKnownSidType]::LocalSystemSid
    )){
        $id=[Security.Principal.SecurityIdentifier]::new($type,$null)
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $id,[Security.AccessControl.FileSystemRights]::FullControl,$allow))
    }
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
        $sid,[Security.AccessControl.FileSystemRights]::ReadAndExecute,$allow))
    [IO.File]::SetAccessControl($exe,$acl)
}
function Verify-State {
    Check-Owned
    $svc=Get-CimInstance Win32_Service -Filter "Name='VIEWTV-Broker-0052'" -ErrorAction Stop
    if($null -eq $svc -or
       $svc.StartName -cnotin @('NT AUTHORITY\LocalService',
                               'NT AUTHORITY\LOCAL SERVICE',
                               'NT AUTHORITY\Local Service') -or
       $svc.StartMode -cne 'Manual'){
        throw 'Servicio sin identidad o inicio correctos.'
    }
    # sc qsidtype uses localized output, not the literal English
    # UNRESTRICTED on Spanish Windows. Require query success; actual
    # SID membership is tested by the running service and its health proof.
    $null=(& sc.exe qsidtype $name | Out-String)
    Check-Exit 'consulta de SID de servicio'
    $nl=[string][char]10
    $expected=@(
        'IDENTIDAD_LOCALSERVICE=PASS',
        'SID_SERVICIO_EN_TOKEN=PASS',
        'PIPE_SOLO_SID_SERVICIO=PASS',
        'SELFTEST_HEALTH_EN_SERVICIO=PASS',
        'FUNCIONES_MEDIA_O_QBIT=NO',
        'CAMBIOS_CONFIG_PRODUCCION=0'
    ) -join $nl
    if(-not [IO.File]::Exists($state) -or
       [IO.File]::ReadAllText($state) -cne ($expected+$nl)){
        throw 'Self-test SID/canal no verificado.'
    }
    Write-Output 'SERVICIO_LOCALSERVICE_INDEPENDIENTE=PASS'
    Write-Output 'SERVICE_SID_PROPIO_NO_INTERACTIVO=PASS'
    Write-Output 'PIPE_SELFTEST_SERVICIO=PASS'
}

if($Mode -cne 'Probe' -and -not $ApprovedMaintenance){
    throw 'Instalar y revertir requieren aprobación explícita.'
}
if($Mode -ceq 'Probe'){
    Write-Output 'BROKER_0052=SONDEO_SOLO_LECTURA'
    Write-Output ('EXISTE_SERVICIO='+$(if(Existing-Service){'SI'}else{'NO'}))
    Write-Output ('EXISTE_DIRECTORIO='+$(if([IO.Directory]::Exists($root)){'SI'}else{'NO'}))
    Write-Output 'MODIFICACIONES=0'
}elseif($Mode -ceq 'Rollback'){
    Cleanup-Owned
    Write-Output 'QBIT_Y_JELLYFIN_MODIFICADOS=0'
    Write-Output 'MEDIOS_MODIFICADOS=0'
}else{
    if(-not (Is-Admin)){throw 'Instalación exige elevación.'}
    if((Existing-Service) -or [IO.Directory]::Exists($root) -or
       [IO.File]::Exists($root)){
        throw 'Servicio o carpeta 0052 existentes; no sobrescribir.'
    }
    No-Reparse $src
    if(-not [IO.File]::Exists($src)){throw 'Fuente C# ausente.'}
    $compiler=[IO.Path]::Combine($env:WINDIR,'Microsoft.NET',
        'Framework64','v4.0.30319','csc.exe')
    if(-not [IO.File]::Exists($compiler)){throw 'Compilador .NET ausente.'}
    try{
        [IO.Directory]::CreateDirectory($root)|Out-Null
        $createdRoot=$true
        # Close ProgramData inheritance immediately, BEFORE placing an EXE.
        Set-AdminOnly $root
        [IO.Directory]::CreateDirectory($bin)|Out-Null
        [IO.Directory]::CreateDirectory($data)|Out-Null
        [IO.File]::WriteAllText($marker,$markText)
        $compilation=@(& $compiler '/nologo' '/target:exe' ('/out:'+$exe) '/reference:System.ServiceProcess.dll' '/reference:System.Core.dll' $src 2>&1)
        if($LASTEXITCODE -ne 0) {
            foreach($line in @($compilation | Select-Object -First 12)) {
                Write-Output ('COMPILADOR_DIAGNOSTICO=' + [string]$line)
            }
            throw 'Compilador rechazó el servicio inerte.'
        }
        if(-not [IO.File]::Exists($exe)){throw 'Sin binario compilado.'}
        $creation=@(& sc.exe create $name 'binPath=' $exe 'obj=' 'NT AUTHORITY\LocalService' 'start=' 'demand' 'DisplayName=' 'VIEWTV Broker Health Sandbox 0052' 2>&1)
        if($LASTEXITCODE -ne 0){
            foreach($line in @($creation | Select-Object -First 10)){
                Write-Output ('SC_CREATE_DIAGNOSTICO='+[string]$line)
            }
            throw 'No se pudo crear servicio LocalService.'
        }
        & sc.exe sidtype $name unrestricted | Out-Null
        Check-Exit 'habilitar SID único'
        $sid=[Security.Principal.NTAccount]::new(
            'NT SERVICE\VIEWTV-Broker-0052').Translate(
              [Security.Principal.SecurityIdentifier])
        Set-PrivateDir $root $sid ([Security.AccessControl.FileSystemRights]::ReadAndExecute)
        Set-PrivateDir $bin $sid ([Security.AccessControl.FileSystemRights]::ReadAndExecute)
        Set-PrivateDir $data $sid ([Security.AccessControl.FileSystemRights]::Modify)
        Set-PrivateExe $sid
        Check-Owned
        Start-Service -Name $name -ErrorAction Stop
        $service=Get-Service -Name $name -ErrorAction Stop
        $service.WaitForStatus('Running',[TimeSpan]::FromSeconds(20))
        $until=[DateTime]::UtcNow.AddSeconds(12)
        while(-not [IO.File]::Exists($state) -and [DateTime]::UtcNow -lt $until){
            Start-Sleep -Milliseconds 150
        }
        Verify-State
        # Operator should be denied by Windows, not merely a missing pipe.
        $denied=$false
        foreach($attempt in 1..5){
            $client=[IO.Pipes.NamedPipeClientStream]::new(
                '.',$pipeName,[IO.Pipes.PipeDirection]::InOut)
            try{
                $client.Connect(1500)
                throw 'El operador entró en la tubería privada.'
            }catch [UnauthorizedAccessException]{
                $denied=$true
                break
            }catch [IO.IOException]{
                if($_.Exception.HResult -eq -2147024891){
                    $denied=$true
                    break
                }
                if($attempt -eq 5){throw}
                Start-Sleep -Milliseconds 150
            }finally{$client.Dispose()}
        }
        if(-not $denied){throw 'Denegación del operador no verificada.'}
        Write-Output 'CLIENTE_OPERADOR_EXCLUIDO_PIPE=PASS'
        Stop-Service -Name $name -ErrorAction Stop
        $service=Get-Service -Name $name -ErrorAction Stop
        $service.WaitForStatus('Stopped',[TimeSpan]::FromSeconds(20))
        Write-Output 'SERVICIO_MANUAL_Y_DETENIDO_TRAS_TEST=PASS'
        Write-Output 'BROKER_PRODUCTIVO_CON_CAPACIDAD_BORRADO=NO'
        Write-Output 'QBIT_Y_JELLYFIN_MODIFICADOS=0'
        Write-Output 'PELICULAS_REALES_ELIMINADAS=0'
        Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
    }catch{
        Write-Output 'INSTALACION_0052_FALLO=SI'
        if($createdRoot){
            try{Cleanup-Owned}
            catch{Write-Output 'ROLLBACK_0052_REQUIERE_REVISION_MANUAL=SI'}
        }
        throw
    }
}
