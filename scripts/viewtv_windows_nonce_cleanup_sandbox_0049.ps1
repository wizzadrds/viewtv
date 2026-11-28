# 0049: limpia solo sandboxes PRIVADOS creados por test nonce Win32.
# Sin rutas ni GUID externos, sin recurse, nunca toca medios productivos.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$parent=[IO.DirectoryInfo]::new($root)
if(-not $parent.Exists -or
   ($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
    throw 'TEMP no seguro.'
}
$cleaned=0
$folders=@([IO.Directory]::GetDirectories($root,'viewtv-0049-ficticio-*'))
foreach($folder in $folders){
    $name=[IO.Path]::GetFileName($folder)
    if($name -cnotmatch '^viewtv-0049-ficticio-([a-f0-9]{32})$'){
        throw 'Nombre ajeno al ensayo.'
    }
    $id=$Matches[1]
    if(-not $folder.StartsWith($root+'\',
        [StringComparison]::OrdinalIgnoreCase)){
        throw 'Raiz diferente a TEMP.'
    }
    $dir=[IO.DirectoryInfo]::new($folder)
    if(-not $dir.Exists -or
       ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
        throw 'Sandbox redirigido.'
    }
    $marker=[IO.Path]::Combine($folder,'marcador-0049.txt')
    $file=[IO.FileInfo]::new($marker)
    if(-not $file.Exists -or $file.Length -gt 100 -or
       ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
       [IO.File]::ReadAllText($marker) -cne
       ('VIEWTV_0049_SOLO_FICTICIO_'+$id)){
        throw 'Marca de propiedad incorrecta; no eliminar.'
    }
    $entries=@([IO.Directory]::GetFileSystemEntries($folder))
    foreach($entry in $entries){
        $entryName=[IO.Path]::GetFileName($entry)
        if($entry -cne $marker -and
           $entryName -cnotmatch '^intencion-[a-f0-9]{32}\.txt$'){
            throw 'Entrada desconocida; no eliminar.'
        }
        $entryInfo=[IO.FileInfo]::new($entry)
        if(-not $entryInfo.Exists -or
           ($entryInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
            throw 'Archivo redirigido; no eliminar.'
        }
    }
    # Ninguna carpeta interior: File.Delete de nombres exactos únicamente.
    foreach($entry in $entries){[IO.File]::Delete($entry)}
    [IO.Directory]::Delete($folder,$false)
    $cleaned++
}
Write-Output ('SANDBOX_0049_PROPIOS_LIMPIADOS='+$cleaned)
Write-Output 'ARCHIVOS_DE_MEDIOS_ELIMINADOS=0'
Write-Output 'TORRENTS_MODIFICADOS=0'
