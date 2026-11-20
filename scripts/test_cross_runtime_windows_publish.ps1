# Windows orchestrates Docker -> NTFS publication. TEST SANDBOX ONLY.
# Never accesses C:\VIEWTV, real downloads, SQLite or qBittorrent.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$public = [System.IO.Path]::GetFullPath($env:PUBLIC)
if ($public.TrimEnd('\') -ine 'C:\Users\Public') {
    throw 'Esta prueba solo admite C:\Users\Public.'
}
$root = Join-Path $public ('viewtv-win-sandbox-' + [Guid]::NewGuid().ToString('N'))
if ([System.IO.Directory]::Exists($root) -or [System.IO.File]::Exists($root)) {
    throw 'El directorio de pruebas ya existe.'
}
$publisher = Join-Path $PSScriptRoot 'viewtv_windows_publish_sandbox.ps1'
$reconciler = Join-Path $PSScriptRoot 'viewtv_windows_reconcile_sandbox.ps1'
. (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')
$keyPath = New-ViewtvTestKey
if (-not [System.IO.File]::Exists($publisher)) {
    throw 'Publicador de prueba ausente.'
}
[System.IO.Directory]::CreateDirectory($root) | Out-Null
$marker = Join-Path $root '.viewtv-win-sandbox-only'
$markerValue = 'VIEWTV_WINDOWS_SANDBOX_ONLY_V1' + [char]10
[System.IO.File]::WriteAllText($marker, $markerValue)

$title = 'Pelicula ficticia (2026)'
$video = $title + '.mkv'
$subtitle = $title + '.es.srt'
$results = [ordered]@{}
try {
    $sources = Join-Path $root 'source'
    [System.IO.Directory]::CreateDirectory($sources) | Out-Null
    $data = New-Object byte[] (3 * 1024 * 1024 + 17)
    $rng = New-Object System.Random 2026
    $rng.NextBytes($data)
    [System.IO.File]::WriteAllBytes((Join-Path $sources $video), $data)
    [System.IO.File]::WriteAllText((Join-Path $sources $subtitle), 'Subtitulo ficticio de VIEWTV')
    $videoHash = (Get-FileHash (Join-Path $sources $video) -Algorithm SHA256).Hash
    $subtitleHash = (Get-FileHash (Join-Path $sources $subtitle) -Algorithm SHA256).Hash
    $linuxRoot = '/mnt/c/Users/Public/' + [System.IO.Path]::GetFileName($root)

    $dockerOutput = & wsl.exe -d Ubuntu-24.04 -u viewtv -e /usr/bin/env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/viewtv/projects/viewtv-broker-0013-20261119/backend:/home/viewtv/projects/viewtv-broker-0013-20261119 /home/viewtv/projects/viewtv/backend/.venv/bin/python -B -m worker.organization_cross_runtime_probe --stage $linuxRoot 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "La preparación Docker devolvió código $LASTEXITCODE."
    }
    $dockerResult = ($dockerOutput | Out-String).Trim() | ConvertFrom-Json
    if ($dockerResult.docker_staging -ne 'verificado' -or $dockerResult.archivos -ne '2') {
        throw 'Docker no verificó los dos ficheros de staging.'
    }
    $stage = Join-Path $root '.viewtv-stage-1'
    if (-not [System.IO.Directory]::Exists($stage) -or
        [System.IO.Directory]::Exists((Join-Path $root $title))) {
        throw 'El staging no se creó correctamente.'
    }
    $results['docker_staging_y_sha256'] = 'correcto'

    # Before Windows publication, even a marked Docker stage must NEVER
    # trigger a Jellyfin scan or produce a visible VIEWTV catalog item.
    $preOutput = & wsl.exe -d Ubuntu-24.04 -u viewtv -e /usr/bin/env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/viewtv/projects/viewtv-broker-0013-20261119/backend:/home/viewtv/projects/viewtv-broker-0013-20261119 /home/viewtv/projects/viewtv/backend/.venv/bin/python -B -m worker.organization_windows_catalog_probe_sandbox --sandbox $linuxRoot --phase before 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'El preflight de catálogo sin publicar ha fallado.' }
    $pre = ($preOutput | Out-String).Trim() | ConvertFrom-Json
    if ($pre.estado -ne 'pendiente_sin_escaneo' -or
        $pre.solicitudes_escaneo -ne 0 -or $pre.catalogo -ne 0) {
        throw 'El staging previo no debe activar Jellyfin.'
    }
    $results['prepublicacion_sin_escaneo'] = 'correcto'

    $approval = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-1' -FinalName $title -KeyPath $keyPath

    # Simulate Docker-stage tampering AFTER Windows has signed its approval.
    $stagedSubtitle = Join-Path $stage $subtitle
    $goodSubtitle = [System.IO.File]::ReadAllBytes($stagedSubtitle)
    $badSubtitle = [byte[]]$goodSubtitle.Clone()
    $badSubtitle[0] = [byte]($badSubtitle[0] -bxor 1)
    [System.IO.File]::WriteAllBytes($stagedSubtitle, $badSubtitle)
    $refusedTampering = $false
    try {
        & $publisher -SandboxRoot $root -StageName '.viewtv-stage-1' -FinalName $title -ApprovalName $approval -KeyPath $keyPath | Out-Null
    } catch {
        $refusedTampering = $true
    }
    if (-not $refusedTampering -or
        -not [System.IO.Directory]::Exists($stage) -or
        [System.IO.Directory]::Exists((Join-Path $root $title))) {
        throw 'Una alteración del staging permitió publicar.'
    }
    [System.IO.File]::WriteAllBytes($stagedSubtitle, $goodSubtitle)
    $results['tamper_docker_rechazado'] = 'correcto'

    $publication = & $publisher -SandboxRoot $root -StageName '.viewtv-stage-1' -FinalName $title -ApprovalName $approval -KeyPath $keyPath | ConvertFrom-Json
    if ($publication.estado -ne 'publicada_en_sandbox' -or $publication.archivos -ne 2) {
        throw 'La publicación nativa Windows no fue confirmada.'
    }
    $dest = Join-Path $root $title
    if ([System.IO.Directory]::Exists($stage) -or
        (Get-FileHash (Join-Path $dest $video) -Algorithm SHA256).Hash -ne $videoHash -or
        (Get-FileHash (Join-Path $dest $subtitle) -Algorithm SHA256).Hash -ne $subtitleHash) {
        throw 'Los archivos publicados no están íntegros.'
    }
    $results['publicacion_multifichero_ntfs'] = 'correcto'

    $reconciliation = & $reconciler -SandboxRoot $root -StageName '.viewtv-stage-1' -FinalName $title -ApprovalName $approval -KeyPath $keyPath | ConvertFrom-Json
    if ($reconciliation.estado -ne 'publicada_verificada' -or
        -not $reconciliation.lectura_solamente) {
        throw 'No se reconcilió la publicación multifichero.'
    }
    $results['reconciliacion_de_lectura'] = 'publicada_verificada'

    # Only a signed Windows publication reconciled as published can enter
    # this synthetic Jellyfin integration. HTTP is ALWAYS MockTransport
    # in the Python probe; no real scan, library or SQLite is accessed.
    $postOutput = & wsl.exe -d Ubuntu-24.04 -u viewtv -e /usr/bin/env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/viewtv/projects/viewtv-broker-0013-20261119/backend:/home/viewtv/projects/viewtv-broker-0013-20261119 /home/viewtv/projects/viewtv/backend/.venv/bin/python -B -m worker.organization_windows_catalog_probe_sandbox --sandbox $linuxRoot --phase after 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'La prueba Windows a catálogo ficticio ha fallado.' }
    $post = ($postOutput | Out-String).Trim() | ConvertFrom-Json
    if ($post.estado -ne 'publicacion_windows_catalogo_simulado_ok' -or
        $post.solicitudes_escaneo -ne 1 -or
        $post.catalogo_antes -ne 0 -or
        $post.catalogo_antes_finalizar -ne 0 -or
        $post.catalogo_despues -ne 1) {
        throw 'El escaneo simulado se completó en orden incorrecto.'
    }
    $results['ntfs_jellyfin_catalogo_ficticio'] = 'correcto'

    $duplicate = Join-Path $root '.viewtv-stage-2'
    [System.IO.Directory]::CreateDirectory($duplicate) | Out-Null
    [System.IO.File]::WriteAllBytes((Join-Path $duplicate $video), [byte[]](1,2,3))
    $approval2 = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-2' -FinalName $title -KeyPath $keyPath
    $refused = $false
    try {
        & $publisher -SandboxRoot $root -StageName '.viewtv-stage-2' -FinalName $title -ApprovalName $approval2 -KeyPath $keyPath | Out-Null
    } catch {
        $refused = $true
    }
    if (-not $refused -or
        -not [System.IO.Directory]::Exists($duplicate) -or
        (Get-FileHash (Join-Path $dest $video) -Algorithm SHA256).Hash -ne $videoHash) {
        throw 'La segunda publicación podría sobrescribir contenido.'
    }
    $results['segundo_intento_sin_sobrescritura'] = 'correcto'

    if ((Get-FileHash (Join-Path $sources $video) -Algorithm SHA256).Hash -ne $videoHash -or
        (Get-FileHash (Join-Path $sources $subtitle) -Algorithm SHA256).Hash -ne $subtitleHash) {
        throw 'La fuente original fue modificada.'
    }
    $results['origen_intacto'] = 'correcto'
    $results | ConvertTo-Json -Compress
}
finally {
    # Only clean this invocation's new, uniquely named and marked folder.
    if (([System.IO.Path]::GetDirectoryName($root) -ieq $public) -and
        [System.IO.Path]::GetFileName($root) -match '^viewtv-win-sandbox-[0-9a-f]{32}$' -and
        [System.IO.File]::Exists($marker) -and
        [System.IO.File]::ReadAllText($marker) -ceq $markerValue) {
        [System.IO.Directory]::Delete($root, $true)
    }
    if ([System.IO.File]::Exists($keyPath)) {
        $keyDirectory = [System.IO.Path]::GetDirectoryName($keyPath)
        if (
            [System.IO.Path]::GetFileName($keyDirectory) -match '^viewtv-test-key-[0-9a-f]{32}$' -and
            [System.IO.Path]::GetDirectoryName($keyDirectory) -ieq [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
        ) {
            [System.IO.Directory]::Delete($keyDirectory, $true)
        }
    }
}
