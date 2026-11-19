# VIEWTV: Windows native directory publication diagnostic.
# ONLY scratch paths under $env:PUBLIC, NEVER C:\VIEWTV, no real media.
# This diagnostic never publishes to production and requires no secrets.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$public = [System.IO.Path]::GetFullPath([Environment]::GetEnvironmentVariable('PUBLIC'))
if ([string]::IsNullOrWhiteSpace($public) -or
    -not [System.IO.Directory]::Exists($public) -or
    [System.IO.Path]::GetPathRoot($public).ToUpperInvariant() -ne 'C:\') {
    throw 'La carpeta publica de Windows no es la unidad C esperada.'
}
$root = Join-Path $public ('viewtv-win-publish-' + [Guid]::NewGuid().ToString('N'))
if ([System.IO.Directory]::Exists($root) -or [System.IO.File]::Exists($root)) {
    throw 'Ya existe un directorio de prueba con el identificador generado.'
}

$results = [ordered]@{}
[System.IO.Directory]::CreateDirectory($root) | Out-Null
$marker = Join-Path $root '.viewtv-win-publish-test-only'
[System.IO.File]::WriteAllText($marker, "VIEWTV_WIN_DIRECTORY_PROBE_V1`n")
try {
    $stage = Join-Path $root '.viewtv-stage-movie'
    $published = Join-Path $root 'Pelicula ficticia (2026)'
    [System.IO.Directory]::CreateDirectory($stage) | Out-Null
    $video = [System.IO.Path]::Combine($stage, 'Pelicula ficticia (2026).mkv')
    $subtitle = [System.IO.Path]::Combine($stage, 'Pelicula ficticia (2026).es.srt')
    $videoBytes = [System.Text.Encoding]::UTF8.GetBytes('contenido multimedia ficticio')
    $subtitleBytes = [System.Text.Encoding]::UTF8.GetBytes('subtitulos ficticios')
    [System.IO.File]::WriteAllBytes($video, $videoBytes)
    [System.IO.File]::WriteAllBytes($subtitle, $subtitleBytes)
    if ([System.IO.Directory]::Exists($published)) { throw 'Destino preexistente inesperado.' }

    [System.IO.Directory]::Move($stage, $published)
    if ([System.IO.Directory]::Exists($stage) -or
        -not [System.IO.File]::Exists([System.IO.Path]::Combine($published, 'Pelicula ficticia (2026).mkv')) -or
        -not [System.IO.File]::Exists([System.IO.Path]::Combine($published, 'Pelicula ficticia (2026).es.srt'))) {
        throw 'La publicacion de carpeta no se completo.'
    }
    if ([Convert]::ToBase64String($videoBytes) -ne [Convert]::ToBase64String(
        [System.IO.File]::ReadAllBytes([System.IO.Path]::Combine($published, 'Pelicula ficticia (2026).mkv'))) -or
        [Convert]::ToBase64String($subtitleBytes) -ne [Convert]::ToBase64String(
        [System.IO.File]::ReadAllBytes([System.IO.Path]::Combine($published, 'Pelicula ficticia (2026).es.srt')))) {
        throw 'Los contenidos de prueba cambiaron durante la publicacion.'
    }
    $results['publicacion_carpeta_multifichero'] = 'correcta'

    $existsDir = Join-Path $root 'Destino existente'
    $existingStage = Join-Path $root '.viewtv-stage-existing'
    [System.IO.Directory]::CreateDirectory($existsDir) | Out-Null
    [System.IO.Directory]::CreateDirectory($existingStage) | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $existsDir 'proteger.txt'), 'ajeno')
    try {
        [System.IO.Directory]::Move($existingStage, $existsDir)
        $results['destino_existente'] = 'FALLO_SOBRESCRITURA'
    } catch [System.IO.IOException] {
        $results['destino_existente'] = 'protegido'
    }
    if (-not [System.IO.Directory]::Exists($existingStage) -or
        [System.IO.File]::ReadAllText((Join-Path $existsDir 'proteger.txt')) -ne 'ajeno') {
        throw 'La carpeta ajena no quedo intacta.'
    }

    $emptyDir = Join-Path $root 'Destino vacio'
    $emptyStage = Join-Path $root '.viewtv-stage-empty'
    [System.IO.Directory]::CreateDirectory($emptyDir) | Out-Null
    [System.IO.Directory]::CreateDirectory($emptyStage) | Out-Null
    try {
        [System.IO.Directory]::Move($emptyStage, $emptyDir)
        $results['destino_vacio_preexistente'] = 'FALLO_SOBRESCRITURA'
    } catch [System.IO.IOException] {
        $results['destino_vacio_preexistente'] = 'protegido'
    }
    if (-not [System.IO.Directory]::Exists($emptyDir) -or
        -not [System.IO.Directory]::Exists($emptyStage)) {
        throw 'Se reemplazo una carpeta vacia ajena.'
    }

    $uppercase = Join-Path $root 'SERIE FICTICIA'
    $caseStage = Join-Path $root '.viewtv-stage-case'
    [System.IO.Directory]::CreateDirectory($uppercase) | Out-Null
    [System.IO.Directory]::CreateDirectory($caseStage) | Out-Null
    try {
        [System.IO.Directory]::Move($caseStage, (Join-Path $root 'serie ficticia'))
        $results['colision_mayusculas'] = 'FALLO_SOBRESCRITURA'
    } catch [System.IO.IOException] {
        $results['colision_mayusculas'] = 'protegida'
    }
    if (-not [System.IO.Directory]::Exists($caseStage) -or
        -not [System.IO.Directory]::Exists($uppercase)) {
        throw 'Se reemplazo una carpeta por colision de mayusculas.'
    }

    $partial = Join-Path $root '.viewtv-stage-interrumpido'
    [System.IO.Directory]::CreateDirectory($partial) | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $partial 'fragmento.tmp'), 'simulacion')
    $target = Join-Path $root 'No publicar interrumpido'
    if ([System.IO.Directory]::Exists($target)) { throw 'Destino de interrupcion ya existe.' }
    $results['interrupcion_antes_de_publicar'] = if (
        [System.IO.Directory]::Exists($partial) -and
        -not [System.IO.Directory]::Exists($target)
    ) { 'sin_publicacion' } else { 'FALLO' }

    if ($results.Values -contains 'FALLO' -or
        $results.Values -contains 'FALLO_SOBRESCRITURA') {
        throw 'Una prueba de no sobrescritura o atomicidad no paso.'
    }
    $results | ConvertTo-Json -Compress
}
finally {
    # Only delete the brand-new, marked, uniquely named scratch root.
    if (([System.IO.Path]::GetDirectoryName($root) -ieq $public) -and
        ([System.IO.Path]::GetFileName($root) -match '^viewtv-win-publish-[0-9a-f]{32}$') -and
        [System.IO.File]::Exists($marker) -and
        [System.IO.File]::ReadAllText($marker) -eq "VIEWTV_WIN_DIRECTORY_PROBE_V1`n") {
        [System.IO.Directory]::Delete($root, $true)
    }
}
