# Publicacion PUNTUAL solo de la descarga VIEWTV #2 verificada.
# Se ejecuta nativamente en Windows; no automatiza otras descargas.
# No reescribe ni borra ni renombra archivos de qBittorrent; enlaza solo el MKV.
$ErrorActionPreference='Stop'
$root='C:\VIEWTV\media'
$sourceRoot=Join-Path $root 'descargas_temporales'
$targetRoot=Join-Path $root 'Peliculas'
$source=Join-Path $sourceRoot 'Nadie 2 (Nobody 2) (2025) [4k 2160p][Esp]\Nadie 2 (Nobody 2) (2025) [4k 2160p][Esp].mkv'
$destinationFolder=Join-Path $targetRoot 'Nadie 2 (2025)'
$destinationName='Nadie 2 (2025).mkv'
$destination=Join-Path $destinationFolder $destinationName
$size=17686540799L

# PowerShell New-Item -Target interpreta corchetes como comodines en
# algunos proveedores. CreateHardLinkW acepta rutas Unicode LITERALES.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ViewtvHardLinkNative {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern bool CreateHardLink(
        string newFile, string existingFile, IntPtr securityAttributes);
}
'@ -ErrorAction Stop

function Check-Dir([string]$path) {
  if (-not [IO.Directory]::Exists($path)) { throw 'No existe la carpeta esperada.' }
  $attributes=[IO.File]::GetAttributes($path)
  if ($attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'Una carpeta usa un enlace de reanalisis.'
  }
}
function Check-Source {
  if (-not [IO.File]::Exists($source)) { throw 'Video de origen ausente.' }
  $info=Get-Item -LiteralPath $source
  if (($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
      $info.Length -ne $size) {
    throw 'El video de origen ya no coincide con la verificacion.'
  }
}
foreach($dir in @($root,$sourceRoot,(Split-Path -Parent $source),$targetRoot)) {
  Check-Dir $dir
}
if ((Get-Volume -DriveLetter C).FileSystem -cne 'NTFS') {
  throw 'Se necesita NTFS para un enlace duro sin duplicar bytes.'
}
if ((Split-Path -Qualifier $source) -cne (Split-Path -Qualifier $destination)) {
  throw 'El origen y destino no comparten volumen.'
}
Check-Source
if ([IO.Directory]::Exists($destinationFolder) -or
    [IO.File]::Exists($destinationFolder)) {
  throw 'El destino ya existe; no se sustituira.'
}
$stage=Join-Path $targetRoot ('.viewtv-publish-2-'+[Guid]::NewGuid().ToString('N'))
if ([IO.Directory]::Exists($stage)) { throw 'Staging inesperado.' }
[IO.Directory]::CreateDirectory($stage) | Out-Null
$stagedFile=Join-Path $stage $destinationName
try {
  # Un HardLink mantiene qBittorrent sembrando sin duplicar ni mover 16,47 GiB.
  if (-not [ViewtvHardLinkNative]::CreateHardLink(
      $stagedFile,$source,[IntPtr]::Zero)) {
    $code=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
    throw ('Windows rechazo enlace duro literal; codigo '+$code)
  }
  $items=@(Get-ChildItem -LiteralPath $stage -Force)
  if ($items.Count -ne 1 -or $items[0].Name -cne $destinationName -or
      $items[0].Length -ne $size) {
    throw 'La carpeta temporal no contiene solo el MKV esperado.'
  }
  Check-Source
  Check-Dir $targetRoot
  if ([IO.Directory]::Exists($destinationFolder)) {throw 'Colision de destino.'}
  # Directorio nuevo bajo NTFS: renombrado Windows nativo, sin replace.
  [IO.Directory]::Move($stage,$destinationFolder)
  Check-Source
  if (-not [IO.File]::Exists($destination) -or
      (Get-Item -LiteralPath $destination).Length -ne $size) {
    throw 'La publicacion no coincide con el archivo de origen.'
  }
  Write-Output 'PUBLICACION_PELICULAS=OK'
  Write-Output 'SOLO_MKV=SI'
  Write-Output 'ORIGEN_QBIT_INTACTO=SI'
  Write-Output 'DESTINO_NUEVO=Nadie 2 (2025)/Nadie 2 (2025).mkv'
} catch {
  Write-Output ('PUBLICACION_PELICULAS=REQUIERE_REVISION')
  Write-Output ('TEMPORAL_REVISABLE='+$stage)
  throw
}
