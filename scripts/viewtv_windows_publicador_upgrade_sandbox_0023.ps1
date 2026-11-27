# VIEWTV 0023: cambio/rollback de script y helper SOLO en TEMP GUID ficticio.
# No modifica C:\VIEWTV, servicios, tareas, SQLite, multimedia ni torrents.
[CmdletBinding()]
param(
    [ValidateSet('Test','Recover','Rollback')][string]$Mode='Test',
    [ValidatePattern('^[a-f0-9]{32}$')][string]$RunId=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($Mode -ceq 'Test') {
    if($RunId) { throw 'Test no admite un ID externo.' }
    $RunId=[Guid]::NewGuid().ToString('N')
} elseif(-not $RunId) { throw 'Falta identidad del ensayo.' }
$parent=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$root=Join-Path $parent ('viewtv-upgrade-ficticio-0023-'+$RunId)
if($parent.StartsWith('C:\VIEWTV', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'La ruta TEMP no es segura.'
}
$bin=Join-Path $root 'bin'
$stage=Join-Path $root 'stage'
$backup=Join-Path $root 'backup'
$installed=Join-Path $bin 'publicador-ficticio.ps1'
$helperInstalled=Join-Path $bin 'mutex-ficticio.ps1'
$stagedPub=Join-Path $stage 'publicador-stage.ps1'
$stagedMutex=Join-Path $stage 'mutex-stage.ps1'
$oldBackup=Join-Path $backup 'version-antigua.ps1'
$discard=Join-Path $backup 'version-sustituida-ficticia.ps1'
$marker=Join-Path $root 'marca.txt'
$intent=Join-Path $root '01-intencion.txt'
$recovered=Join-Path $root '02-recuperado.txt'
$updated=Join-Path $root '03-actualizado.txt'
$rolledBack=Join-Path $root '04-revertido.txt'
$sourcePub=Join-Path $PSScriptRoot 'viewtv_windows_publicador_0013.ps1'
$sourceLock=Join-Path $PSScriptRoot 'viewtv_windows_media_lock_0022.ps1'
$oldValue='VERSION_FICTICIA_ANTIGUA_'+$RunId
$markValue='VIEWTV_TEST_VERSIONES_0023_'+$RunId

function Write-Once([string]$Path,[string]$Text) {
    $bytes=[Text.Encoding]::UTF8.GetBytes($Text)
    $stream=[IO.FileStream]::new($Path,[IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,[IO.FileShare]::None,4096,
        [IO.FileOptions]::WriteThrough)
    try {
        $stream.Write($bytes,0,$bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
}
function Hash([string]$Path) {
    $info=[IO.FileInfo]::new($Path)
    if(-not $info.Exists -or
       ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Archivo de ensayo ausente o redirigido.'
    }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}
function Check-Match([string]$A,[string]$B) {
    if((Hash $A) -cne (Hash $B)) { throw 'SHA256 de version diferente.' }
}
function Assert-Sandbox {
    $check=[IO.DirectoryInfo]::new($root)
    if(-not $check.Exists -or
       ($check.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
       -not [IO.File]::Exists($marker) -or
       [IO.File]::ReadAllText($marker) -cne $markValue) {
        throw 'El directorio temporal no pertenece al ensayo.'
    }
    foreach($dir in @($bin,$stage,$backup)) {
        $info=[IO.DirectoryInfo]::new($dir)
        if(-not $info.Exists -or
           ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Subdirectorio no verificable.'
        }
    }
    $allowRoot=@($marker,$intent,$recovered,$updated,$rolledBack,$bin,$stage,$backup)
    $allowBin=@($installed,$helperInstalled)
    $allowStage=@($stagedPub,$stagedMutex)
    $allowBackup=@($oldBackup,$discard)
    foreach($spec in @(
        @{directory=$root;allow=$allowRoot},
        @{directory=$bin;allow=$allowBin},
        @{directory=$stage;allow=$allowStage},
        @{directory=$backup;allow=$allowBackup}
    )) {
        foreach($entry in @([IO.Directory]::GetFileSystemEntries($spec.directory))) {
            if($spec.allow -cnotcontains $entry) {
                throw 'Fichero ajeno detectado en sandbox.'
            }
            $info=[IO.FileInfo]::new($entry)
            if(($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Reparse point no permitido.'
            }
        }
    }
}
function Assert-Old {
    if([IO.File]::ReadAllText($installed) -cne $oldValue -or
       [IO.File]::Exists($helperInstalled)) {
        throw 'No se restauró el publicador ficticio original.'
    }
}
function Call-Other-Process([string]$StageName) {
    $exe=Join-Path $PSHOME 'powershell.exe'
    & $exe -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -Mode $StageName -RunId $RunId
    if($LASTEXITCODE -ne 0) { throw 'Proceso secundario rechazó recuperación.' }
}

if($Mode -ceq 'Test') {
    if([IO.File]::Exists($root) -or [IO.Directory]::Exists($root)) {
        throw 'GUID de ensayo ya usado.'
    }
    [IO.Directory]::CreateDirectory($root)|Out-Null
    foreach($dir in @($bin,$stage,$backup)) {
        [IO.Directory]::CreateDirectory($dir)|Out-Null
    }
    Write-Once $marker $markValue
    Write-Once $installed $oldValue
    Assert-Sandbox
    [IO.File]::Copy($sourcePub,$stagedPub,$false)
    [IO.File]::Copy($sourceLock,$stagedMutex,$false)
    Check-Match $sourcePub $stagedPub
    Check-Match $sourceLock $stagedMutex
    Write-Once $intent ('INTENCION_'+$RunId)
    [IO.File]::Replace($stagedPub,$installed,$oldBackup,$true)
    Check-Match $installed $sourcePub
    if([IO.File]::Exists($helperInstalled)) { throw 'Mutex apareció antes de tiempo.' }
    # Corte simulado entre script y helper, recuperación desde otro proceso.
    Call-Other-Process 'Recover'
    Call-Other-Process 'Recover'
    Assert-Old
    Write-Output 'RECUPERACION_VERSION_INCOMPLETA_EN_OTRO_PROCESO=PASS'
    [IO.File]::Copy($sourcePub,$stagedPub,$false)
    Check-Match $sourcePub $stagedPub
    [IO.File]::Replace($stagedPub,$installed,$oldBackup,$true)
    [IO.File]::Move($stagedMutex,$helperInstalled)
    Check-Match $installed $sourcePub
    Check-Match $helperInstalled $sourceLock
    Write-Once $updated ('INSTALACION_FICTICIA_COMPLETA_'+$RunId)
    Write-Output 'NUEVA_VERSION_Y_HELPER_FICTICIOS_SHA256=PASS'
    Call-Other-Process 'Rollback'
    Call-Other-Process 'Rollback'
    Assert-Old
    Write-Output 'ROLLBACK_VERSION_OTRO_PROCESO=PASS'
    Assert-Sandbox
    foreach($file in @(
        $discard,$oldBackup,$stagedPub,$stagedMutex,$helperInstalled,$installed,
        $rolledBack,$updated,$recovered,$intent,$marker
    )) {
        if([IO.File]::Exists($file)) { [IO.File]::Delete($file) }
    }
    foreach($dir in @($bin,$stage,$backup)) { [IO.Directory]::Delete($dir,$false) }
    [IO.Directory]::Delete($root,$false)
    Write-Output 'DIRECTORIO_SANDBOX_LIMPIADO=SI'
    Write-Output 'TAREA_PRODUCTIVA_MODIFICADA=NO'
    Write-Output 'PUBLICADOR_PRODUCTIVO_MODIFICADO=NO'
    Write-Output 'MEDIOS_Y_TORRENTS_MODIFICADOS=0'
} elseif($Mode -ceq 'Recover') {
    Assert-Sandbox
    if(-not [IO.File]::Exists($intent)) { throw 'Falta intención firmada por sandbox.' }
    if([IO.File]::Exists($recovered)) {
        Assert-Old
    } else {
        Check-Match $installed $sourcePub
        if([IO.File]::Exists($helperInstalled) -or
           [IO.File]::ReadAllText($oldBackup) -cne $oldValue) {
            throw 'El ensayo no está en el punto de corte aprobado.'
        }
        [IO.File]::Replace($oldBackup,$installed,$discard,$true)
        Assert-Old
        Check-Match $discard $sourcePub
        [IO.File]::Delete($discard)
        Write-Once $recovered ('RECUPERADO_'+$RunId)
    }
    Write-Output 'RECUPERACION_IDEMPOTENTE=PASS'
} else {
    Assert-Sandbox
    if(-not [IO.File]::Exists($updated)) { throw 'Sin actualización ficticia.' }
    if([IO.File]::Exists($rolledBack)) {
        Assert-Old
    } else {
        Check-Match $installed $sourcePub
        Check-Match $helperInstalled $sourceLock
        if([IO.File]::ReadAllText($oldBackup) -cne $oldValue) {
            throw 'Respaldo ficticio alterado.'
        }
        [IO.File]::Delete($helperInstalled)
        [IO.File]::Replace($oldBackup,$installed,$discard,$true)
        Assert-Old
        Check-Match $discard $sourcePub
        [IO.File]::Delete($discard)
        Write-Once $rolledBack ('ROLLBACK_COMPLETADO_'+$RunId)
    }
    Write-Output 'ROLLBACK_IDEMPOTENTE=PASS'
}
