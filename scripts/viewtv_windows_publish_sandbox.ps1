# VIEWTV: Windows-native directory publisher, TEST SANDBOX ONLY.
# Requires a brand-new, explicitly marked directory directly under C:\Users\Public.
# Does not access C:\VIEWTV or perform torrent/Jellyfin actions.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SandboxRoot,
    [Parameter(Mandatory=$true)][string]$StageName,
    [Parameter(Mandatory=$true)][string]$FinalName
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-LeafName([string]$name) {
    if ([string]::IsNullOrWhiteSpace($name) -or $name.Length -gt 150 -or
        $name -eq '.' -or $name -eq '..' -or
        $name.Trim() -cne $name -or $name.EndsWith('.') -or
        $name -match '[<>:"/\\|?*\x00-\x1f]') {
        throw 'Nombre de publicación no autorizado.'
    }
    $firstPart = ($name -split '\.')[0].ToUpperInvariant()
    if ($firstPart -in @('CON','PRN','AUX','NUL') -or
        $firstPart -match '^(COM|LPT)[1-9]$') {
        throw 'Nombre reservado de Windows.'
    }
}

$public = [System.IO.Path]::GetFullPath([Environment]::GetEnvironmentVariable('PUBLIC'))
if ([string]::IsNullOrWhiteSpace($public) -or
    [System.IO.Path]::GetPathRoot($public).ToUpperInvariant() -ne 'C:\' -or
    -not [System.IO.Directory]::Exists($public)) {
    throw 'No se permite publicar fuera de la carpeta pública Windows.'
}
$root = [System.IO.Path]::GetFullPath($SandboxRoot).TrimEnd('\')
$parent = [System.IO.Path]::GetDirectoryName($root)
$leaf = [System.IO.Path]::GetFileName($root)
if (-not $parent.Equals($public.TrimEnd('\'), [System.StringComparison]::OrdinalIgnoreCase) -or
    $leaf -cnotmatch '^viewtv-win-sandbox-[0-9a-f]{32}$' -or
    -not [System.IO.Directory]::Exists($root)) {
    throw 'La raíz debe ser un sandbox nuevo directamente bajo Public.'
}
$dirInfo = [System.IO.DirectoryInfo]::new($root)
if (($dirInfo.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'No se aceptan carpetas redirigidas.'
}
$marker = Join-Path $root '.viewtv-win-sandbox-only'
$markerInfo = [System.IO.FileInfo]::new($marker)
if (-not $markerInfo.Exists -or
    ($markerInfo.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -or
    [System.IO.File]::ReadAllText($marker) -cne "VIEWTV_WINDOWS_SANDBOX_ONLY_V1`n") {
    throw 'El marcador explícito de pruebas no es válido.'
}
if ($StageName -cnotmatch '^\.viewtv-stage-[1-9][0-9]{0,9}$') {
    throw 'Nombre de staging no autorizado.'
}
Test-LeafName $FinalName
$staged = Join-Path $root $StageName
$final = Join-Path $root $FinalName
if (-not [System.IO.Directory]::Exists($staged)) {
    throw 'Staging inexistente: requiere revisión.'
}
$stageInfo = [System.IO.DirectoryInfo]::new($staged)
if (($stageInfo.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'No se aceptan enlaces o carpetas redirigidas.'
}
if ([System.IO.Directory]::Exists($final) -or [System.IO.File]::Exists($final)) {
    throw 'Destino ya existente: requiere revisión.'
}

# Confinado a pruebas: archivos directos, un vídeo, subtítulos asociados.
$entries = @([System.IO.Directory]::GetFileSystemEntries($staged))
if ($entries.Count -lt 1 -or $entries.Count -gt 20) {
    throw 'Número de archivos de prueba no admitido.'
}
$videoCount = 0
$stem = ''
$subtitles = @()
foreach ($entry in $entries) {
    $info = [System.IO.FileInfo]::new($entry)
    if (-not $info.Exists -or
        ($info.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -or
        $info.Length -le 0 -or $info.Length -gt 33554432) {
        throw 'Staging contiene entradas inseguras.'
    }
    Test-LeafName $info.Name
    $ext = $info.Extension.ToLowerInvariant()
    if ($ext -in @('.mkv','.mp4','.m4v','.avi')) {
        $videoCount += 1
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($info.Name)
    } elseif ($ext -in @('.srt','.ass','.vtt')) {
        $subtitles += $info.Name
    } else {
        throw 'Formato de archivo de prueba no admitido.'
    }
}
if ($videoCount -ne 1) {
    throw 'Se requiere exactamente un archivo de vídeo.'
}
foreach ($subtitle in $subtitles) {
    if (-not $subtitle.StartsWith(
        $stem + '.', [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw 'El subtítulo no corresponde al vídeo.'
    }
}

# Directory.Move uses the native Windows move operation, without replacing
# destination. Both paths are direct siblings on the SAME NTFS volume.
# If Windows returns an error, NEVER auto-retry: state may be ambiguous.
[System.IO.Directory]::Move($staged, $final)
[pscustomobject]@{
    estado = 'publicada_en_sandbox'
    archivos = $entries.Count
    motor = 'Windows_Directory_Move'
} | ConvertTo-Json -Compress
