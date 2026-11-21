# Ejecución automática y periódica (una sola pasada).
# Se ejecuta EXCLUSIVAMENTE con usuario interactivo limitado.
# Nunca requiere LocalSystem, PIN, cambios a torrents o servicio SCM.
[CmdletBinding()]
param([ValidateSet('Preflight','Once')][string]$Mode='Preflight')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root='C:\VIEWTV\publicador'
$publisher=Join-Path (Join-Path $root 'bin') 'viewtv_windows_publicador_0013.ps1'
$journal=Join-Path $root 'journal'
$logfile=Join-Path $journal 'tarea-periodica-0013-estado.json'
$principal=[Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent())
# El script dot-source tiene un parámetro $Mode propio y lo cambia
# al cargar -Mode Library; conservar el solicitado antes de importarlo.
$requestedMode=$Mode

function Write-SafeStatus([string]$State, [string]$Publication='ninguna',
                          [string]$Catalog='pendiente') {
    $record=[ordered]@{
        estado=$State
        publicacion=$Publication
        catalogo=$Catalog
        fecha_utc=[DateTime]::UtcNow.ToString('o')
    } | ConvertTo-Json -Compress
    if (-not [IO.Directory]::Exists($journal)) {
        throw 'Diario privado no disponible.'
    }
    if ([IO.File]::Exists($logfile)) {
        $existing=[IO.FileInfo]::new($logfile)
        if (($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
            $existing.Length -gt 4096) {
            throw 'Estado del publicador no seguro.'
        }
    }
    # File.Replace exige privilegios ajenos al usuario limitado en este
    # Windows. Es SOLO una telemetría prescindible, no un diario de
    # publicación ni una decisión de autoridad; escribir sobre el
    # archivo propio conserva la ACL de usuario ya verificada.
    [IO.File]::WriteAllText($logfile,$record,[Text.Encoding]::UTF8)
}

try {
    if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Se prohíbe el publicador ejecutándose elevado.'
    }
    if (-not [IO.File]::Exists($publisher)) {
        throw 'No existe el publicador Windows aprobado.'
    }
    . $publisher -Mode Library
    $policy=Get-ViewtvPolicy
    if ([string]$policy.mode -cne 'general' -or
        [int]$policy.after_id -ne 3 -or
        $null -ne $policy.allowed_download_id) {
        throw 'El corte histórico o modo de Windows no coincide.'
    }
    Assert-AuthorityReady $policy
    if ($requestedMode -ceq 'Preflight') {
        Write-Output 'TAREA_PUBLICADOR_LIMITADA_ID_MAYOR_3=OK'
        return
    }

    $powershell=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $output=@(& $powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $publisher -Mode Once)
    if ($LASTEXITCODE -ne 0 -or $output.Count -ne 1 -or
        $output[0] -cnotin @('sin_trabajos','publicada','reconciliada')) {
        throw 'Una pasada del publicador no terminó con estado válido.'
    }
    # Sincronizar por el mecanismo transaccional oficial:
    # si Jellyfin sigue escaneando, la próxima pasada vuelve a sincronizar.
    $sync=@(& docker.exe exec viewtv-api-1 python -m worker.organization_windows_cli sync)
    if ($LASTEXITCODE -ne 0 -or $sync.Count -ne 1 -or
        $sync[0].Length -gt 4096) {
        throw 'Falló la sincronización controlada del catálogo.'
    }
    $result=$sync[0] | ConvertFrom-Json
    if ([string]$result.estado -cne 'catalogo_sincronizado' -or
        $result.elementos_procesados -isnot [int] -or
        $result.elementos_procesados -lt 1) {
        throw 'El catálogo no quedó confirmado.'
    }
    Write-SafeStatus 'correcto' ([string]$output[0]) 'sincronizado'
    Write-Output 'TAREA_PUBLICADOR_Y_CATALOGO_0013_OK'
} catch {
    # Fallar cerrado; no enseñar tokens, nombres o rutas en la tarea.
    try { Write-SafeStatus 'requiere_revision' 'no_confirmada' 'no_confirmado' } catch {}
    [Console]::Error.WriteLine('TAREA_PUBLICADOR_0013_REQUIERE_REVISION')
    exit 2
}
