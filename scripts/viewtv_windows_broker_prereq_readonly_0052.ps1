# VIEWTV 0052: detect Windows installation prerequisites; no changes.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
try {
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $principal=[Security.Principal.WindowsPrincipal]::new($identity)
    $admin=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    $service=@(Get-Service -Name 'VIEWTV-Broker-0052' -ErrorAction SilentlyContinue)
    $task=@(Get-ScheduledTask -TaskName 'VIEWTV Broker 0052' -ErrorAction SilentlyContinue)
    $dir='C:\ProgramData\VIEWTV\broker-0052'
    $compiler=Test-Path -LiteralPath ([IO.Path]::Combine($env:WINDIR,
      'Microsoft.NET','Framework64','v4.0.30319','csc.exe')) -PathType Leaf
    $native=Get-Service -Name 'qBittorrent*' -ErrorAction SilentlyContinue
    Write-Output 'BROKER_0052_PREREQ=SOLO_LECTURA'
    Write-Output ('SESION_ADMIN_ELEVADA='+$(if($admin){'SI'}else{'NO'}))
    Write-Output ('SERVICIO_BROKER_0052_EXISTE='+$(if($service.Count){'SI'}else{'NO'}))
    Write-Output ('TAREA_BROKER_0052_EXISTE='+$(if($task.Count){'SI'}else{'NO'}))
    Write-Output ('CARPETA_BROKER_0052_EXISTE='+$(if([IO.Directory]::Exists($dir)){'SI'}else{'NO'}))
    Write-Output ('COMPILADOR_NET_FRAMEWORK_DISPONIBLE='+$(if($compiler){'SI'}else{'NO'}))
    Write-Output 'MODIFICACIONES_EFECTUADAS=0'
    Write-Output 'PROCESOS_QBIT_JELLYFIN_TOCADOS=0'
    Write-Output 'PELÍCULAS_ELIMINADAS=0'
} catch {
    Write-Output 'BROKER_0052_PREREQ=INCOMPLETA'
    Write-Output 'MODIFICACIONES_EFECTUADAS=0'
    exit 2
}