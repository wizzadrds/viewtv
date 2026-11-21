# Registro DESHABILITADO de tarea Windows de usuario NO elevado.
# No modifica la política de publicación ni arranca ninguna descarga.
[CmdletBinding()]
param([switch]$RegisterDisabled)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not $RegisterDisabled) { throw 'Solo admite -RegisterDisabled.' }
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Registrar tarea requiere administrador, ejecutarla NO.'
}
$backup='/home/viewtv/viewtv-backups/publicador-auto-general-pre-20261122-003621.tar.gz'
$expected='672a3d896c70e113b88d21a1b32e6dc8b3224cc7412370f004c12fb0d80f11b6'
$hash=@(& wsl.exe -d Ubuntu-24.04 -- sha256sum $backup)
if($LASTEXITCODE -ne 0 -or $hash.Count -ne 1 -or
   -not $hash[0].StartsWith($expected+' ')) {
    throw 'Respaldo previo no coincide.'
}
$null=@(& wsl.exe -d Ubuntu-24.04 -- tar -tzf $backup)
if($LASTEXITCODE -ne 0) { throw 'Respaldo tar no verificable.' }
$probe='VIEWTV-0013-Sondeo-Usuario-Limitado'
$last=Get-ScheduledTaskInfo -TaskName $probe -ErrorAction Stop
$original=Get-ScheduledTask -TaskName $probe -ErrorAction Stop
$marker='C:\VIEWTV\publicador\journal\tarea-limitada-probe-0013.json'
if($last.LastTaskResult -ne 0 -or
   $original.Principal.RunLevel -cne 'Limited' -or
   -not [IO.File]::Exists($marker)) {
    throw 'Sondeo de usuario limitado no validado.'
}
$proof=Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
if($proof.resultado -cne 'SONDEO_LIMITADO_OK' -or $proof.elevada -ne $false -or
   $proof.acceso_docker -ne $true -or $proof.medios_solo_lectura -ne $true) {
    throw 'Evidencia del sondeo incorrecta.'
}
$src=Join-Path $PSScriptRoot 'viewtv_publicador_tarea_periodica_0013.ps1'
$dst='C:\VIEWTV\publicador\bin\viewtv_publicador_tarea_periodica_0013.ps1'
if(-not [IO.File]::Exists($src) -or [IO.File]::Exists($dst)) {
    throw 'Origen ausente o instalación anterior presente.'
}
$name='VIEWTV - Publicador automatico 0013'
if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
    throw 'La tarea existe; no sobrescribir.'
}
if(Get-Service ViewtvPublicador0013 -ErrorAction SilentlyContinue) {
    throw 'Ya existe un servicio publicador; no duplicar.'
}
[IO.File]::Copy($src,$dst,$false)
if((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash -cne
   (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash) {
    throw 'El publicador limitado no coincide con el código revisado.'
}
$exe=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$action=New-ScheduledTaskAction -Execute $exe -Argument (
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+
    $dst+'" -Mode Once'
)
# Cada cinco minutos si el usuario está conectado; también al iniciar sesión.
$trigger1=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(10) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$trigger2=New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
$user=New-ScheduledTaskPrincipal -UserId $identity.Name `
    -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
    -MultipleInstances IgnoreNew
$null=Register-ScheduledTask -TaskName $name -Action $action `
    -Trigger @($trigger1,$trigger2) -Principal $user -Settings $settings `
    -Description 'ViewTV solo futuras ID >3, 5min, usuario interactivo limitado.' `
    -ErrorAction Stop
$null=Disable-ScheduledTask -TaskName $name -ErrorAction Stop
$created=Get-ScheduledTask -TaskName $name -ErrorAction Stop
if($created.State -ne 'Disabled' -or
   $created.Principal.RunLevel -cne 'Limited' -or
   $created.Principal.LogonType -cne 'Interactive') {
    throw 'Tarea nueva no está desactivada o es elevada.'
}
Write-Output 'TAREA_PUBLICADOR_0013_REGISTRADA_DESHABILITADA=SI'
Write-Output 'TAREA_PUBLICADOR_0013_PRIVILEGIO=LIMITED'
Write-Output 'TAREA_PUBLICADOR_0013_LOGON=INTERACTIVE'
