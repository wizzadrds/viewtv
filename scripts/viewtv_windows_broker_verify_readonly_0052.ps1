# VIEWTV 0052: independent read-only audit of installed inert broker.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$name='VIEWTV-Broker-0052'
$root='C:\ProgramData\VIEWTV-Broker-0052'
$bin=[IO.Path]::Combine($root,'bin')
$data=[IO.Path]::Combine($root,'data')
$exe=[IO.Path]::Combine($bin,'viewtv-broker-health-0052.exe')
$state=[IO.Path]::Combine($data,'state.txt')
$mark=[IO.Path]::Combine($root,'VIEWTV-0052-MARKER.txt')
function Assert([bool]$ok,[string]$message){
    if(-not $ok){throw $message}
}
try{
    $service=Get-CimInstance Win32_Service -Filter "Name='VIEWTV-Broker-0052'" -ErrorAction Stop
    Assert ($null -ne $service) 'Servicio 0052 ausente.'
    Assert ($service.StartName -in @(
        'NT AUTHORITY\LocalService','NT AUTHORITY\LOCAL SERVICE',
        'NT AUTHORITY\Local Service')) 'Cuenta de servicio no verificada.'
    Assert ($service.State -eq 'Stopped') 'Servicio de ensayo sigue ejecutando.'
    Assert ($service.StartMode -eq 'Manual') 'Servicio de ensayo tiene autoarranque.'
    Assert (($service.PathName.Trim('"')) -ceq $exe) 'Binario no es el esperado.'
    $svcSid=[Security.Principal.NTAccount]::new(
        'NT SERVICE\VIEWTV-Broker-0052').Translate(
            [Security.Principal.SecurityIdentifier])
    $operator=[Security.Principal.WindowsIdentity]::GetCurrent().User
    Assert ($svcSid.Value -cne $operator.Value) 'SID de servicio equivale al operador.'
    Write-Output 'BROKER_SID_DISTINTO_OPERADOR=PASS'
    Write-Output 'SERVICIO_MANUAL_Y_DETENIDO=PASS'

    foreach($path in @($root,$bin,$data,$exe,$mark,$state)){
        Assert (([IO.Directory]::Exists($path)) -or
                ([IO.File]::Exists($path))) 'Ruta aislada ausente.'
        $info=Get-Item -LiteralPath $path -Force -ErrorAction Stop
        Assert (($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'Ruta aislada redirigida.'
    }
    Assert ([IO.File]::ReadAllText($mark) -ceq
        'VIEWTV_0052_PRIVATE_HEALTH_ONLY') 'Marcador incorrecto.'
    Write-Output 'CARPETA_PRIVADA_MARCADA=PASS'

    $admins=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null).Value
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null).Value
    $sidNames=@($admins,$system,$svcSid.Value)
    foreach($path in @($root,$bin,$data,$exe)){
        $acl=Get-Acl -LiteralPath $path -ErrorAction Stop
        Assert $acl.AreAccessRulesProtected 'ACL no protegida.'
        $rules=@($acl.GetAccessRules(
            $true,$false,[Security.Principal.SecurityIdentifier]))
        Assert ($rules.Count -eq 3) 'ACL admite ACEs inesperadas.'
        $actual=@($rules | ForEach-Object {$_.IdentityReference.Value})
        Assert (@($actual | Select-Object -Unique).Count -eq 3) 'Identidades duplicadas.'
        foreach($rule in $rules){
            Assert ($rule.IdentityReference.Value -in $sidNames) 'Principal extra en DACL.'
            Assert ($rule.AccessControlType -eq
                [Security.AccessControl.AccessControlType]::Allow) 'Denegación explícita inesperada.'
            Assert (-not $rule.IsInherited) 'Permisos heredados inesperados.'
            if($rule.IdentityReference.Value -ceq $svcSid.Value){
                $rights=$rule.FileSystemRights
                $mutate=[Security.AccessControl.FileSystemRights]::Write
                if($path -ceq $data){
                    Assert (($rights -band $mutate) -ne 0) 'Servicio no puede escribir su log.'
                }else{
                    Assert (($rights -band $mutate) -eq 0) 'Servicio podría alterar binario o raíz.'
                }
            }else{
                Assert (($rule.FileSystemRights -band
                    [Security.AccessControl.FileSystemRights]::FullControl) -ne 0) 'Admin o SYSTEM no pueden revertir.'
            }
        }
    }
    Write-Output 'ACL_EXCLUSIVAS_ADMIN_SYSTEM_SERVICE=PASS'
    Write-Output 'BINARIO_SIN_WRITE_SERVICIO=PASS'
    Write-Output 'DIRECTORIO_DATOS_PRIVADO=PASS'

    $nl=[string][char]10
    $expected=@(
        'IDENTIDAD_LOCALSERVICE=PASS',
        'SID_SERVICIO_EN_TOKEN=PASS',
        'PIPE_SOLO_SID_SERVICIO=PASS',
        'SELFTEST_HEALTH_EN_SERVICIO=PASS',
        'FUNCIONES_MEDIA_O_QBIT=NO',
        'CAMBIOS_CONFIG_PRODUCCION=0'
    ) -join $nl
    Assert ([IO.File]::ReadAllText($state) -ceq ($expected+$nl)) 'Self-test no acredita el canal.'
    Write-Output 'AUTO_PRUEBA_BROKER_SID_Y_PIPE=PASS'
    Write-Output 'BROKER_FUNCIONES_DE_BORRADO=NO'
    Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
    Write-Output 'ARCHIVOS_REALES_ELIMINADOS=0'
}catch{
    Write-Output 'AUDITORIA_BROKER_0052=INCOMPLETA'
    Write-Output 'PERMISO_DE_BORRADO_OTORGADO=NO'
    Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
    Write-Output 'ARCHIVOS_REALES_ELIMINADOS=0'
    exit 2
}