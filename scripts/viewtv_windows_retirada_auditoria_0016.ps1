# VIEWTV 0016: auditoría NTFS REAL SOLO LECTURA + ensayo de borrado EXCLUSIVAMENTE SANDBOX.
# No contiene ningún modo que borre películas, torrents o diarios de producción.
[CmdletBinding()]
param([ValidateSet('Audit','Sandbox')][string]$Mode='Audit')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$MediaRoot = 'C:\VIEWTV\media'
$SourceRoot = 'C:\VIEWTV\media\descargas_temporales'
$MovieRoot = 'C:\VIEWTV\media\Peliculas'
$JournalRoot = 'C:\VIEWTV\publicador\journal'

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class ViewtvLinkAudit0016 {
    [StructLayout(LayoutKind.Sequential)]
    public struct FileInfoNative {
        public uint Attributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME Creation;
        public System.Runtime.InteropServices.ComTypes.FILETIME Access;
        public System.Runtime.InteropServices.ComTypes.FILETIME Write;
        public uint VolumeSerial;
        public uint SizeHigh;
        public uint SizeLow;
        public uint Links;
        public uint IndexHigh;
        public uint IndexLow;
    }
    [DllImport("kernel32.dll", SetLastError=true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetFileInformationByHandle(
        SafeFileHandle handle, out FileInfoNative info);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool CreateHardLinkW(
        string newName, string existingName, IntPtr attributes);
}
'@

function Assert-Leaf([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value.Length -gt 150 -or
        $Value -in @('.','..') -or $Value.Trim() -cne $Value -or
        $Value.EndsWith('.') -or $Value -match '[<>:"/\\|?*\x00-\x1f]' -or
        ($Value -split '\.')[0] -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$') {
        throw 'Componente de ruta no autorizado.'
    }
}
function Split-StrictRelative([string]$Relative) {
    if ([string]::IsNullOrWhiteSpace($Relative) -or
        $Relative.Length -gt 800 -or $Relative.Contains('\') -or
        $Relative.Contains(':') -or $Relative.StartsWith('/')) {
        throw 'Ruta relativa no autorizada.'
    }
    $parts=@($Relative.Split('/'))
    if ($parts.Count -lt 1 -or $parts.Count -gt 16) {
        throw 'Profundidad de ruta fuera de límite.'
    }
    foreach ($part in $parts) { Assert-Leaf $part }
    return $parts
}
function Assert-PlainDirectory([string]$Path) {
    $d=[IO.DirectoryInfo]::new($Path)
    if (-not $d.Exists) {
        throw 'Directorio ausente.'
    }
    if (($d.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Directorio redirigido.'
    }
}
function Resolve-UnderRoot([string]$Root, [string]$Relative) {
    Assert-PlainDirectory $Root
    $parts=@(Split-StrictRelative $Relative)
    $cursor=$Root
    for($i=0; $i -lt ($parts.Count - 1); $i++) {
        $cursor=[IO.Path]::Combine($cursor,$parts[$i])
        Assert-PlainDirectory $cursor
    }
    return [IO.Path]::Combine($cursor,$parts[-1])
}
function File-Fingerprint([string]$Path) {
    $info=[IO.FileInfo]::new($Path)
    if(-not $info.Exists -or
        ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Archivo ausente o redirigido.'
    }
    $handle=[IO.FileStream]::new(
        $Path, [IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
    try {
        $native=[ViewtvLinkAudit0016+FileInfoNative]::new()
        if(-not [ViewtvLinkAudit0016]::GetFileInformationByHandle(
            $handle.SafeFileHandle, [ref]$native)) {
            throw 'Imposible confirmar identidad de archivo NTFS.'
        }
        if(($native.Attributes -band 0x400) -ne 0) {
            throw 'Archivo de reanálisis no autorizado.'
        }
        return [pscustomobject]@{
            volume=[uint32]$native.VolumeSerial
            high=[uint32]$native.IndexHigh
            low=[uint32]$native.IndexLow
            links=[uint32]$native.Links
            bytes=[long]$handle.Length
        }
    } finally {
        $handle.Dispose()
    }
}
function Test-SameHardlink($Origin, $Published, [long]$Size) {
    if($Size -le 0) { throw 'Tamaño esperado inválido.' }
    $a=File-Fingerprint $Origin
    $b=File-Fingerprint $Published
    if($a.bytes -ne $Size -or $b.bytes -ne $Size -or
       $a.volume -ne $b.volume -or $a.high -ne $b.high -or
       $a.low -ne $b.low -or $a.links -lt 2 -or
       $a.links -ne $b.links) {
       throw 'Origen y copia no son el mismo hardlink NTFS.'
    }
    return $a.links
}
function Get-JournalPlanHash($Intent) {
    # Mismo contrato estable que el publicador 0013, sin secretos.
    $body=[ordered]@{
        id=[long]$Intent.download_id
        torrent=[string]$Intent.torrent_hash
        library=[string]$Intent.library
        files=@($Intent.files)
    } | ConvertTo-Json -Compress -Depth 8
    $sha=[Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($sha.ComputeHash(
            [Text.Encoding]::UTF8.GetBytes($body))).Replace('-','').ToLowerInvariant()
    } finally { $sha.Dispose() }
}
function Test-Journal([IO.FileInfo]$File) {
    if($File.Name -cnotmatch '^download-([1-9][0-9]*)\.json$' -or
        $File.Length -lt 30 -or $File.Length -gt 16384 -or
        ($File.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Diario no autorizado.'
    }
    $id=[long]$Matches[1]
    $record=[IO.File]::ReadAllText($File.FullName)|ConvertFrom-Json
    if($record.version -ne 1 -or $record.download_id -ne $id -or
        $null -eq $record.intent -or $record.intent.download_id -ne $id -or
        $record.intent.library -cne 'Peliculas' -or
        [string]$record.intent.torrent_hash -cnotmatch '^(?:[a-f0-9]{40}|[a-f0-9]{64})$') {
        throw 'Diario y descarga incongruentes.'
    }
    if([string]$record.manifest_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
       [string]$record.manifest_sha256 -cne (Get-JournalPlanHash $record.intent)) {
        throw 'Huella del manifiesto no coincidente.'
    }
    $folder=[string]$record.folder
    Assert-Leaf $folder
    $destination=[IO.Path]::Combine($MovieRoot,$folder)
    try { Assert-PlainDirectory $destination } catch {
        throw 'Carpeta de publicación no disponible.'
    }
    $files=@($record.intent.files)
    if($files.Count -lt 1 -or $files.Count -gt 20) {
        throw 'Manifiesto vacío o excesivo.'
    }
    $visited=@{}
    $videos=0
    $total=0L
    foreach($entry in $files) {
        $destinationParts=@(Split-StrictRelative ([string]$entry.destination_relative))
        if($destinationParts.Count -ne 3 -or
            $destinationParts[0] -cne 'Peliculas' -or
            $destinationParts[1] -cne $folder) {
            throw 'El manifiesto no corresponde a la carpeta publicada.'
        }
        $leaf=$destinationParts[2]
        if($visited.ContainsKey($leaf.ToLowerInvariant())) {
            throw 'Archivo repetido en el manifiesto.'
        }
        $visited[$leaf.ToLowerInvariant()]=$true
        if([IO.Path]::GetExtension($leaf).ToLowerInvariant() -in
          @('.mp4','.mkv','.m4v','.avi')) {
            $videos++
        }
        try {
            $source=Resolve-UnderRoot $SourceRoot ([string]$entry.source_relative)
        } catch { throw 'Ruta de origen no verificable.' }
        try {
            $target=Resolve-UnderRoot $MediaRoot ([string]$entry.destination_relative)
        } catch { throw 'Ruta de destino no verificable.' }
        $size=[long]$entry.size_bytes
        $null=Test-SameHardlink $source $target $size
        $total+=$size
    }
    if($videos -ne 1) { throw 'No existe un único vídeo autorizado.' }
    if(@([IO.Directory]::GetFileSystemEntries($destination)).Count -ne $files.Count) {
        throw 'Archivos adicionales o destino incompleto.'
    }
    return [pscustomobject]@{ id=$id; folder=$folder; archivos=$files.Count; bytes=$total }
}

function Audit-Production {
    foreach($dir in @($MediaRoot,$SourceRoot,$MovieRoot,$JournalRoot)) {
        Assert-PlainDirectory $dir
    }
    $valid=0
    $blocked=0
    $files=0
    $prior=0
    $found=@{}
    $journals=@([IO.Directory]::GetFiles($JournalRoot,'download-*.json'))
    foreach($item in $journals) {
        try {
            $result=Test-Journal ([IO.FileInfo]::new($item))
            $valid++
            $files+=$result.archivos
            $found[$result.folder.ToLowerInvariant()]=1
            if($result.id -le 3) { $prior++ }
        } catch {
            $blocked++
            # Solo etiquetas constantes: jamás mostrar rutas, títulos o hashes.
            $reason=[string]$_.Exception.Message
            $known=@(
                'Carpeta de publicación no disponible.',
                'Ruta de origen no verificable.',
                'Ruta de destino no verificable.',
                'Diario no autorizado.',
                'Diario y descarga incongruentes.',
                'Huella del manifiesto no coincidente.',
                'El manifiesto no corresponde a la carpeta publicada.',
                'Archivo repetido en el manifiesto.',
                'No existe un único vídeo autorizado.',
                'Archivos adicionales o destino incompleto.',
                'Origen y copia no son el mismo hardlink NTFS.',
                'Componente de ruta no autorizado.',
                'Ruta relativa no autorizada.',
                'Profundidad de ruta fuera de límite.',
                'Directorio ausente.',
                'Directorio redirigido.',
                'Archivo ausente o redirigido.',
                'Archivo de reanálisis no autorizado.',
                'Imposible confirmar identidad de archivo NTFS.',
                'Tamaño esperado inválido.',
                'Manifiesto vacío o excesivo.'
            )
            if($known -contains $reason) {
                Write-Output "BLOQUEO_VALIDACION_${blocked}=$reason"
            } else {
                Write-Output "BLOQUEO_VALIDACION_${blocked}=CAUSA_NO_PUBLICADA"
            }
        }
    }
    $unknown=0
    foreach($dir in @([IO.Directory]::GetDirectories($MovieRoot))) {
        $info=[IO.DirectoryInfo]::new($dir)
        if(-not $found.ContainsKey($info.Name.ToLowerInvariant())) { $unknown++ }
    }
    Write-Output "DIARIOS_ENCONTRADOS=$($journals.Count)"
    Write-Output "DIARIOS_VERIFICADOS_POR_HARDLINK=$valid"
    Write-Output "DIARIOS_BLOQUEADOS=$blocked"
    Write-Output "FICHEROS_PUBLICADOS_VERIFICADOS=$files"
    Write-Output "DIARIOS_VERIFICADOS_HISTORICOS_ID_1_A_3=$prior"
    Write-Output "CARPETAS_SIN_DIARIO_VALIDADO=$unknown"
    Write-Output 'JELLYFIN_Y_QBIT_PENDIENTES_DE_CORRELACION=SI'
    Write-Output 'BORRADOS_PRODUCCION=0'
}

function Test-Sandbox {
    $parent=[IO.Path]::GetTempPath()
    $root=[IO.Path]::Combine(
        $parent, 'viewtv-retiro-sandbox-'+[guid]::NewGuid().ToString('N'))
    if([IO.Directory]::Exists($root)) { throw 'Sandbox ya existe.' }
    $null=[IO.Directory]::CreateDirectory($root)
    $origin=[IO.Path]::Combine($root,'origen.bin')
    $published=[IO.Path]::Combine($root,'publicado.bin')
    try {
        $bytes=[Text.Encoding]::UTF8.GetBytes('VIEWTV_SANDBOX_UNICAMENTE_0016')
        [IO.File]::WriteAllBytes($origin,$bytes)
        if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
            $published, $origin, [IntPtr]::Zero)) {
            throw 'No se pudo crear enlace de ensayo.'
        }
        $n=Test-SameHardlink $origin $published $bytes.Length
        if($n -ne 2) { throw 'El enlace de ensayo no es exclusivo.' }
        # Bloquear un archivo abierto antes de simular la eliminación.
        $lock=[IO.FileStream]::new(
            $origin,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None)
        try {
            $denied=$false
            try { $null=File-Fingerprint $published } catch { $denied=$true }
            if(-not $denied) { throw 'La exclusión de descriptor abierto falló.' }
        } finally { $lock.Dispose() }
        # ÚNICO borrado de prueba: el archivo NUEVO y PRIVADO del sandbox.
        $null=Test-SameHardlink $origin $published $bytes.Length
        [IO.File]::Delete($published)
        if([IO.File]::Exists($published) -or
            -not [IO.File]::Exists($origin) -or
            (File-Fingerprint $origin).links -ne 1) {
            throw 'El origen del hardlink resultó afectado.'
        }
        Write-Output 'ENSAYO_SANDBOX_NTFS_BORRADO_SOLO_COPIA=PASS'
        Write-Output 'ORIGINAL_SANDBOX_CONSERVADO=SI'
        Write-Output 'ESPACIO_REAL_LIBERADO_AL_CONSERVAR_ORIGINAL=NO_GARANTIZADO'
    } finally {
        # Borrar únicamente ficheros ficticios que este mismo proceso creó
        # dentro del sandbox GUID recién creado. JAMÁS usar -Recurse en medios.
        if([IO.File]::Exists($published)) { [IO.File]::Delete($published) }
        if([IO.File]::Exists($origin)) { [IO.File]::Delete($origin) }
        if([IO.Directory]::Exists($root)) { [IO.Directory]::Delete($root,$false) }
    }
    Write-Output 'BORRADOS_PRODUCCION=0'
}

if($Mode -ceq 'Audit') { Audit-Production } else { Test-Sandbox }
