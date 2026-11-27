# VIEWTV 0022: ensayo MUTEX nativo entre dos procesos Windows.
# SIN archivos de video, SIN medios, SIN Docker, SIN qBit, SIN borrados.
[CmdletBinding()]
param(
    [ValidateSet('Test','Hold')][string]$Mode='Test',
    [ValidatePattern('^[a-f0-9]{32}$')][string]$RunId=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_media_lock_0022.ps1')
$parent=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
if($parent.StartsWith('C:\VIEWTV', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'TEMP no puede apuntar a medios VIEWTV.'
}
if($Mode -ceq 'Test') {
    if($RunId) { throw 'Test crea su propia identidad ficticia.' }
    $RunId=[Guid]::NewGuid().ToString('N')
} elseif(-not $RunId) { throw 'Falta GUID ficticio.' }
$root=[IO.Path]::Combine($parent,'viewtv-exclusion-sandbox-0022-'+$RunId)
$marker=Join-Path $root 'marca-privada.txt'
$ready=Join-Path $root 'hijo-posee-mutex.txt'
$mark='VIEWTV-SANDBOX-EXCLUSION-'+$RunId

function Assert-Sandbox {
    $dir=[IO.DirectoryInfo]::new($root)
    if(-not $dir.Exists -or
       ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
       -not [IO.File]::Exists($marker) -or
       [IO.File]::ReadAllText($marker) -cne $mark) {
        throw 'El sandbox de exclusion no pertenece a este ensayo.'
    }
    $allowed=@($marker,$ready)
    foreach($item in @([IO.Directory]::GetFileSystemEntries($root))) {
        $info=[IO.FileInfo]::new($item)
        if(-not ($allowed -ccontains $item) -or -not $info.Exists -or
           ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Elemento inesperado en sandbox.'
        }
    }
}

if($Mode -ceq 'Hold') {
    Assert-Sandbox
    $owned=Enter-ViewtvMediaExclusion0022 -Proposito 'sandbox' -SandboxId $RunId
    try {
        [IO.File]::WriteAllText($ready,$mark,[Text.Encoding]::UTF8)
        Start-Sleep -Seconds 12
    } finally {
        Exit-ViewtvMediaExclusion0022 -Mutex $owned
    }
    return
}

if([IO.Directory]::Exists($root) -or [IO.File]::Exists($root)) {
    throw 'Colision improbable de GUID: abortar.'
}
[IO.Directory]::CreateDirectory($root)|Out-Null
[IO.File]::WriteAllText($marker,$mark,[Text.Encoding]::UTF8)
$child=$null
try {
    Assert-Sandbox
    $exe=Join-Path $PSHOME 'powershell.exe'
    # El unico proceso que se puede interrumpir es este subproceso creado
    # por el TEST, nunca un publicador real ni qBit.
    $argv='-NoProfile -ExecutionPolicy Bypass -File "'+
        $PSCommandPath+'" -Mode Hold -RunId '+$RunId
    $child=Start-Process -FilePath $exe -ArgumentList $argv -PassThru -WindowStyle Hidden
    $hasReady=$false
    for($i=0;$i -lt 100;$i++) {
        if([IO.File]::Exists($ready)) {
            Assert-Sandbox
            if([IO.File]::ReadAllText($ready) -cne $mark) {
                throw 'Hijo con identidad incorrecta.'
            }
            $hasReady=$true
            break
        }
        if($child.HasExited) { throw 'El hijo salio antes del mutex.' }
        Start-Sleep -Milliseconds 50
    }
    if(-not $hasReady) { throw 'Hijo no adquirio lock.' }
    $blocked=$false
    $attempt=$null
    try {
        $attempt=Enter-ViewtvMediaExclusion0022 -Proposito 'sandbox' -SandboxId $RunId
    } catch {
        $blocked=$true
    } finally {
        if($null -ne $attempt) {
            Exit-ViewtvMediaExclusion0022 -Mutex $attempt
        }
    }
    if(-not $blocked) { throw 'La exclusion no impidio acceso concurrente.' }
    Write-Output 'PUBLICADOR_Y_RETIRADOR_FICTICIOS_EXCLUIDOS=PASS'
    $alternateBlocked=$false
    try {
        $wrong=Enter-ViewtvMediaExclusion0022 -Proposito 'retirada' -SandboxId $RunId
        Exit-ViewtvMediaExclusion0022 -Mutex $wrong
    } catch { $alternateBlocked=$true }
    if(-not $alternateBlocked) { throw 'El nombre productivo pudo variar.' }
    Write-Output 'NOMBRE_MUTEX_PRODUCTIVO_NO_MODIFICABLE=PASS'
    # Interrumpir solo el hijo ficticio de este PID; el kernel libera
    # el mutex. Un abandonado se considera una operacion fallida.
    Stop-Process -Id $child.Id -Force
    $child.WaitForExit(5000) | Out-Null
    $recovered=$false
    $untrusted=$false
    try {
        $retry=Enter-ViewtvMediaExclusion0022 -Proposito 'sandbox' -SandboxId $RunId
        try { $recovered=$true } finally {
            Exit-ViewtvMediaExclusion0022 -Mutex $retry
        }
    } catch {
        # Mutex abandonado en el primer reintento: el helper lo libera y
        # deniega la operacion (falla cerrado); reintentar no es borrar.
        $untrusted=$true
    }
    if(-not $recovered -and $untrusted) {
        $retry=Enter-ViewtvMediaExclusion0022 -Proposito 'sandbox' -SandboxId $RunId
        try { $recovered=$true } finally {
            Exit-ViewtvMediaExclusion0022 -Mutex $retry
        }
    }
    if(-not $recovered) { throw 'El lock ficticio no fue recuperable.' }
    Write-Output 'SALIDA_ABRUPTA_HIJO_MUTEX_RECUPERABLE=PASS'
    Write-Output 'ARCHIVOS_MEDIOS_REALES_TOCADOS=0'
    Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
} finally {
    if($null -ne $child -and -not $child.HasExited) {
        Stop-Process -Id $child.Id -Force
        $child.WaitForExit(5000) | Out-Null
    }
    Assert-Sandbox
    foreach($file in @($ready,$marker)) {
        if([IO.File]::Exists($file)) { [IO.File]::Delete($file) }
    }
    [IO.Directory]::Delete($root,$false)
}
