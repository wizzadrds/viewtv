# Tests of the Windows-only, sandbox-only directory publisher.
# Creates a private GUID folder under $env:PUBLIC and removes ONLY that folder.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$publisher = Join-Path $PSScriptRoot 'viewtv_windows_publish_sandbox.ps1'
if (-not [System.IO.File]::Exists($publisher)) { throw 'El publicador de pruebas no existe.' }

$public = [System.IO.Path]::GetFullPath($env:PUBLIC)
if ([System.IO.Path]::GetPathRoot($public).ToUpperInvariant() -ne 'C:\') {
    throw 'Se requiere la unidad C de Windows.'
}
$root = Join-Path $public ('viewtv-win-sandbox-' + [Guid]::NewGuid().ToString('N'))
if ([System.IO.Directory]::Exists($root) -or [System.IO.File]::Exists($root)) {
    throw 'El sandbox aleatorio ya existe.'
}
[System.IO.Directory]::CreateDirectory($root) | Out-Null
$marker = Join-Path $root '.viewtv-win-sandbox-only'
[System.IO.File]::WriteAllText($marker, "VIEWTV_WINDOWS_SANDBOX_ONLY_V1`n")

$results = [ordered]@{}
function Create-Stage([int]$id, [string]$name, [string]$data) {
    $stage = Join-Path $root ('.viewtv-stage-' + $id)
    [System.IO.Directory]::CreateDirectory($stage) | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $stage $name), $data)
    return $stage
}
function Should-Refuse([scriptblock]$operation) {
    try {
        & $operation | Out-Null
    } catch {
        return
    }
    throw 'Una operación peligrosa fue aceptada.'
}
try {
    # Atomic directory publication of video + two independent subtitles.
    $stage = Create-Stage 1 'Corto ficticio (2026).mkv' 'contenido de vídeo ficticio'
    [System.IO.File]::WriteAllText((Join-Path $stage 'Corto ficticio (2026).es.srt'), 'es ficticio')
    [System.IO.File]::WriteAllText((Join-Path $stage 'Corto ficticio (2026).en.srt'), 'en ficticio')
    $result = & $publisher -SandboxRoot $root -StageName '.viewtv-stage-1' -FinalName 'Corto ficticio (2026)' | ConvertFrom-Json
    if ($result.estado -ne 'publicada_en_sandbox' -or $result.archivos -ne 3 -or
        [System.IO.Directory]::Exists($stage)) {
        throw 'La publicación multifichero no se completó.'
    }
    $final = Join-Path $root 'Corto ficticio (2026)'
    foreach ($name in @('Corto ficticio (2026).mkv',
                       'Corto ficticio (2026).es.srt',
                       'Corto ficticio (2026).en.srt')) {
        if (-not [System.IO.File]::Exists((Join-Path $final $name))) {
            throw 'Falta un archivo después de publicar.'
        }
    }
    $results['pelicula_y_dos_subtitulos'] = 'correcto'

    # Exact destination existing: no overwrite, no deletion, staging retained.
    $stage2 = Create-Stage 2 'otro.mkv' 'nuevo'
    $already = Join-Path $root 'Ya existe'
    [System.IO.Directory]::CreateDirectory($already) | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $already 'preservar.txt'), 'ajeno')
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-2' -FinalName 'Ya existe' }
    if (-not [System.IO.Directory]::Exists($stage2) -or
        [System.IO.File]::ReadAllText((Join-Path $already 'preservar.txt')) -ne 'ajeno') {
        throw 'La colisión alteró datos preexistentes.'
    }
    $results['no_sobrescritura'] = 'correcto'

    # Case-insensitive collision on NTFS.
    $stage3 = Create-Stage 3 'otro.mkv' 'ficticio'
    $uppercase = Join-Path $root 'SERIE FICTICIA'
    [System.IO.Directory]::CreateDirectory($uppercase) | Out-Null
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-3' -FinalName 'serie ficticia' }
    if (-not [System.IO.Directory]::Exists($stage3) -or
        -not [System.IO.Directory]::Exists($uppercase)) {
        throw 'Se sustituyó una carpeta equivalente.'
    }
    $results['colision_mayusculas'] = 'correcto'

    # Reject unexpected files (installer, malware) and unknown subtitles.
    $stage4 = Create-Stage 4 'video.mkv' 'ficticio'
    [System.IO.File]::WriteAllText((Join-Path $stage4 'installer.exe'), 'prohibido')
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-4' -FinalName 'Contenido no apto' }
    if (-not [System.IO.File]::Exists((Join-Path $stage4 'installer.exe'))) {
        throw 'La entrada insegura se modificó.'
    }
    $results['archivo_no_permitido'] = 'rechazado'

    $stage5 = Create-Stage 5 'video.mkv' 'ficticio'
    [System.IO.File]::WriteAllText((Join-Path $stage5 'otra_serie.es.srt'), 'extraño')
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-5' -FinalName 'Subtitulo ajeno' }
    $results['subtitulo_no_correspondiente'] = 'rechazado'

    $stage6 = Create-Stage 6 'video.mkv' 'ficticio'
    [System.IO.File]::WriteAllText((Join-Path $stage6 'video2.mp4'), 'segundo')
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-6' -FinalName 'Dos videos' }
    $results['multiple_video'] = 'rechazado'

    # Reject path traversal/invalid root before inspecting any real library.
    $stage7 = Create-Stage 7 'video.mkv' 'ficticio'
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '../otro' -FinalName 'Peli' }
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-7' -FinalName '../Fuera' }
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-7' -FinalName 'CON' }
    Should-Refuse { & $publisher -SandboxRoot $public -StageName '.viewtv-stage-7' -FinalName 'Peli' }
    if (-not [System.IO.Directory]::Exists($stage7)) {
        throw 'Un rechazo movió el staging.'
    }
    $results['proteccion_de_rutas'] = 'correcto'

    # Removing marker blocks publication; restore for safe cleanup.
    $stage8 = Create-Stage 8 'video.mkv' 'ficticio'
    [System.IO.File]::WriteAllText($marker, 'marcador incorrecto')
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-8' -FinalName 'No publicar' }
    [System.IO.File]::WriteAllText($marker, "VIEWTV_WINDOWS_SANDBOX_ONLY_V1`n")
    if (-not [System.IO.Directory]::Exists($stage8)) {
        throw 'Sin marcador se modificó el staging.'
    }
    $results['marcador_obligatorio'] = 'correcto'

    # Simulated power loss BEFORE move leaves staging and no public target.
    $stage9 = Create-Stage 9 'video.mkv' 'ficticio'
    if (-not [System.IO.Directory]::Exists($stage9) -or
        [System.IO.Directory]::Exists((Join-Path $root 'Nunca publicado'))) {
        throw 'El escenario de interrupción no está aislado.'
    }
    $results['interrupcion_antes_publicacion'] = 'sin_efectos'

    $results | ConvertTo-Json -Compress
}
finally {
    if (([System.IO.Path]::GetDirectoryName($root) -ieq $public) -and
        [System.IO.Path]::GetFileName($root) -match '^viewtv-win-sandbox-[0-9a-f]{32}$' -and
        [System.IO.File]::Exists($marker) -and
        [System.IO.File]::ReadAllText($marker) -eq "VIEWTV_WINDOWS_SANDBOX_ONLY_V1`n") {
        [System.IO.Directory]::Delete($root, $true)
    }
}
