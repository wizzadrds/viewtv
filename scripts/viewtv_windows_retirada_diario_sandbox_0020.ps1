# VIEWTV 0020. SOLO DOS ARCHIVOS FICTICIOS creados en TEMP, nunca C:\VIEWTV.
# Tres modos internos; no acepta rutas, peliculas, torrents ni descargas.
[CmdletBinding()]
param(
    [ValidateSet('Test','Recover','Finish')][string]$Mode='Test',
    [ValidatePattern('^[a-f0-9]{32}$')][string]$RunId=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
# El script base tiene un parámetro propio llamado Mode; al cargarlo con
# dot-source, conservar el modo del sandbox para no aceptar otro implícito.
$requestedMode=$Mode
. (Join-Path $PSScriptRoot 'viewtv_windows_retirada_auditoria_0016.ps1') -Mode Audit |
    Out-Null
$Mode=$requestedMode

if ($Mode -ceq 'Test') {
    if ($RunId) { throw 'El ensayo no admite IDs externos.' }
    $RunId=[Guid]::NewGuid().ToString('N')
} elseif (-not $RunId) { throw 'Falta ID privado del ensayo.' }
$parent=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$root=[IO.Path]::GetFullPath(
    [IO.Path]::Combine($parent,'viewtv-0020-ficticio-'+$RunId))
if ($root -cne [IO.Path]::Combine($parent,'viewtv-0020-ficticio-'+$RunId) -or
    $root.StartsWith('C:\VIEWTV\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Ruta de ensayo no autorizada.'
}
$marker=Join-Path $root 'sandbox-privado.txt'
$source=Join-Path $root 'origen-ficticio.bin'
$target=Join-Path $root 'publicado-ficticio.bin'
$first=Join-Path $root '01-intent.json'
$restored=Join-Path $root '02-restored.json'
$closing=Join-Path $root '03-finalize-intent.json'
$unlinked=Join-Path $root '04-unlinked.json'
$finished=Join-Path $root '05-finished.json'
$all=@($marker,$source,$target,$first,$restored,$closing,$unlinked,$finished)
$markerValue='VIEWTV_0020_FICTICIO_'+$RunId
$expectedBytes=1048576L

function Write-Once([string]$Path,[string]$Value) {
    $bytes=[Text.Encoding]::UTF8.GetBytes($Value)
    $file=[IO.FileStream]::new($Path,[IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,[IO.FileShare]::None,4096,
        [IO.FileOptions]::WriteThrough)
    try {
        $file.Write($bytes,0,$bytes.Length)
        $file.Flush($true)
    } finally { $file.Dispose() }
}
function Assert-Sandbox {
    Assert-PlainDirectory $parent
    Assert-PlainDirectory $root
    $check=[IO.FileInfo]::new($marker)
    if(-not $check.Exists -or $check.Length -gt 100 -or
       ($check.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
       [IO.File]::ReadAllText($marker) -cne $markerValue) {
        throw 'Marca del sandbox no verificable.'
    }
    $entries=@([IO.Directory]::GetFileSystemEntries($root))
    if($entries.Count -gt $all.Count) {
        throw 'Carpeta del sandbox alterada.'
    }
    foreach($item in $entries) {
        $info=[IO.FileInfo]::new($item)
        if(-not ($all -ccontains $item) -or -not $info.Exists -or
           ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Archivo ajeno o redirigido en el sandbox.'
        }
    }
}
function Write-Phase([string]$Path,[string]$Phase,$Evidence) {
    $json=[ordered]@{
        version=1
        run=$RunId
        phase=$Phase
        bytes=$expectedBytes
        volume=[long]$Evidence.volume
        high=[long]$Evidence.high
        low=[long]$Evidence.low
    } | ConvertTo-Json -Compress
    Write-Once $Path $json
}
function Read-Phase([string]$Path,[string]$Phase) {
    Assert-Sandbox
    $info=[IO.FileInfo]::new($Path)
    if(-not $info.Exists -or $info.Length -lt 50 -or $info.Length -gt 1024) {
        throw 'Diario no disponible.'
    }
    $record=[IO.File]::ReadAllText($Path)|ConvertFrom-Json
    if($record.version -ne 1 -or $record.run -cne $RunId -or
       $record.phase -cne $Phase -or $record.bytes -ne $expectedBytes -or
       $null -eq $record.volume -or $null -eq $record.high -or
       $null -eq $record.low) { throw 'Diario de identidad inválida.' }
    return $record
}
function Assert-Fingerprint($Actual,$Expected,[int]$Links) {
    if($Actual.volume -ne $Expected.volume -or
       $Actual.high -ne $Expected.high -or
       $Actual.low -ne $Expected.low -or
       $Actual.bytes -ne $expectedBytes -or $Actual.links -ne $Links) {
        throw 'El objeto de ensayo no coincide con la huella NTFS.'
    }
}
function Assert-Both($Proof) {
    Assert-Fingerprint (File-Fingerprint $source) $Proof 2
    Assert-Fingerprint (File-Fingerprint $target) $Proof 2
}
function Invoke-Stage([string]$Phase) {
    $exe=Join-Path $PSHOME 'powershell.exe'
    & $exe -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -Mode $Phase -RunId $RunId
    if ($LASTEXITCODE -ne 0) { throw 'Proceso independiente falló.' }
}

if($Mode -ceq 'Test') {
    if([IO.Directory]::Exists($root) -or [IO.File]::Exists($root)) {
        throw 'Directorio de ensayo ya existente.'
    }
    [IO.Directory]::CreateDirectory($root)|Out-Null
    Write-Once $marker $markerValue
    $payload=New-Object byte[] $expectedBytes
    [IO.File]::WriteAllBytes($source,$payload)
    if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
        $target,$source,[IntPtr]::Zero)) { throw 'Hardlink de ensayo falló.' }
    Assert-Sandbox
    $proof=File-Fingerprint $source
    Assert-Both $proof
    Write-Phase $first 'intencion_antes_del_unlink' $proof
    # Simula corte: enlace publicado eliminado pero no se escribió fase nueva.
    [IO.File]::Delete($target)
    Assert-Fingerprint (File-Fingerprint $source) $proof 1
    Invoke-Stage 'Recover'
    # Repetir la recuperación debe ser idempotente, nunca error por
    # el diario ya presente tras un acuse de éxito perdido.
    Invoke-Stage 'Recover'
    $null=Read-Phase $restored 'restaurado_desde_proceso_nuevo'
    Assert-Both $proof
    Write-Output 'DIARIO_WRITETHROUGH_Y_RESTAURACION_POST_CORTE=PASS'
    Invoke-Stage 'Finish'
    Invoke-Stage 'Finish'
    $null=Read-Phase $finished 'finalizado'
    if([IO.File]::Exists($source) -or [IO.File]::Exists($target)) {
        throw 'Los dos nombres ficticios no desaparecieron.'
    }
    Write-Output 'AMBOS_HARDLINKS_FICTICIOS_RETIRADOS=PASS'
    Assert-Sandbox
    foreach($file in @($finished,$unlinked,$closing,$restored,$first,$marker)) {
        [IO.File]::Delete($file)
    }
    [IO.Directory]::Delete($root,$false)
    Write-Output 'DIRECTORIO_FICTICIO_LIMPIADO=SI'
    Write-Output 'PELICULAS_REALES_BORRADAS=0'
    Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
 } elseif($Mode -ceq 'Recover') {
    $proof=Read-Phase $first 'intencion_antes_del_unlink'
    if([IO.File]::Exists($target)) {
        Assert-Both $proof
    } else {
        Assert-Fingerprint (File-Fingerprint $source) $proof 1
        if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
            $target,$source,[IntPtr]::Zero)) { throw 'No se restauró sandbox.' }
        Assert-Both $proof
    }
    if([IO.File]::Exists($restored)) {
        $null=Read-Phase $restored 'restaurado_desde_proceso_nuevo'
    } else {
        Write-Phase $restored 'restaurado_desde_proceso_nuevo' $proof
    }
    Write-Output 'RECUPERACION_EN_PROCESO_WINDOWS_DISTINTO=PASS'
} else {
    $proof=Read-Phase $restored 'restaurado_desde_proceso_nuevo'
    if([IO.File]::Exists($finished)) {
        $null=Read-Phase $finished 'finalizado'
        if([IO.File]::Exists($source) -or [IO.File]::Exists($target)) {
            throw 'Se detectaron archivos después de finalizar.'
        }
        Write-Output 'FINALIZACION_REPETIDA_SIN_OPERACIONES=PASS'
        return
    }
    if([IO.File]::Exists($closing)) {
        $null=Read-Phase $closing 'intencion_antes_del_ultimo_unlink'
    } else {
        Assert-Both $proof
        Write-Phase $closing 'intencion_antes_del_ultimo_unlink' $proof
    }
    if([IO.File]::Exists($target)) {
        Assert-Both $proof
        [IO.File]::Delete($target)
    }
    if([IO.File]::Exists($source)) {
        Assert-Fingerprint (File-Fingerprint $source) $proof 1
    } elseif (-not [IO.File]::Exists($unlinked)) {
        throw 'La última referencia desapareció sin diario de paso anterior.'
    }
    if([IO.File]::Exists($unlinked)) {
        $null=Read-Phase $unlinked 'copia_retirada'
    } else {
        Write-Phase $unlinked 'copia_retirada' $proof
    }
    # SOLO EL ULTIMO ENLACE DEL ARCHIVO NUEVO DEL SANDBOX GUID.
    if([IO.File]::Exists($source)) {
        Assert-Fingerprint (File-Fingerprint $source) $proof 1
        [IO.File]::Delete($source)
    }
    Write-Phase $finished 'finalizado' $proof
    Write-Output 'DIARIO_DE_FINALIZACION_FICTICIA=PASS'
}
