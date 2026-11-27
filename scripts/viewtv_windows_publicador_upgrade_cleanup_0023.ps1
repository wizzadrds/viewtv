# VIEWTV 0023: limpiar SOLO sandboxes de instalacion de esta misma prueba.
# No acepta parametros, sin Remove-Item -Recurse, sin C:\VIEWTV.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$parent=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$parentInfo=[IO.DirectoryInfo]::new($parent)
if(-not $parentInfo.Exists -or
   ($parentInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
   $parent.StartsWith('C:\VIEWTV', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Directorio TEMP no permitido.'
}
$cleaned=0
$rejected=0
$roots=@([IO.Directory]::GetDirectories(
    $parent,'viewtv-upgrade-ficticio-0023-*'
))
foreach($root in $roots) {
    $info=[IO.DirectoryInfo]::new($root)
    if($info.Name -cnotmatch '^viewtv-upgrade-ficticio-0023-([a-f0-9]{32})$') {
        $rejected++;continue
    }
    $id=$Matches[1]
    $marker=Join-Path $root 'marca.txt'
    $expected='VIEWTV_TEST_VERSIONES_0023_'+$id
    $bin=Join-Path $root 'bin'
    $stage=Join-Path $root 'stage'
    $backup=Join-Path $root 'backup'
    $rootFiles=@(
        $marker,
        (Join-Path $root '01-intencion.txt'),
        (Join-Path $root '02-recuperado.txt'),
        (Join-Path $root '03-actualizado.txt'),
        (Join-Path $root '04-revertido.txt')
    )
    $binFiles=@(
        (Join-Path $bin 'publicador-ficticio.ps1'),
        (Join-Path $bin 'mutex-ficticio.ps1')
    )
    $stageFiles=@(
        (Join-Path $stage 'publicador-stage.ps1'),
        (Join-Path $stage 'mutex-stage.ps1')
    )
    $backupFiles=@(
        (Join-Path $backup 'version-antigua.ps1'),
        (Join-Path $backup 'version-sustituida-ficticia.ps1')
    )
    $allowedDirs=@($bin,$stage,$backup)
    $valid=$true
    if(($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
       -not [IO.File]::Exists($marker) -or
       [IO.File]::ReadAllText($marker) -cne $expected) {
        $valid=$false
    }
    if($valid) {
        foreach($dir in $allowedDirs) {
            $di=[IO.DirectoryInfo]::new($dir)
            if(-not $di.Exists -or
               ($di.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                $valid=$false;break
            }
        }
    }
    if($valid) {
        foreach($spec in @(
            @{dir=$root;allowed=@($rootFiles+$allowedDirs)},
            @{dir=$bin;allowed=$binFiles},
            @{dir=$stage;allowed=$stageFiles},
            @{dir=$backup;allowed=$backupFiles}
        )) {
            foreach($entry in @([IO.Directory]::GetFileSystemEntries($spec.dir))) {
                $entryInfo=[IO.FileInfo]::new($entry)
                if($spec.allowed -cnotcontains $entry -or
                   ($entryInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                    $valid=$false;break
                }
            }
        }
    }
    if(-not $valid) { $rejected++;continue }
    foreach($file in @($binFiles+$stageFiles+$backupFiles+$rootFiles)) {
        if([IO.File]::Exists($file)) { [IO.File]::Delete($file) }
    }
    foreach($dir in $allowedDirs) { [IO.Directory]::Delete($dir,$false) }
    [IO.Directory]::Delete($root,$false)
    $cleaned++
}
Write-Output 'SANDBOX_0023_LIMPIEZA=SOLO_DIRECTORIOS_FICTICIOS_VERIFICADOS'
Write-Output ('SANDBOX_0023_LIMPIADOS='+$cleaned)
Write-Output ('SANDBOX_0023_RECHAZADOS='+$rejected)
Write-Output 'CARPETAS_MEDIOS_MODIFICADAS=0'
Write-Output 'PUBLICADOR_PRODUCTIVO_MODIFICADO=NO'
