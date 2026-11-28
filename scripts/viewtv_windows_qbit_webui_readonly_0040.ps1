# VIEWTV 0040: inventario WebUI/GUI de qBit en Windows, solo lectura.
# Nunca revela claves, hashes de contraseñas, direcciones o rutas.
# Ningún parámetro, escritura, cambio de firewall o control de proceso.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Emit-Incomplete {
    Write-Output 'QBIT_WEBUI_0040=INCOMPLETA'
    Write-Output 'BROKER_SECRETO_EXCLUSIVO=NO_VERIFICADO'
    Write-Output 'GUI_BLOQUEADA_PARA_REANUDAR=NO_VERIFICADA'
    Write-Output 'FILE_ID_SIN_ESCRITORES=NO_VERIFICADO'
    Write-Output 'PERMISO_DE_BORRADO_OTORGADO=NO'
    Write-Output 'ARCHIVOS_ELIMINADOS=0'
    Write-Output 'TORRENTS_MODIFICADOS=0'
    Write-Output 'CAUSA=EVIDENCIA_NO_DISPONIBLE'
}
function YesNo([bool]$value) {
    if($value){return 'SI'}
    return 'NO'
}
try {
    $processes=@(Get-CimInstance Win32_Process -Filter "Name='qbittorrent.exe'" -ErrorAction Stop)
    if($processes.Count -ne 1) { throw 'Instancia nativa no unica.' }
    $qPid=[int]$processes[0].ProcessId
    if($qPid -le 0) { throw 'PID no verificable.' }
    $owner=Invoke-CimMethod -InputObject $processes[0] -MethodName GetOwnerSid -ErrorAction Stop
    if($owner.ReturnValue -ne 0 -or
       [string]$owner.Sid -cnotmatch '^S-1-[0-9-]{4,}$') {
        throw 'Identidad del proceso no verificable.'
    }
    $mySid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $sameSid=[string]$owner.Sid -ceq [string]$mySid

    $listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object {
        [int]$_.OwningProcess -eq $qPid
    })
    if($listeners.Count -eq 0){throw 'No hay listeners qBit verificables.'}
    $external=@($listeners | Where-Object {
        [string]$_.LocalAddress -notin @('127.0.0.1','::1')
    }).Count -gt 0

    # SOLO conexiones WebUI. Los peers del torrent usan otros puertos:
    # nunca publicar las direcciones de los clientes ni de los peers.
    $webUiExternal=@(Get-NetTCPConnection -State Established -ErrorAction Stop |
        Where-Object {
            [int]$_.OwningProcess -eq $qPid -and
            [int]$_.LocalPort -eq 8080 -and
            [string]$_.RemoteAddress -notin @('127.0.0.1','::1')
        }).Count -gt 0

    $broad=$false
    $rules=@(Get-NetFirewallRule -PolicyStore ActiveStore -ErrorAction Stop |
        Where-Object {
            $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and
            $_.Action -eq 'Allow'
        })
    foreach($rule in $rules) {
        $app=@($rule|Get-NetFirewallApplicationFilter -ErrorAction Stop)
        if(@($app|Where-Object { [string]$_.Program -match '(?i)[\\/]qbittorrent\.exe$' }).Count -eq 0){
            continue
        }
        $ports=@($rule|Get-NetFirewallPortFilter -ErrorAction Stop)
        $addresses=@($rule|Get-NetFirewallAddressFilter -ErrorAction Stop)
        if($ports.Count -ne 1 -or $addresses.Count -ne 1) {
            throw 'Filtros firewall ambiguos.'
        }
        if(
            [string]$addresses[0].RemoteAddress -eq 'Any' -and
            [string]$ports[0].LocalPort -in @('Any','8080') -and
            [string]$ports[0].Protocol -in @('TCP','Any')
        ) {
            $broad=$true
        }
    }

    # El fichero del usuario actual NO necesariamente es el perfil real
    # del proceso qBit: puede iniciarse con opciones o perfiles distintos.
    # Solo consultar nombres de claves y booleans seguros en [WebUI].
    $config=[IO.Path]::Combine($env:APPDATA,'qBittorrent','qBittorrent.ini')
    $configInfo=[IO.FileInfo]::new($config)
    if(-not $configInfo.Exists -or
        ($configInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        $configInfo.Length -gt 1024*1024) {
        throw 'Configuracion WebUI inaccesible o redirigida.'
    }
    $section=''
    $seen=@{}
    foreach($line in [IO.File]::ReadAllLines($config)) {
        if($line -match '^\[([a-zA-Z0-9]+)\]$') {
            $section=[string]$Matches[1]
            continue
        }
        if($section -cne 'WebUI' -or $line -cnotmatch '^([^=]+)=(.*)$'){
            continue
        }
        $key=[string]$Matches[1]
        if($key -notin @('Enabled','APIKey','Password_PBKDF2')) {continue}
        if($seen.ContainsKey($key)){throw 'Clave WebUI repetida.'}
        $value=[string]$Matches[2]
        if($key -ceq 'Enabled'){
            if($value -notin @('true','false')){throw 'Flag WebUI no normalizado.'}
            $seen[$key]=$value -ceq 'true'
        } else {
            # Ni conservar ni mostrar los secretos: SOLO presencia no vacia.
            $seen[$key]=(-not [string]::IsNullOrWhiteSpace($value))
        }
    }
    if(-not $seen.ContainsKey('Enabled')) {
        throw 'Flag WebUI no declarado.'
    }

    Write-Output 'QBIT_WEBUI_0040=OBSERVACION_SOLO_LECTURA'
    Write-Output 'QBIT_INSTANCIA_NATIVA_UNICA=SI'
    Write-Output ('QBIT_PROCESO_SID_OPERADOR='+(YesNo $sameSid))
    Write-Output ('WEBUI_HABILITADA_CONFIG_OPERADOR='+(YesNo $seen['Enabled']))
    Write-Output ('WEBUI_APIKEY_EN_CONFIG='+(YesNo ($seen.ContainsKey('APIKey') -and $seen['APIKey'])))
    Write-Output ('WEBUI_PASSWORD_HASH_EN_CONFIG='+(YesNo ($seen.ContainsKey('Password_PBKDF2') -and $seen['Password_PBKDF2'])))
    Write-Output ('QBIT_LISTENER_EXTERNO='+(YesNo $external))
    Write-Output ('QBIT_FIREWALL_ALLOW_AMPLIA='+(YesNo $broad))
    Write-Output ('WEBUI_CONEXION_REMOTA_OBSERVADA='+(YesNo $webUiExternal))
    Write-Output 'WEBUI_CONFIG_VINCULADA_A_PROCESO=NO_VERIFICADA'
    Write-Output 'BROKER_SECRETO_EXCLUSIVO=NO_VERIFICADO'
    Write-Output 'GUI_BLOQUEADA_PARA_REANUDAR=NO_VERIFICADA'
    Write-Output 'FILE_ID_SIN_ESCRITORES=NO_VERIFICADO'
    Write-Output 'PERMISO_DE_BORRADO_OTORGADO=NO'
    Write-Output 'ARCHIVOS_ELIMINADOS=0'
    Write-Output 'TORRENTS_MODIFICADOS=0'
} catch {
    Emit-Incomplete
    exit 2
}
