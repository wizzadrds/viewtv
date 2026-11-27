# VIEWTV 0021: medicion de espacio libre con hardlinks SOLO FICTICIOS.
# No acepta rutas o IDs; nunca borra contenido en C:\VIEWTV ni toca qBit.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

. (Join-Path $PSScriptRoot 'viewtv_windows_retirada_auditoria_0016.ps1') -Mode Audit |
    Out-Null

Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class ViewtvSpaceSandbox0021 {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetDiskFreeSpaceExW(
        string directoryName,
        out ulong freeBytesAvailable,
        out ulong totalNumberOfBytes,
        out ulong totalNumberOfFreeBytes);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetVolumePathNameW(
        string fileName, StringBuilder volumePathName, uint bufferLength);
}
'@

function Get-VolumeRoot([string]$Path) {
    $buffer=[Text.StringBuilder]::new(512)
    if(-not [ViewtvSpaceSandbox0021]::GetVolumePathNameW(
        $Path,$buffer,512)) { throw 'No se pudo verificar el volumen Windows.' }
    return $buffer.ToString().TrimEnd('\').ToUpperInvariant()
}
function Free-Bytes([string]$Path) {
    [UInt64]$available=0
    [UInt64]$total=0
    [UInt64]$free=0
    if(-not [ViewtvSpaceSandbox0021]::GetDiskFreeSpaceExW(
        $Path,[ref]$available,[ref]$total,[ref]$free)) {
        throw 'No se pudo medir espacio libre del volumen.'
    }
    return [long]$available
}
function Assert-Sandbox {
    Assert-PlainDirectory $parent
    Assert-PlainDirectory $root
    if(-not [IO.File]::Exists($marker) -or
       [IO.File]::ReadAllText($marker) -cne $markValue) {
        throw 'Marca de carpeta temporal no verificable.'
    }
    $allowed=@($marker,$origin,$published)
    foreach($file in @([IO.Directory]::GetFileSystemEntries($root))) {
        $info=[IO.FileInfo]::new($file)
        if(-not ($allowed -ccontains $file) -or -not $info.Exists -or
           ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Sandbox contiene datos no previstos.'
        }
    }
}

$guid=[Guid]::NewGuid().ToString('N')
$parent=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$root=[IO.Path]::Combine($parent,'viewtv-0021-ficticio-'+$guid)
if([IO.Directory]::Exists($root) -or [IO.File]::Exists($root) -or
   $root.StartsWith('C:\VIEWTV\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Raiz temporal de ensayo no autorizada.'
}
$marker=Join-Path $root 'marker-private.txt'
$origin=Join-Path $root 'original-ficticio.bin'
$published=Join-Path $root 'publicado-ficticio.bin'
$markValue='VIEWTV_0021_FICTICIO_'+$guid
$size=8*1024*1024
$sameVolume=(Get-VolumeRoot $root) -ceq (Get-VolumeRoot 'C:\VIEWTV\media')
$made=$false
try {
    [IO.Directory]::CreateDirectory($root)|Out-Null
    [IO.File]::WriteAllText($marker,$markValue,[Text.Encoding]::UTF8)
    $made=$true
    Assert-Sandbox
    $before=Free-Bytes $root
    # Bytes pseudoaleatorios sin compresión trivial, exclusivos del sandbox.
    $payload=New-Object byte[] $size
    $random=[Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($payload) } finally { $random.Dispose() }
    $stream=[IO.FileStream]::new($origin,[IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,[IO.FileShare]::None,4096,
        [IO.FileOptions]::WriteThrough)
    try {
        $stream.Write($payload,0,$payload.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
    Assert-Sandbox
    $afterWrite=Free-Bytes $root
    if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
        $published,$origin,[IntPtr]::Zero)) { throw 'No se creo hardlink ficticio.' }
    $a=File-Fingerprint $origin
    $b=File-Fingerprint $published
    if($a.volume -ne $b.volume -or $a.high -ne $b.high -or
       $a.low -ne $b.low -or $a.links -ne 2 -or $b.links -ne 2 -or
       $a.bytes -ne $size) { throw 'No es un par de enlaces unico.' }
    $afterLink=Free-Bytes $root
    Assert-Sandbox
    [IO.File]::Delete($published)
    $check=File-Fingerprint $origin
    if($check.links -ne 1 -or $check.volume -ne $a.volume -or
       $check.high -ne $a.high -or $check.low -ne $a.low) {
        throw 'Primer unlink inesperado.'
    }
    $afterOne=Free-Bytes $root
    Assert-Sandbox
    [IO.File]::Delete($origin)
    $afterBoth=Free-Bytes $root
    if([IO.File]::Exists($origin) -or [IO.File]::Exists($published)) {
        throw 'Quedan enlaces ficticios.'
    }
    # Delta global observado: ruido/otras escrituras pueden afectar esta cifra.
    $estimated=[long]($afterBoth-$afterOne)
    Write-Output 'MEDICION_DISCO_GETDISKFREESPACEEXW=PASS'
    Write-Output ('VOLUMEN_SANDBOX_COINCIDE_CON_MEDIA='+$sameVolume.ToString().ToUpperInvariant())
    Write-Output ('TAMANO_LOGICO_ENSAYO_BYTES='+$size)
    Write-Output ('DELTA_LIBRE_AL_CREAR_BYTES='+[long]($afterWrite-$before))
    Write-Output ('DELTA_LIBRE_AL_CREAR_HARDLINK_BYTES='+[long]($afterLink-$afterWrite))
    Write-Output ('DELTA_LIBRE_AL_QUITAR_PRIMER_LINK_BYTES='+[long]($afterOne-$afterLink))
    Write-Output ('DELTA_LIBRE_AL_QUITAR_ULTIMO_LINK_BYTES='+$estimated)
    Write-Output 'DELTA_NO_ATRIBUIBLE_CON_CERTEZA=SI'
    Write-Output 'DOS_ENLACES_FICTICIOS_BORRADOS=PASS'
    Write-Output 'ARCHIVOS_REALES_BORRADOS=0'
    Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
} finally {
    if($made -and [IO.Directory]::Exists($root)) {
        Assert-Sandbox
        foreach($f in @($published,$origin,$marker)) {
            if([IO.File]::Exists($f)) { [IO.File]::Delete($f) }
        }
        [IO.Directory]::Delete($root,$false)
    }
}
