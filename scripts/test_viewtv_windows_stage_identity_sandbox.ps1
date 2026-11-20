# Pruebas NTFS de identificadores, solo directorios nuevos en Public.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_stage_identity_sandbox.ps1')
$public = [IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
if ($public -ine 'C:\Users\Public') { throw 'Public debe estar en C:.' }
$root = Join-Path $public ('viewtv-win-sandbox-'+[guid]::NewGuid().ToString('N'))
$marker = Join-Path $root '.viewtv-win-sandbox-only'
$mark = "VIEWTV_WINDOWS_SANDBOX_ONLY_V1"+[char]10
$results=[ordered]@{}
$keyPath=$null
. (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')
$publisher = Join-Path $PSScriptRoot 'viewtv_windows_publish_sandbox.ps1'
function Must-Fail([scriptblock]$script) {
    $failed=$false
    try { & $script | Out-Null } catch { $failed=$true }
    if (-not $failed) { throw 'La entrada NTFS insegura fue aceptada.' }
}
try {
    if ([IO.Directory]::Exists($root) -or [IO.File]::Exists($root)) {
        throw 'Carpeta GUID ya existe.'
    }
    [IO.Directory]::CreateDirectory($root) | Out-Null
    [IO.File]::WriteAllText($marker,$mark)
    $stage1=Join-Path $root '.viewtv-stage-1'
    [IO.Directory]::CreateDirectory($stage1) | Out-Null
    $file1=Join-Path $stage1 'Corto ficticio.mkv'
    [IO.File]::WriteAllText($file1,'mismo contenido')
    $first=Get-ViewtvTestStageFingerprint $root '.viewtv-stage-1'
    if ($first -cne (Get-ViewtvTestStageFingerprint $root '.viewtv-stage-1')) {
        throw 'Identificador NTFS no estable.'
    }
    $results['identidad_estable']='correcto'

    # Identical SHA-256 but different NTFS file identity must be detected.
    $oldFile=Join-Path $stage1 'old.tmp'
    [IO.File]::Move($file1,$oldFile)
    [IO.File]::WriteAllText($file1,'mismo contenido')
    if ((Get-FileHash -LiteralPath $file1 -Algorithm SHA256).Hash -cne
        (Get-FileHash -LiteralPath $oldFile -Algorithm SHA256).Hash) {
        throw 'La prueba no contiene bytes idénticos.'
    }
    $second=Get-ViewtvTestStageFingerprint $root '.viewtv-stage-1'
    if ($first -ceq $second) { throw 'Sustitución con mismo hash no detectada.' }
    [IO.File]::Delete($oldFile)
    $results['sustitucion_mismos_bytes']='detectada'

    # Hardlink sharing the same backing object outside the stage.
    $stage2=Join-Path $root '.viewtv-stage-2'
    [IO.Directory]::CreateDirectory($stage2) | Out-Null
    $file2=Join-Path $stage2 'Corto ficticio.mkv'
    [IO.File]::WriteAllText($file2,'datos ficticios')
    $extra=Join-Path $root 'otra-referencia.tmp'
    $null = New-Item -ItemType HardLink -Path $extra -Target $file2 -ErrorAction Stop
    Must-Fail { Get-ViewtvTestStageFingerprint $root '.viewtv-stage-2' }
    $results['hardlink_multiple']='rechazado'

    # Directory reparse point is never treated as a verified staging folder.
    $link=Join-Path $root '.viewtv-stage-3'
    $null = New-Item -ItemType Junction -Path $link -Target $stage1 -ErrorAction Stop
    Must-Fail { Get-ViewtvTestStageFingerprint $root '.viewtv-stage-3' }
    $results['junction_staging']='rechazado'

    # NTFS prohibits renaming the directory with an open child file even when
    # the stream was opened with FileShare.Delete. Hence handles must be closed
    # before the move; this test is evidence of the remaining TOCTOU window.
    $stage4=Join-Path $root '.viewtv-stage-4'
    [IO.Directory]::CreateDirectory($stage4) | Out-Null
    $file4=Join-Path $stage4 'video.mkv'
    [IO.File]::WriteAllText($file4,'video')
    $share=[IO.FileShare]::Read -bor [IO.FileShare]::Delete
    $opened=[IO.FileStream]::new($file4,[IO.FileMode]::Open,[IO.FileAccess]::Read,$share)
    try {
        Must-Fail { [IO.Directory]::Move($stage4,(Join-Path $root 'MovimientoInseguro')) }
        $results['descriptor_abierto_bloquea_move']='confirmado'
    } finally {
        $opened.Dispose()
    }

    # Test against real sandbox publisher: identical bytes but a DIFFERENT
    # NTFS file ID since the approval was created must not be published.
    $stage5=Join-Path $root '.viewtv-stage-5'
    [IO.Directory]::CreateDirectory($stage5) | Out-Null
    $file5=Join-Path $stage5 'Video de prueba.mkv'
    [IO.File]::WriteAllText($file5,'contenido original')
    $keyPath = New-ViewtvTestKey
    $approval = New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-5' -FinalName 'No publicar sustitucion' -KeyPath $keyPath
    $previous = Join-Path $root 'sustituido-original.tmp'
    [IO.File]::Move($file5,$previous)
    [IO.File]::WriteAllText($file5,'contenido original')
    if ((Get-FileHash -LiteralPath $file5 -Algorithm SHA256).Hash -cne (Get-FileHash -LiteralPath $previous -Algorithm SHA256).Hash) {
        throw 'El ensayo de sustitución no conserva SHA-256.'
    }
    Must-Fail { & $publisher -SandboxRoot $root -StageName '.viewtv-stage-5' -FinalName 'No publicar sustitucion' -ApprovalName $approval -KeyPath $keyPath }
    if (-not [IO.Directory]::Exists($stage5) -or [IO.Directory]::Exists((Join-Path $root 'No publicar sustitucion'))) {
        throw 'El publicador permitió la sustitución con hashes idénticos.'
    }
    $results['publicador_rechaza_identidad_sustituida']='correcto'

    # Full allowed 20-file group: signed IDs must not inadvertently exceed
    # the safely bounded approval envelope.
    $stage6=Join-Path $root '.viewtv-stage-6'
    [IO.Directory]::CreateDirectory($stage6) | Out-Null
    $stem='Titulo '+('a'*129)
    [IO.File]::WriteAllText((Join-Path $stage6 ($stem+'.mkv')), 'video ficticio')
    for($i=1; $i -le 19; $i++) {
        $name=$stem+('.s{0:00}.srt' -f $i)
        [IO.File]::WriteAllText((Join-Path $stage6 $name), ('subtitulo ficticio '+$i))
    }
    $approval6=New-ViewtvTestApproval -SandboxRoot $root -StageName '.viewtv-stage-6' -FinalName 'Grupo con subtitulos' -KeyPath $keyPath
    $ok6 = & $publisher -SandboxRoot $root -StageName '.viewtv-stage-6' -FinalName 'Grupo con subtitulos' -ApprovalName $approval6 -KeyPath $keyPath | ConvertFrom-Json
    if ($ok6.estado -ne 'publicada_en_sandbox' -or $ok6.archivos -ne 20 -or
        [IO.Directory]::Exists($stage6) -or
        @(Get-ChildItem -LiteralPath (Join-Path $root 'Grupo con subtitulos') -File).Count -ne 20) {
        throw 'Grupo de 20 ficheros no publicado íntegro.'
    }
    $results['video_y_19_subtitulos_ntfs']='correcto'

    $results | ConvertTo-Json -Compress
} finally {
    if ($keyPath -and [IO.File]::Exists($keyPath)) {
        $keyDir=[IO.Path]::GetDirectoryName($keyPath)
        if ([IO.Path]::GetDirectoryName($keyDir) -ieq [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\\') -and
            [IO.Path]::GetFileName($keyDir) -cmatch '^viewtv-test-key-[0-9a-f]{32}$') {
            [IO.Directory]::Delete($keyDir,$true)
        }
    }
    if ([IO.Directory]::Exists($root) -and
        [IO.Path]::GetDirectoryName($root) -ieq $public -and
        [IO.Path]::GetFileName($root) -cmatch '^viewtv-win-sandbox-[0-9a-f]{32}$' -and
        ([IO.DirectoryInfo]::new($root).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
        [IO.File]::Exists($marker) -and [IO.File]::ReadAllText($marker) -ceq $mark) {
        # Explicitly remove the reparse link itself, never its target.
        $junction=Join-Path $root '.viewtv-stage-3'
        if ([IO.Directory]::Exists($junction) -and
            ([IO.DirectoryInfo]::new($junction).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            [IO.Directory]::Delete($junction,$false)
        }
        [IO.Directory]::Delete($root,$true)
    }
}
