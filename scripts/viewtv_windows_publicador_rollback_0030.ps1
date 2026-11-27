# VIEWTV 0030: rollback estricto del par publicador/mutex.
# Test = ensayo privado (no toca la instalación); Restore exige tarea Disabled.
[CmdletBinding()]
param(
    [ValidateSet('Test','Restore')][string]$Mode='Test',
    [Parameter(Mandatory)][string]$BackupDirectory
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root='C:\VIEWTV\publicador'
$bin=Join-Path $root 'bin'
$task='VIEWTV - Publicador automatico 0013'
$target=Join-Path $bin 'viewtv_windows_publicador_0013.ps1'
$helper=Join-Path $bin 'viewtv_windows_media_lock_0022.ps1'
$oldFile=Join-Path $BackupDirectory 'viewtv_windows_publicador_0013.ps1'
$manifestFile=Join-Path $BackupDirectory 'manifest.json'
$source='\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\viewtv_windows_publicador_0013.ps1'
function Get-ShaExact([string]$P) {
    $i=[IO.FileInfo]::new($P)
    if(-not $i.Exists -or ($i.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Archivo ausente o redirigido.'
    }
    (Get-FileHash -LiteralPath $P -Algorithm SHA256).Hash.ToUpperInvariant()
}
function Assert-Dir([string]$P) {
    $i=[IO.DirectoryInfo]::new($P)
    if(-not $i.Exists -or ($i.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Carpeta no segura.'
    }
}
function Assert-TaskDisabled {
    $t=Get-ScheduledTask -TaskName $task
    if([string]$t.State -cne 'Disabled' -or
       $t.Principal.RunLevel -cne 'Limited') { throw 'Tarea no inmovilizada.' }
    $active=@(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -ieq 'ViewtvPublicadorServicio0013.exe' -or
        ($_.Name -in @('powershell.exe','pwsh.exe') -and
         ([string]$_.CommandLine -match 'viewtv_windows_publicador_0013\.ps1|viewtv_publicador_tarea_periodica_0013\.ps1'))
    })
    if($active.Count -ne 0) { throw 'Proceso publicador en ejecución.' }
}
if($BackupDirectory -cnotmatch '^C:\\VIEWTV\\publicador\\respaldo-0030-[0-9]{8}-[0-9]{6}-[a-f0-9]{8}$') {
    throw 'Respaldo fuera del directorio privado.'
}
foreach($dir in @($root,$bin,$BackupDirectory)) {Assert-Dir $dir}
$m=[IO.File]::ReadAllText($manifestFile)|ConvertFrom-Json
if($m.version -cne '0030' -or $m.helper_installed_before -ne $false -or
   $m.state_before -cne 'Ready' -or
   [string]$m.old_sha256 -cne '9533A16D2031F89ADFF414C1A9E226BCD503C6357B7105978113403E573F9611' -or
   [string]$m.new_sha256 -cne '49765CF442D6084588F6BAF7B061BE4A29AD8DFFFA379B22681AECE17441993C' -or
   [string]$m.new_helper_sha256 -cne 'C1DBE8C78D53DBFDE75F50E2CE97A9A0FC0E2F55A3156952196DCA445B29A6C8' -or
   (Get-ShaExact $oldFile) -cne [string]$m.old_sha256) {
    throw 'Respaldo no coincide con los hashes aprobados.'
}
if($Mode -ceq 'Test') {
    $testDir=Join-Path $BackupDirectory ('ensayo-rollback-'+[guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($testDir)|Out-Null
    try {
        $current=Join-Path $testDir 'instalado.ps1'
        $stage=Join-Path $testDir 'original-stage.ps1'
        $discard=Join-Path $testDir 'reemplazado.ps1'
        [IO.File]::Copy($source,$current,$false)
        [IO.File]::Copy($oldFile,$stage,$false)
        if((Get-ShaExact $current) -cne [string]$m.new_sha256 -or
           (Get-ShaExact $stage) -cne [string]$m.old_sha256) {
            throw 'Ensayo: versiones distintas.'
        }
        [IO.File]::Replace($stage,$current,$discard,$true)
        if((Get-ShaExact $current) -cne [string]$m.old_sha256 -or
           (Get-ShaExact $discard) -cne [string]$m.new_sha256) {
            throw 'Ensayo: File.Replace no recuperó ambas versiones.'
        }
        'ROLLBACK_0030_PROCESO_INDEPENDIENTE=PASS'
        'ROLLBACK_0030_FILE_REPLACE_Y_HASHES=PASS'
        'PRODUCCION_MODIFICADA=NO'
    } finally {
        foreach($name in @('instalado.ps1','original-stage.ps1','reemplazado.ps1')) {
            $f=Join-Path $testDir $name
            if([IO.File]::Exists($f)){[IO.File]::Delete($f)}
        }
        [IO.Directory]::Delete($testDir,$false)
    }
} else {
    Assert-TaskDisabled
    $actual=Get-ShaExact $target
    if($actual -cnotin @([string]$m.old_sha256,[string]$m.new_sha256)) {
        throw 'Script desconocido: no restaurar ni reactivar.'
    }
    if([IO.File]::Exists($helper) -and
       (Get-ShaExact $helper) -cne [string]$m.new_helper_sha256) {
        throw 'Helper desconocido: no borrar.'
    }
    if($actual -ceq [string]$m.new_sha256) {
        $stage=Join-Path $bin ('rollback-0030-'+[guid]::NewGuid().ToString('N')+'.ps1')
        $discard=Join-Path $BackupDirectory ('version-descartada-'+[guid]::NewGuid().ToString('N')+'.ps1')
        [IO.File]::Copy($oldFile,$stage,$false)
        if((Get-ShaExact $stage) -cne [string]$m.old_sha256) {throw 'Copia de rollback distinta.'}
        [IO.File]::Replace($stage,$target,$discard,$true)
        if((Get-ShaExact $target) -cne [string]$m.old_sha256) {
            throw 'Rollback del script no verificable.'
        }
    }
    if([IO.File]::Exists($helper)) {
        [IO.File]::Delete($helper)
    }
    if((Get-ShaExact $target) -cne [string]$m.old_sha256 -or
       [IO.File]::Exists($helper)) {throw 'Rollback incompleto.'}
    'ROLLBACK_0030_PRODUCCION=RESTAURADA_ANTIGUA'
    'TAREA_SIGUE_DESHABILITADA=SI'
}
