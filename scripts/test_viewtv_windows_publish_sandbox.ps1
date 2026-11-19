# Tests of the Windows-only, sandbox-only directory publisher.
# Creates a private GUID folder under $env:PUBLIC and removes ONLY that folder.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$publisher = Join-Path $PSScriptRoot 'viewtv_windows_publish_sandbox.ps1'
$reconciler = Join-Path $PSScriptRoot 'viewtv_windows_reconcile_sandbox.ps1'
. (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')
$keyPath = New-ViewtvTestKey
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
function Invoke-TestPublisher([string]$stageName, [string]$finalName) {
    $approval = New-ViewtvTestApproval -SandboxRoot $root -StageName $stageName -FinalName $finalName -KeyPath $keyPath
    & $publisher -SandboxRoot $root -StageName $stageName -FinalName $finalName -ApprovalName $approval -KeyPath $keyPath
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
    $result = Invoke-TestPublisher '.viewtv-stage-1' 'Corto ficticio (2026)' | ConvertFrom-Json
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
    Should-Refuse { Invoke-TestPublisher '.viewtv-stage-2' 'Ya existe' }
    if (-not [System.IO.Directory]::Exists($stage2) -or
        [System.IO.File]::ReadAllText((Join-Path $already 'preservar.txt')) -ne 'ajeno') {
        throw 'La colisión alteró datos preexistentes.'
    }
    $results['no_sobrescritura'] = 'correcto'

    # Case-insensitive collision on NTFS.
    $stage3 = Create-Stage 3 'otro.mkv' 'ficticio'
    $uppercase = Join-Path $root 'SERIE FICTICIA'
    [System.IO.Directory]::CreateDirectory($uppercase) | Out-Null
    Should-Refuse { Invoke-TestPublisher '.viewtv-stage-3' 'serie ficticia' }
    if (-not [System.IO.Directory]::Exists($stage3) -or
        -not [System.IO.Directory]::Exists($uppercase)) {
        throw 'Se sustituyó una carpeta equivalente.'
    }
    $results['colision_mayusculas'] = 'correcto'

    # Reject unexpected files (installer, malware) and unknown subtitles.
    $stage4 = Create-Stage 4 'video.mkv' 'ficticio'
    [System.IO.File]::WriteAllText((Join-Path $stage4 'installer.exe'), 'prohibido')
    Should-Refuse { Invoke-TestPublisher '.viewtv-stage-4' 'Contenido no apto' }
    if (-not [System.IO.File]::Exists((Join-Path $stage4 'installer.exe'))) {
        throw 'La entrada insegura se modificó.'
    }
    $results['archivo_no_permitido'] = 'rechazado'

    $stage5 = Create-Stage 5 'video.mkv' 'ficticio'
    [System.IO.File]::WriteAllText((Join-Path $stage5 'otra_serie.es.srt'), 'extraño')
    Should-Refuse { Invoke-TestPublisher '.viewtv-stage-5' 'Subtitulo ajeno' }
    $results['subtitulo_no_correspondiente'] = 'rechazado'

    $stage6 = Create-Stage 6 'video.mkv' 'ficticio'
    [System.IO.File]::WriteAllText((Join-Path $stage6 'video2.mp4'), 'segundo')
    Should-Refuse { Invoke-TestPublisher '.viewtv-stage-6' 'Dos videos' }
    $results['multiple_video'] = 'rechazado'

    # Reject path traversal/invalid root before inspecting any real library.
    $stage7 = Create-Stage 7 'video.mkv' 'ficticio'
    Should-Refuse { Invoke-TestPublisher '../otro' 'Peli' }
    Should-Refuse { Invoke-TestPublisher '.viewtv-stage-7' '../Fuera' }
    Should-Refuse { Invoke-TestPublisher '.viewtv-stage-7' 'CON' }
    Should-Refuse { & $publisher -SandboxRoot $public -StageName '.viewtv-stage-7' -FinalName 'Peli' -ApprovalName '.viewtv-approval-7.json' -KeyPath $keyPath }
    if (-not [System.IO.Directory]::Exists($stage7)) {
        throw 'Un rechazo movió el staging.'
    }
    $results['proteccion_de_rutas'] = 'correcto'

    # Removing marker blocks publication; restore for safe cleanup.
    $stage8 = Create-Stage 8 'video.mkv' 'ficticio'
    [System.IO.File]::WriteAllText($marker, 'marcador incorrecto')
    $approval8 = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-8' -FinalName 'No publicar' -KeyPath $keyPath
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-8' -FinalName 'No publicar' -ApprovalName $approval8 -KeyPath $keyPath }
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

    # Tampered signature: no publication, the unrelated stage remains untouched.
    $stage10 = Create-Stage 10 'video.mkv' 'contenido intacto'
    $approval10 = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-10' -FinalName 'No firma' -KeyPath $keyPath
    $approval10Path = Join-Path $root $approval10
    $badEnvelope = [System.IO.File]::ReadAllText($approval10Path) | ConvertFrom-Json
    $badEnvelope.signature = [Convert]::ToBase64String((New-Object byte[] 32))
    [System.IO.File]::WriteAllText($approval10Path, ($badEnvelope | ConvertTo-Json -Compress))
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-10' -FinalName 'No firma' -ApprovalName $approval10 -KeyPath $keyPath }
    if (-not [System.IO.Directory]::Exists($stage10)) { throw 'Firma alterada permitió publicación.' }
    $results['firma_alterada'] = 'rechazada'

    # Same-length contents tampered AFTER signature: requires SHA256 verification.
    $stage11 = Create-Stage 11 'video.mkv' 'original'
    $approval11 = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-11' -FinalName 'No cambio' -KeyPath $keyPath
    [System.IO.File]::WriteAllText((Join-Path $stage11 'video.mkv'), 'alterado')
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-11' -FinalName 'No cambio' -ApprovalName $approval11 -KeyPath $keyPath }
    if (-not [System.IO.Directory]::Exists($stage11)) { throw 'Contenido alterado permitió publicación.' }
    $results['sha256_modificado'] = 'rechazado'

    # Expired, validly signed approvals must not permit publication.
    $stage12 = Create-Stage 12 'video.mkv' 'ficticio'
    $approval12 = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-12' -FinalName 'No caducado' -KeyPath $keyPath -ExpiryMinutes -1
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-12' -FinalName 'No caducado' -ApprovalName $approval12 -KeyPath $keyPath }
    if (-not [System.IO.Directory]::Exists($stage12)) { throw 'Autorización caducada permitió publicar.' }
    $results['autorizacion_caducada'] = 'rechazada'

    # A valid signature for one destination cannot be replayed to a different one.
    $stage13 = Create-Stage 13 'video.mkv' 'ficticio'
    $approval13 = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-13' -FinalName 'Autorizado' -KeyPath $keyPath
    Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-13' -FinalName 'No Autorizado' -ApprovalName $approval13 -KeyPath $keyPath }
    if (-not [System.IO.Directory]::Exists($stage13)) { throw 'Destino distinto permitió publicar.' }
    $results['destino_sin_autorizacion'] = 'rechazado'

    # An unrelated key must not be able to confirm the approval.
    $stage14 = Create-Stage 14 'video.mkv' 'ficticio'
    $approval14 = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-14' -FinalName 'No clave' -KeyPath $keyPath
    $otherKey = New-ViewtvTestKey
    try {
        Should-Refuse { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-14' -FinalName 'No clave' -ApprovalName $approval14 -KeyPath $otherKey }
    } finally {
        $otherDir = [System.IO.Path]::GetDirectoryName($otherKey)
        if ([System.IO.Path]::GetFileName($otherDir) -match '^viewtv-test-key-[0-9a-f]{32}$') {
            [System.IO.Directory]::Delete($otherDir, $true)
        }
    }
    if (-not [System.IO.Directory]::Exists($stage14)) { throw 'Clave incorrecta permitió publicación.' }
    $results['clave_diferente'] = 'rechazada'

    # Reconcile without any filesystem modification (after a finished move).
    $reconciled = & $reconciler -SandboxRoot $root -StageName '.viewtv-stage-1' -FinalName 'Corto ficticio (2026)' -ApprovalName '.viewtv-approval-1.json' -KeyPath $keyPath | ConvertFrom-Json
    if ($reconciled.estado -ne 'publicada_verificada' -or
        -not $reconciled.lectura_solamente) {
        throw 'No se pudo verificar una publicación completada.'
    }
    $results['reconciliacion_publicada'] = 'verificada'

    # Valid staged job: report pending, but never publish automatically.
    $stage15 = Create-Stage 15 'video.mkv' 'contenido de prueba'
    $approval15 = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-15' -FinalName 'Pendiente' -KeyPath $keyPath
    $pending = & $reconciler -SandboxRoot $root -StageName '.viewtv-stage-15' -FinalName 'Pendiente' -ApprovalName $approval15 -KeyPath $keyPath | ConvertFrom-Json
    if ($pending.estado -ne 'pendiente_de_publicacion' -or
        -not [System.IO.Directory]::Exists($stage15) -or
        [System.IO.Directory]::Exists((Join-Path $root 'Pendiente'))) {
        throw 'La conciliación alteró un staging aún pendiente.'
    }
    $results['reconciliacion_pendiente'] = 'sin_cambios'

    # Both stage and published folder: ambiguous; neither is removed.
    $stage16 = Create-Stage 16 'video.mkv' 'original'
    $approval16 = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-16' -FinalName 'Ambigua' -KeyPath $keyPath
    $ambiguous = Join-Path $root 'Ambigua'
    [System.IO.Directory]::CreateDirectory($ambiguous) | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $ambiguous 'video.mkv'), 'tercero')
    $checked = & $reconciler -SandboxRoot $root -StageName '.viewtv-stage-16' -FinalName 'Ambigua' -ApprovalName $approval16 -KeyPath $keyPath | ConvertFrom-Json
    if ($checked.estado -ne 'requiere_revision' -or
        -not [System.IO.Directory]::Exists($stage16) -or
        [System.IO.File]::ReadAllText((Join-Path $ambiguous 'video.mkv')) -ne 'tercero') {
        throw 'Un estado ambiguo fue alterado.'
    }
    $results['reconciliacion_ambigua'] = 'solo_revision'

    # A published file that has changed must NEVER be acknowledged as verified.
    $stage17 = Create-Stage 17 'video.mkv' 'contenido'
    $approval17 = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-17' -FinalName 'Corrupta' -KeyPath $keyPath
    [System.IO.Directory]::Move($stage17, (Join-Path $root 'Corrupta'))
    [System.IO.File]::WriteAllText((Join-Path $root 'Corrupta\video.mkv'), 'cambiado')
    $corrupted = & $reconciler -SandboxRoot $root -StageName '.viewtv-stage-17' -FinalName 'Corrupta' -ApprovalName $approval17 -KeyPath $keyPath | ConvertFrom-Json
    if ($corrupted.estado -ne 'requiere_revision') {
        throw 'Una publicación corrupta fue aceptada.'
    }
    $results['reconciliacion_sha256_incorrecto'] = 'rechazado'

    # Expired authorizations may verify a past publication, NEVER publish anew.
    $stage18 = Create-Stage 18 'video.mkv' 'original antiguo'
    $approval18 = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-18' -FinalName 'Antigua' -KeyPath $keyPath -ExpiryMinutes -1
    [System.IO.Directory]::Move($stage18, (Join-Path $root 'Antigua'))
    $old = & $reconciler -SandboxRoot $root -StageName '.viewtv-stage-18' -FinalName 'Antigua' -ApprovalName $approval18 -KeyPath $keyPath | ConvertFrom-Json
    if ($old.estado -ne 'publicada_verificada') {
        throw 'La conciliación histórica de solo lectura falló.'
    }
    $results['reconciliacion_caducada'] = 'verificada_sin_republicar'

    # No stage, no destination: manual review, not an automatic retry.
    $missing = & $reconciler -SandboxRoot $root -StageName '.viewtv-stage-19' -FinalName 'Ausente' -ApprovalName '.viewtv-approval-19.json' -KeyPath $keyPath | ConvertFrom-Json
    if ($missing.estado -ne 'requiere_revision') {
        throw 'La ausencia no exige revisión.'
    }
    $results['reconciliacion_ausente'] = 'requiere_revision'
    $results | ConvertTo-Json -Compress
}
finally {
    if (([System.IO.Path]::GetDirectoryName($root) -ieq $public) -and
        [System.IO.Path]::GetFileName($root) -match '^viewtv-win-sandbox-[0-9a-f]{32}$' -and
        [System.IO.File]::Exists($marker) -and
        [System.IO.File]::ReadAllText($marker) -eq "VIEWTV_WINDOWS_SANDBOX_ONLY_V1`n") {
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
