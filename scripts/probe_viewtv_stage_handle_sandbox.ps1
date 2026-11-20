# Prueba de compatibilidad de descriptores NTFS; NUNCA producción.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$public = [IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
if ($public -ine 'C:\Users\Public') { throw 'Raíz no permitida.' }
$root = Join-Path $public ('viewtv-win-sandbox-' + [guid]::NewGuid().ToString('N'))
$marker = Join-Path $root '.viewtv-win-sandbox-only'
$markerText = "VIEWTV_WINDOWS_SANDBOX_ONLY_V1" + [char]10
$results = [ordered]@{}
try {
    [IO.Directory]::CreateDirectory($root) | Out-Null
    [IO.File]::WriteAllText($marker, $markerText)
    foreach ($variant in @('Read','ReadDelete','None','ReadWriteDelete')) {
        $stage = Join-Path $root ('.viewtv-stage-' + [string]($results.Count+1))
        $final = Join-Path $root ('Resultado-' + $variant)
        [IO.Directory]::CreateDirectory($stage) | Out-Null
        $file = Join-Path $stage 'video.mkv'
        [IO.File]::WriteAllText($file,'video de prueba')
        $share = switch ($variant) {
            'Read' { [IO.FileShare]::Read }
            'ReadDelete' { [IO.FileShare]::Read -bor [IO.FileShare]::Delete }
            'None' { [IO.FileShare]::None }
            'ReadWriteDelete' { [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete }
        }
        $stream = [IO.FileStream]::new($file,[IO.FileMode]::Open,[IO.FileAccess]::Read,$share)
        try {
            $writeDenied = $false
            try {
                $probe = [IO.FileStream]::new($file,[IO.FileMode]::Open,[IO.FileAccess]::Write,[IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete)
                $probe.Dispose()
            } catch [IO.IOException] { $writeDenied = $true }
            $moveWorked = $false
            $moveError = ''
            try {
                [IO.Directory]::Move($stage,$final)
                $moveWorked = $true
            } catch { $moveError = $_.Exception.GetType().Name }
            $results[$variant] = [pscustomobject]@{escritura_bloqueada=$writeDenied;movimiento_permitido=$moveWorked;error=$moveError}
        } finally {
            $stream.Dispose()
        }
    }
    foreach ($variant in @('Read','ReadDelete','None','ReadWriteDelete')) {
        if ($results[$variant].movimiento_permitido) {
            throw 'La prueba de bloqueo NTFS cambió: revisar compatibilidad.'
        }
        $expectedWriteDenied = $variant -ne 'ReadWriteDelete'
        if ($results[$variant].escritura_bloqueada -ne $expectedWriteDenied) {
            throw 'Las reglas FileShare no coinciden con lo esperado.'
        }
    }
    $results | ConvertTo-Json -Compress
} finally {
    if ($root -and [IO.Directory]::Exists($root) -and
        [IO.Path]::GetDirectoryName($root) -ieq $public -and
        [IO.Path]::GetFileName($root) -cmatch '^viewtv-win-sandbox-[0-9a-f]{32}$' -and
        ([IO.DirectoryInfo]::new($root).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
        [IO.File]::Exists($marker) -and [IO.File]::ReadAllText($marker) -ceq $markerText) {
        [IO.Directory]::Delete($root,$true)
    }
}
