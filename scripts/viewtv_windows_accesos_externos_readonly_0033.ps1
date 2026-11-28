# VIEWTV 0033: auditoría observacional de rutas externas; NUNCA concede borrado.
# Sin argumentos, secretos, rutas de medios ni modificaciones a host/procesos.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Emit-FailClosed {
    param([string]$Reason = 'EVIDENCIA_NO_DISPONIBLE')
    Write-Output 'ACCESOS_EXTERNOS_0033=INCOMPLETO'
    Write-Output 'JELLYFIN_NATIVO_ESCUCHA_EXTERNA=DESCONOCIDO'
    Write-Output 'JELLYFIN_FIREWALL_ALLOW=DESCONOCIDO'
    Write-Output 'QBIT_ESCUCHA_EXTERNA=DESCONOCIDO'
    Write-Output 'QBIT_FIREWALL_ALLOW=DESCONOCIDO'
    Write-Output 'DOCKER_JELLYFIN_SOLO_LOCAL=DESCONOCIDO'
    Write-Output 'NTFS_EXCLUSION_KERNEL=NO_VERIFICADA'
    Write-Output 'CUSTODIA_QBIT=NO_VERIFICADA'
    Write-Output 'DRENAJE_EXTERNO=NO_VERIFICADO'
    Write-Output 'PERMISO_DE_BORRADO_OTORGADO=NO'
    Write-Output 'ARCHIVOS_ELIMINADOS=0'
    Write-Output 'TORRENTS_MODIFICADOS=0'
    Write-Output ('CAUSA=' + $Reason)
}

try {
    $tcp = @(Get-NetTCPConnection -State Listen -ErrorAction Stop)
    $owners = @{}
    foreach ($item in $tcp) {
        $pidKey = [string]$item.OwningProcess
        if (-not $owners.ContainsKey($pidKey)) {
            try {
                $proc = Get-Process -Id ([int]$item.OwningProcess) -ErrorAction Stop
                $owners[$pidKey] = ([string]$proc.ProcessName).ToLowerInvariant()
            } catch {
                $owners[$pidKey] = 'no_verificado'
            }
        }
    }

    # La identidad del proceso determina qué puerto se atribuye a cada lector.
    $nativeJellyfin = @($tcp | Where-Object {
        $owners[[string]$_.OwningProcess] -ceq 'jellyfin' -and
        $_.LocalAddress -in @('0.0.0.0','::')
    })
    $nativeQbit = @($tcp | Where-Object {
        $owners[[string]$_.OwningProcess] -ceq 'qbittorrent' -and
        $_.LocalAddress -in @('0.0.0.0','::')
    })
    $localDocker = @($tcp | Where-Object {
        $_.LocalPort -eq 8097 -and
        $_.LocalAddress -in @('127.0.0.1','::1')
    })
    $remoteDocker = @($tcp | Where-Object {
        $_.LocalPort -eq 8097 -and
        $_.LocalAddress -notin @('127.0.0.1','::1')
    })

    $jellyAllow = $false
    $qbitAllow = $false
    $firewall = @(Get-NetFirewallRule -PolicyStore ActiveStore -ErrorAction Stop |
        Where-Object {
            $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and
            $_.Action -eq 'Allow' -and
            $_.DisplayName -match '(?i)jellyfin|qbittorrent'
        })
    foreach ($rule in $firewall) {
        $apps = @($rule | Get-NetFirewallApplicationFilter -ErrorAction Stop)
        $ports = @($rule | Get-NetFirewallPortFilter -ErrorAction Stop)
        $addresses = @($rule | Get-NetFirewallAddressFilter -ErrorAction Stop)
        if ($ports.Count -ne 1 -or $addresses.Count -ne 1) {
            throw 'Filtros de regla no verificables.'
        }
        $isBroad = (
            [string]$ports[0].LocalPort -eq 'Any' -and
            [string]$addresses[0].RemoteAddress -eq 'Any'
        )
        if (-not $isBroad) { continue }
        foreach ($app in $apps) {
            $program = [string]$app.Program
            if ($program -match '(?i)[\\/]jellyfin\.exe$') { $jellyAllow = $true }
            if ($program -match '(?i)[\\/]qbittorrent\.exe$') { $qbitAllow = $true }
        }
    }

    function YesNo([bool]$value) {
        if ($value) { return 'SI' }
        return 'NO'
    }
    # Un resultado 'NO' en este inventario NO es una prueba negativa universal.
    Write-Output 'ACCESOS_EXTERNOS_0033=AUDITORIA_SOLO_LECTURA'
    Write-Output ('JELLYFIN_NATIVO_ESCUCHA_EXTERNA=' + (YesNo ($nativeJellyfin.Count -gt 0)))
    Write-Output ('JELLYFIN_FIREWALL_ALLOW=' + (YesNo $jellyAllow))
    Write-Output ('QBIT_ESCUCHA_EXTERNA=' + (YesNo ($nativeQbit.Count -gt 0)))
    Write-Output ('QBIT_FIREWALL_ALLOW=' + (YesNo $qbitAllow))
    Write-Output ('DOCKER_JELLYFIN_SOLO_LOCAL=' + (YesNo (
        $localDocker.Count -gt 0 -and $remoteDocker.Count -eq 0
    )))
    Write-Output 'NTFS_EXCLUSION_KERNEL=NO_VERIFICADA'
    Write-Output 'CUSTODIA_QBIT=NO_VERIFICADA'
    Write-Output 'DRENAJE_EXTERNO=NO_VERIFICADO'
    Write-Output 'PERMISO_DE_BORRADO_OTORGADO=NO'
    Write-Output 'ARCHIVOS_ELIMINADOS=0'
    Write-Output 'TORRENTS_MODIFICADOS=0'
} catch {
    Emit-FailClosed
    exit 2
}
