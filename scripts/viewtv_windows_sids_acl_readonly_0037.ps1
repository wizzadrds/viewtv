# VIEWTV 0037: auditoría de identidades/ACL del host, solo lectura.
# Sin argumentos. No cambia cuentas, ACL, servicios, torrents ni multimedia.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Report-Blocked([string]$Status) {
    Write-Output ('SIDS_WINDOWS_0037=' + $Status)
    Write-Output 'RETIRADA_POR_SIDS_PREPARADA=NO'
    Write-Output 'AISLAMIENTO_KERNEL_ARCHIVOS_PRODUCCION=NO_VERIFICADO'
    Write-Output 'PERMISO_DE_BORRADO_OTORGADO=NO'
    Write-Output 'ARCHIVOS_REALES_ELIMINADOS=0'
    Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
}
function Yes-No-Unknown($value) {
    if($null -eq $value) { return 'DESCONOCIDO' }
    if([bool]$value) { return 'SI' }
    return 'NO'
}
try {
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $principal=[Security.Principal.WindowsPrincipal]::new($identity)
    $sid=[string]$identity.User.Value
    $isAdmin=$principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
    $owners=@{}
    $processes=@(Get-CimInstance Win32_Process -Filter (
        "Name='jellyfin.exe' OR Name='qbittorrent.exe'"
    ) -ErrorAction Stop)
    foreach($proc in $processes) {
        $name=([string]$proc.Name).ToLowerInvariant()
        if($name -notin @('jellyfin.exe','qbittorrent.exe')) {
            throw 'Proceso inesperado durante la auditoría.'
        }
        $owner=Invoke-CimMethod -InputObject $proc -MethodName GetOwnerSid -ErrorAction Stop
        if($owner.ReturnValue -ne 0 -or
           [string]$owner.Sid -cnotmatch '^S-1-[0-9-]{4,}$') {
            throw 'Propietario de proceso no verificable.'
        }
        if(-not $owners.ContainsKey($name)) { $owners[$name]=@() }
        $owners[$name]+=[string]$owner.Sid
    }
    $jfSame=$null
    $qbitSame=$null
    if($owners.ContainsKey('jellyfin.exe') -and
       $owners['jellyfin.exe'].Count -gt 0) {
        $jfSame=@($owners['jellyfin.exe'] |
            Where-Object {$_ -ceq $sid}).Count -gt 0
    }
    if($owners.ContainsKey('qbittorrent.exe') -and
       $owners['qbittorrent.exe'].Count -gt 0) {
        $qbitSame=@($owners['qbittorrent.exe'] |
            Where-Object {$_ -ceq $sid}).Count -gt 0
    }
    $task=Get-ScheduledTask -TaskName 'VIEWTV - Publicador automatico 0013' -ErrorAction Stop
    $taskSid=$null
    try {
        $ntAccount=[Security.Principal.NTAccount]::new(
            [string]$task.Principal.UserId
        )
        $taskSid=[string]($ntAccount.Translate(
            [Security.Principal.SecurityIdentifier])).Value
    } catch {
        $taskSid=$null
    }
    $publisherSame=$null
    if($null -ne $taskSid) { $publisherSame=$taskSid -ceq $sid }
    # Las ACL de raíz no prueban permisos efectivos: existen grupos,
    # handles antiguos, permisos en archivos y directorios externos.
    $paths=@(
        'C:\VIEWTV\media',
        'C:\VIEWTV\media\descargas_temporales',
        'C:\VIEWTV\media\Peliculas',
        'C:\VIEWTV\publicador\journal'
    )
    $protected=0
    foreach($path in $paths) {
        $dir=[IO.DirectoryInfo]::new($path)
        if(-not $dir.Exists -or
           ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Directorio Windows ausente o redirigido.'
        }
        $acl=[IO.Directory]::GetAccessControl($path)
        if($acl.AreAccessRulesProtected) { $protected++ }
    }
    $ephemeral=@(Get-LocalUser -ErrorAction Stop | Where-Object {
        $_.Description -ceq 'VIEWTV-0013-EPHEMERAL'
    })
    Write-Output 'SIDS_WINDOWS_0037=OBSERVADOS_SOLO_LECTURA'
    Write-Output ('OPERADOR_ADMIN_ELEVADO=' + (Yes-No-Unknown $isAdmin))
    Write-Output ('JELLYFIN_COMPARTE_SID_OPERADOR=' + (
        Yes-No-Unknown $jfSame
    ))
    Write-Output ('QBIT_COMPARTE_SID_OPERADOR=' + (
        Yes-No-Unknown $qbitSame
    ))
    Write-Output ('PUBLICADOR_COMPARTE_SID_OPERADOR=' + (
        Yes-No-Unknown $publisherSame
    ))
    Write-Output ('DIRECTORIOS_RAIZ_ACL_PROTEGIDAS=' +
        [string]$protected + '_DE_4')
    Write-Output ('CUENTAS_EFIMERAS_SIN_LIMPIAR=' +
        [string]$ephemeral.Count)
    Write-Output 'BROKER_SID_DISTINTO_EN_PRODUCCION=NO_VERIFICADO'
    Write-Output 'LECTORES_SIN_FILE_WRITE_ATTRIBUTES_EN_PRODUCCION=NO_VERIFICADO'
    Write-Output 'AISLAMIENTO_KERNEL_ARCHIVOS_PRODUCCION=NO_VERIFICADO'
    Write-Output 'RETIRADA_POR_SIDS_PREPARADA=NO'
    Write-Output 'PERMISO_DE_BORRADO_OTORGADO=NO'
    Write-Output 'ARCHIVOS_REALES_ELIMINADOS=0'
    Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
} catch {
    Report-Blocked 'EVIDENCIA_INCOMPLETA'
    exit 2
}
