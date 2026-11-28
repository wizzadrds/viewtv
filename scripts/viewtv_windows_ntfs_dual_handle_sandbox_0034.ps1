# VIEWTV 0034 — ensayo Win32 de dos handles DELETE sobre hardlinks TEMP.
# Sin parámetros, sin rutas reales, sin instalación ni comandos a servicios.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_retirada_auditoria_0016.ps1') -Mode Audit |
    Out-Null

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class ViewtvDualNative0034 {
    [StructLayout(LayoutKind.Sequential)]
    public struct DispositionInfoEx { public uint Flags; }

    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true,
      EntryPoint="CreateFileW")]
    public static extern SafeFileHandle OpenNative(
        string fileName, uint access, uint sharing, IntPtr security,
        uint creation, uint flags, IntPtr template);

    [DllImport("kernel32.dll", SetLastError=true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetFileInformationByHandle(
        SafeFileHandle file, int infoClass, ref DispositionInfoEx info,
        uint bufferSize);
}
'@

$parent=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$root=[IO.Path]::Combine($parent,
    'viewtv-dual-0034-ficticio-'+[Guid]::NewGuid().ToString('N'))
$source=[IO.Path]::Combine($root,'descarga-ficticia.bin')
$copy=[IO.Path]::Combine($root,'pelicula-ficticia.bin')
$extra=[IO.Path]::Combine($root,'otro-hardlink-ficticio.bin')
$mark=[IO.Path]::Combine($root,'marca-0034.txt')
$journal=[IO.Path]::Combine($root,'diario-sandbox-0034.jsonl')
$markValue='VIEWTV-DUAL-HANDLE-0034'
$created=$false

function Assert-PrivateSandbox {
    if(-not [IO.Directory]::Exists($root) -or
        [IO.Path]::GetFileName($root) -cnotmatch
            '^viewtv-dual-0034-ficticio-[a-f0-9]{32}$' -or
        -not $root.StartsWith($parent+'\',
            [StringComparison]::OrdinalIgnoreCase) -or
        $root.StartsWith('C:\VIEWTV\',
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'El ensayo no está confinado a TEMP.'
    }
    foreach($path in @($parent,$root)) {
        if(([IO.DirectoryInfo]::new($path).Attributes -band
            [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Redirección de directorio no permitida.'
        }
    }
    if(-not [IO.File]::Exists($mark) -or
        [IO.File]::ReadAllText($mark) -cne $markValue) {
        throw 'Marcador de ensayo ausente.'
    }
    foreach($file in [IO.Directory]::GetFileSystemEntries($root)) {
        $item=[IO.FileInfo]::new($file)
        if($file -cnotin @($source,$copy,$extra,$mark,$journal) -or
           ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Elemento externo o redirigido dentro del ensayo.'
        }
    }
}

function Write-Journal0034([string]$State, $Id) {
    if($State -cnotin @('PREPARADO','PRIMER_LINK_RETIRADO','RESTAURADO',
                       'RETIRADA_FINAL_PREPARADA','FINAL_PRIMER_LINK',
                       'FINAL_SEGUNDO_LINK','FINALIZADO') -or
        $null -eq $Id -or [int64]$Id.links -lt 1) {
        throw 'Estado o File ID de diario no verificable.'
    }
    $json=([ordered]@{
        version=1
        estado=$State
        volumen=[uint32]$Id.volume
        file_id_alto=[uint32]$Id.high
        file_id_bajo=[uint32]$Id.low
    } | ConvertTo-Json -Compress)
    $bytes=[Text.Encoding]::UTF8.GetBytes($json+[Environment]::NewLine)
    $stream=[IO.FileStream]::new(
        $journal,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::Write,
        [IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough
    )
    try {
        $null=$stream.Seek(0,[IO.SeekOrigin]::End)
        $stream.Write($bytes,0,$bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
}

function Open-DeleteHandle([string]$Path) {
    # DELETE(0x10000) + FILE_READ_ATTRIBUTES(0x80), FILE_SHARE_DELETE(4).
    # No se admite ningún acceso READ_DATA / WRITE_DATA mientras vive.
    $handle=[ViewtvDualNative0034]::OpenNative(
        $Path,[uint32]0x10080,[uint32]4,[IntPtr]::Zero,
        [uint32]3,[uint32]0,[IntPtr]::Zero)
    if($null -eq $handle -or $handle.IsInvalid) {
        $code=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
        if($null -ne $handle) { $handle.Dispose() }
        throw ('No se pudo reservar handle DELETE. Codigo Win32 '+$code)
    }
    return $handle
}
function Native-FileInfo($Handle) {
    $native=[ViewtvLinkAudit0016+FileInfoNative]::new()
    if(-not [ViewtvLinkAudit0016]::GetFileInformationByHandle(
        $Handle,[ref]$native)) { throw 'Identidad kernel no verificable.' }
    return $native
}
function Deny-Reader([string]$Path) {
    $stream=$null
    $blocked=$false
    try {
        $stream=[IO.FileStream]::new(
            $Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,
            [IO.FileShare]::ReadWrite)
    } catch [IO.IOException] {
        $blocked=$true
    } finally {
        if($null -ne $stream) { $stream.Dispose() }
    }
    if(-not $blocked) { throw 'El lector ha sorteado la custodia Win32.' }
}

if([IO.Directory]::Exists($root) -or [IO.File]::Exists($root)) {
    throw 'Colisión de GUID de ensayo.'
}
try {
    [IO.Directory]::CreateDirectory($root)|Out-Null
    $created=$true
    [IO.File]::WriteAllText($mark,$markValue)
    Assert-PrivateSandbox
    $payload=New-Object byte[] (128*1024)
    $random=[Security.Cryptography.RandomNumberGenerator]::Create()
    try{$random.GetBytes($payload)}finally{$random.Dispose()}
    [IO.File]::WriteAllBytes($source,$payload)
    if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
        $copy,$source,[IntPtr]::Zero)) { throw 'No se creó el hardlink ficticio.' }
    $a=File-Fingerprint $source
    $b=File-Fingerprint $copy
    if($a.links -ne 2 -or $b.links -ne 2 -or
       $a.volume -ne $b.volume -or $a.high -ne $b.high -or
       $a.low -ne $b.low) { throw 'Par inicial no verificable.' }

    Write-Journal0034 'PREPARADO' $a
    $one=$null
    $two=$null
    try {
        $one=Open-DeleteHandle $source
        $two=Open-DeleteHandle $copy
        $id1=Native-FileInfo $one
        $id2=Native-FileInfo $two
        if($id1.VolumeSerial -ne $id2.VolumeSerial -or
           $id1.IndexHigh -ne $id2.IndexHigh -or
           $id1.IndexLow -ne $id2.IndexLow -or
           $id1.Links -ne 2 -or $id2.Links -ne 2 -or
           ($id1.Attributes -band 0x400) -ne 0 -or
           ($id2.Attributes -band 0x400) -ne 0) {
            throw 'La identidad no es exactamente dos hardlinks normales.'
        }
        Deny-Reader $source
        Deny-Reader $copy
        Write-Output 'DOS_HANDLES_DELETE_MISMO_FILE_ID=PASS'
        Write-Output 'LECTORES_BLOQUEADOS_DURANTE_DOBLE_RESERVA=PASS'

        # Un tercero puede abrir una reserva DELETE-only compatible.
        # La prueba debe informar si es posible crear nuevos hardlinks;
        # nunca asumimos que FILE_SHARE_DELETE prohíbe otros cambios.
        $thirdCreated=[ViewtvLinkAudit0016]::CreateHardLinkW(
            $extra,$source,[IntPtr]::Zero)
        if($thirdCreated) {
            Write-Output 'TERCER_LINK_DURANTE_RESERVA=POSIBLE'
            Write-Output 'AISLAMIENTO_PRODUCCION_POR_SHARE_DELETE=INSUFICIENTE'
            # Sólo se permite retirar el enlace extra creado aquí, dentro
            # del sandbox temporal GUID. No se tocan extras reales de qBit.
            [IO.File]::Delete($extra)
            $again=Native-FileInfo $one
            if($again.Links -ne 2) {
                throw 'No se pudo restaurar la identidad ficticia exacta.'
            }
        } else {
            Write-Output 'TERCER_LINK_DURANTE_RESERVA=BLOQUEADO'
        }

        # FILE_DISPOSITION_INFO_EX = 21, flags DELETE | POSIX_SEMANTICS.
        # Simular una interrupción DESPUÉS del primer unlink ficticio:
        # soltar los handles, reconstruir el enlace por el File ID que
        # sigue vivo, y sólo entonces repetir la doble adquisición.
        $disp=[ViewtvDualNative0034+DispositionInfoEx]::new()
        $disp.Flags=[uint32]3
        if(-not [ViewtvDualNative0034]::SetFileInformationByHandle(
            $one,21,[ref]$disp,[uint32]4)) {
            $errorCode=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
            throw ('Disposicion Win32 primer enlace rechazada: '+$errorCode)
        }
        Write-Journal0034 'PRIMER_LINK_RETIRADO' $a
        $two.Dispose()
        $two=$null
        $one.Dispose()
        $one=$null
        if([IO.File]::Exists($source) -or -not [IO.File]::Exists($copy)) {
            throw 'El estado posterior al primer unlink no es reconciliable.'
        }
        $survivor=File-Fingerprint $copy
        if($survivor.links -ne 1 -or
           $survivor.volume -ne $a.volume -or
           $survivor.high -ne $a.high -or
           $survivor.low -ne $a.low) {
            throw 'Superviviente ficticio no coincide con el File ID previo.'
        }
        if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
            $source,$copy,[IntPtr]::Zero)) {
            throw 'No se pudo restaurar el enlace ficticio.'
        }
        $one=Open-DeleteHandle $source
        $two=Open-DeleteHandle $copy
        $again=Native-FileInfo $one
        if($again.Links -ne 2 -or $again.VolumeSerial -ne $a.volume -or
           $again.IndexHigh -ne $a.high -or $again.IndexLow -ne $a.low) {
            throw 'Identidad inconsistente después de reconciliación.'
        }
        Deny-Reader $copy
        Write-Journal0034 'RESTAURADO' $a
        Write-Output 'RESTAURAR_PRIMER_UNLINK_TRAS_CIERRE_SIMULADO=PASS'
        Write-Journal0034 'RETIRADA_FINAL_PREPARADA' $a
        if(-not [ViewtvDualNative0034]::SetFileInformationByHandle(
            $one,21,[ref]$disp,[uint32]4)) {
            $errorCode=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
            throw ('Segundo intento del primer unlink rechazado: '+$errorCode)
        }
        Write-Journal0034 'FINAL_PRIMER_LINK' $a
        Write-Output 'UNLINK_PRIMER_HARDLINK_CON_HANDLES_RETENIDOS=PASS'
        if(-not [ViewtvDualNative0034]::SetFileInformationByHandle(
            $two,21,[ref]$disp,[uint32]4)) {
            $errorCode=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
            throw ('Disposicion Win32 segundo enlace rechazada: '+$errorCode)
        }
        Write-Journal0034 'FINAL_SEGUNDO_LINK' $a
        Write-Output 'UNLINK_SEGUNDO_HARDLINK_CON_HANDLES_RETENIDOS=PASS'
    } finally {
        if($null -ne $two) { $two.Dispose() }
        if($null -ne $one) { $one.Dispose() }
    }

    if([IO.File]::Exists($source) -or [IO.File]::Exists($copy)) {
        throw 'Disposición no hizo desaparecer ambos nombres ficticios.'
    }
    Write-Journal0034 'FINALIZADO' $a
    $lines=@([IO.File]::ReadAllLines($journal))
    $states=@('PREPARADO','PRIMER_LINK_RETIRADO','RESTAURADO',
              'RETIRADA_FINAL_PREPARADA','FINAL_PRIMER_LINK',
              'FINAL_SEGUNDO_LINK','FINALIZADO')
    if($lines.Count -ne $states.Count) {
        throw 'Diario duradero incompleto.'
    }
    for($index=0;$index -lt $states.Count;$index++) {
        $entry=$lines[$index] | ConvertFrom-Json
        if($entry.version -ne 1 -or $entry.estado -cne $states[$index] -or
           $entry.volumen -ne $a.volume -or
           $entry.file_id_alto -ne $a.high -or
           $entry.file_id_bajo -ne $a.low) {
            throw 'Diario de identidad o etapas contradictorio.'
        }
    }
    Assert-PrivateSandbox
    Write-Output 'DIARIO_WRITE_THROUGH_Y_RECONCILIACION_FILE_ID=PASS'
    Write-Output 'ENSAYO_DOS_UNLINKS_NTFS_SIN_SOLTAR_HANDLES=PASS'
    Write-Output 'EJECUTOR_PRODUCCION_AUN_NO_IMPLEMENTADO=SI'
    Write-Output 'ARCHIVOS_REALES_ELIMINADOS=0'
    Write-Output 'TORRENTS_MODIFICADOS=0'
} finally {
    if($created -and [IO.Directory]::Exists($root)) {
        Assert-PrivateSandbox
        foreach($file in @($extra,$copy,$source,$journal,$mark)) {
            if([IO.File]::Exists($file)) { [IO.File]::Delete($file) }
        }
        [IO.Directory]::Delete($root,$false)
    }
}
