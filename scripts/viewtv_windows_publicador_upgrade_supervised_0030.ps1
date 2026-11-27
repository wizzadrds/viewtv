# VIEWTV 0030, instalación supervisada de publicador + helper 0022.
# Requiere tarea Disabled y quiescencia ya probada en dos instantes.
[CmdletBinding()]
param([Parameter(Mandatory)][string]$BackupDirectory)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root='C:\VIEWTV\publicador'
$bin=Join-Path $root 'bin'
$task='VIEWTV - Publicador automatico 0013'
$scriptFile=Join-Path $bin 'viewtv_windows_publicador_0013.ps1'
$helper=Join-Path $bin 'viewtv_windows_media_lock_0022.ps1'
$wrapper=Join-Path $bin 'viewtv_publicador_tarea_periodica_0013.ps1'
$source='\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts'
$manifestFile=Join-Path $BackupDirectory 'manifest.json'
function Get-ShaExact([string]$P) {
    $f=[IO.FileInfo]::new($P)
    if(-not $f.Exists -or ($f.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Archivo ausente o reparse.'
    }
    (Get-FileHash -LiteralPath $P -Algorithm SHA256).Hash.ToUpperInvariant()
}
function Assert-PlainDir([string]$P) {
    $f=[IO.DirectoryInfo]::new($P)
    if(-not $f.Exists -or ($f.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Carpeta no verificable.'
    }
}
function Assert-Quiescent {
    $t=Get-ScheduledTask -TaskName $task
    if($t.State -cne 'Disabled' -or $t.Principal.RunLevel -cne 'Limited' -or
       $t.Principal.LogonType -cne 'Interactive') { throw 'La tarea no está confinada.' }
    $processes=@(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'ViewtvPublicadorServicio0013.exe' -or
        ($_.Name -in @('powershell.exe','pwsh.exe') -and
         ([string]$_.CommandLine -match 'viewtv_windows_publicador_0013\.ps1|viewtv_publicador_tarea_periodica_0013\.ps1'))
    })
    $unknown=@(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -in @('powershell.exe','pwsh.exe') -and $null -eq $_.CommandLine
    })
    $stages=@(Get-ChildItem -LiteralPath 'C:\VIEWTV\media\Peliculas' -Directory -Filter '.viewtv-publicando-*')
    $service=Get-Service -Name 'ViewtvPublicador0013' -ErrorAction SilentlyContinue
    if($processes.Count -ne 0 -or $unknown.Count -ne 0 -or
       $stages.Count -ne 0 -or $null -ne $service) { throw 'No existe quiescencia comprobable.' }
}
function Write-Stage([string]$Name,[string]$Text) {
    $path=Join-Path $BackupDirectory $Name
    $bytes=[Text.Encoding]::UTF8.GetBytes($Text)
    $stream=[IO.FileStream]::new($path,[IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,[IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough)
    try { $stream.Write($bytes,0,$bytes.Length);$stream.Flush($true) }
    finally { $stream.Dispose() }
}
function Assert-PrivateAcl([string]$P) {
    $acl=Get-Acl -LiteralPath $P
    $allowed=@(
        'S-1-5-18','S-1-5-32-544',
        [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    )
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if($rules.Count -lt 1 -or $rules.Count -gt 3) {throw 'ACL inesperada'}
    foreach($rule in $rules) {
        if($rule.AccessControlType -ne 'Allow' -or
           $allowed -cnotcontains $rule.IdentityReference.Value) {
            throw 'ACL con identidad ajena.'
        }
    }
}
if($BackupDirectory -cnotmatch '^C:\\VIEWTV\\publicador\\respaldo-0030-[0-9]{8}-[0-9]{6}-[a-f0-9]{8}$') {
    throw 'Respaldo fuera del directorio privado.'
}
foreach($dir in @($root,$bin,$BackupDirectory)) {Assert-PlainDir $dir}
if(-not (Get-Acl -LiteralPath $bin).AreAccessRulesProtected){throw 'bin no confinado'}
$m=[IO.File]::ReadAllText($manifestFile)|ConvertFrom-Json
if($m.version -cne '0030' -or $m.helper_installed_before -ne $false -or
   (Get-ShaExact (Join-Path $BackupDirectory 'viewtv_windows_publicador_0013.ps1')) -cne [string]$m.old_sha256 -or
   (Get-ShaExact $scriptFile) -cne [string]$m.old_sha256 -or
   (Get-ShaExact $wrapper) -cne [string]$m.wrapper_sha256 -or
   (Get-ShaExact (Join-Path $source 'viewtv_windows_publicador_0013.ps1')) -cne [string]$m.new_sha256 -or
   (Get-ShaExact (Join-Path $source 'viewtv_windows_media_lock_0022.ps1')) -cne [string]$m.new_helper_sha256 -or
   [IO.File]::Exists($helper)) {throw 'No coincide la pareja de versiones y respaldo'}
Assert-Quiescent
Start-Sleep -Seconds 3
Assert-Quiescent
$guid=[Guid]::NewGuid().ToString('N')
$stagePub=Join-Path $bin ('stage-0030-publicador-'+$guid+'.ps1')
$stageHelper=Join-Path $bin ('stage-0030-helper-'+$guid+'.ps1')
$replacedBackup=Join-Path $BackupDirectory ('file-replace-original-'+$guid+'.ps1')
try {
    [IO.File]::Copy((Join-Path $source 'viewtv_windows_publicador_0013.ps1'),$stagePub,$false)
    [IO.File]::Copy((Join-Path $source 'viewtv_windows_media_lock_0022.ps1'),$stageHelper,$false)
    if((Get-ShaExact $stagePub) -cne [string]$m.new_sha256 -or
       (Get-ShaExact $stageHelper) -cne [string]$m.new_helper_sha256) {
        throw 'Staging incorrecto.'
    }
    Assert-PrivateAcl $stagePub
    Assert-PrivateAcl $stageHelper
    Assert-Quiescent
    Write-Stage 'install-intent-0030.txt' ('INSTALACION_0030_INTENCION_'+$guid)
    [IO.File]::Replace($stagePub,$scriptFile,$replacedBackup,$true)
    if((Get-ShaExact $replacedBackup) -cne [string]$m.old_sha256 -or
       (Get-ShaExact $scriptFile) -cne [string]$m.new_sha256) {
        throw 'File.Replace no verificable.'
    }
    [IO.File]::Move($stageHelper,$helper)
    if((Get-ShaExact $helper) -cne [string]$m.new_helper_sha256 -or
       (Get-ShaExact $scriptFile) -cne [string]$m.new_sha256 -or
       (Get-ShaExact $wrapper) -cne [string]$m.wrapper_sha256 -or
       (Get-Acl -LiteralPath $scriptFile).Sddl -cne [string]$m.script_acl_sddl) {
        throw 'Postinstalacion de pareja/ACL no verificable.'
    }
    Assert-PrivateAcl $scriptFile
    Assert-PrivateAcl $helper
    Assert-Quiescent
    Write-Stage 'install-complete-0030.txt' ('INSTALACION_0030_COMPLETA_'+$guid)
    'PAREJA_0030_INSTALADA=SI'
    'FILE_REPLACE_RESPALDO_SHA256=PASS'
    'PUBLICADOR_INSTALADO_SHA256='+(Get-ShaExact $scriptFile)
    'HELPER_INSTALADO_SHA256='+(Get-ShaExact $helper)
    'WRAPPER_SIN_CAMBIOS=SI'
    'ACL_PRIVADAS_VERIFICADAS=SI'
    'TAREA_SIGUE_DISABLED=SI'
} catch {
    [Console]::Error.WriteLine('INSTALACION_0030_FALLIDA_REQUIERE_ROLLBACK')
    $rollback=Join-Path $BackupDirectory 'rollback-0030.ps1'
    & (Join-Path $PSHOME 'powershell.exe') -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $rollback -Mode Restore -BackupDirectory $BackupDirectory
    if($LASTEXITCODE -ne 0){[Console]::Error.WriteLine('ROLLBACK_0030_NO_CONFIRMADO_TAREA_DISABLED')}
    throw
} finally {
    foreach($f in @($stagePub,$stageHelper)) {
        if([IO.File]::Exists($f)) {[IO.File]::Delete($f)}
    }
}
