# VIEWTV: read-only reconciliation of an ambiguous Windows test publication.
# NO copying, moving, renaming, deleting, modifying SQLite or torrent actions.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SandboxRoot,
    [Parameter(Mandatory=$true)][string]$StageName,
    [Parameter(Mandatory=$true)][string]$FinalName,
    [Parameter(Mandatory=$true)][string]$ApprovalName,
    [Parameter(Mandatory=$true)][string]$KeyPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')

$public = [System.IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
$root = [System.IO.Path]::GetFullPath($SandboxRoot).TrimEnd('\')
if (
    [System.IO.Path]::GetDirectoryName($root) -ine $public -or
    [System.IO.Path]::GetFileName($root) -cnotmatch '^viewtv-win-sandbox-[0-9a-f]{32}$' -or
    -not [System.IO.Directory]::Exists($root)
) {
    throw 'La reconciliación solo permite sandboxes Windows de prueba.'
}
$dir = [System.IO.DirectoryInfo]::new($root)
if (($dir.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'Raíz redirigida no permitida.'
}
$marker = [System.IO.FileInfo]::new((Join-Path $root '.viewtv-win-sandbox-only'))
if (
    -not $marker.Exists -or
    ($marker.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -or
    [System.IO.File]::ReadAllText($marker.FullName) -cne ("VIEWTV_WINDOWS_SANDBOX_ONLY_V1" + [char]10)
) {
    throw 'Marcador de sandbox inválido.'
}
if (
    $StageName -cnotmatch '^\.viewtv-stage-[1-9][0-9]{0,9}$' -or
    [string]::IsNullOrWhiteSpace($FinalName) -or
    $FinalName -match '[<>:"/\\|?*\x00-\x1f]' -or
    $FinalName.StartsWith('.') -or
    $FinalName.EndsWith('.') -or
    $FinalName.Trim() -cne $FinalName -or
    $ApprovalName -cnotmatch '^\.viewtv-approval-[1-9][0-9]{0,9}\.json$'
) {
    throw 'Identificador del plan no autorizado.'
}
$stage = Join-Path $root $StageName
$final = Join-Path $root $FinalName
$stagePresent = [System.IO.Directory]::Exists($stage)
$finalPresent = [System.IO.Directory]::Exists($final)
$state = 'requiere_revision'
$reason = 'resultado_ambiguo'
if ($stagePresent -and $finalPresent) {
    $state = 'requiere_revision'
    $reason = 'staging_y_destino_presentes'
} elseif (-not $stagePresent -and -not $finalPresent) {
    $state = 'requiere_revision'
    $reason = 'faltan_staging_y_destino'
} else {
    try {
        if ($stagePresent) {
            $valid = Assert-ViewtvTestApproval -SandboxRoot $root -StageName $StageName -FinalName $FinalName -ApprovalName $ApprovalName -KeyPath $KeyPath -Location Stage
            if ($valid) {
                $state = 'pendiente_de_publicacion'
                $reason = 'staging_verificado'
            }
        } else {
            # An expired approval CAN verify an already published folder but
            # NEVER permits a new publication or an automatic retry.
            $valid = Assert-ViewtvTestApproval -SandboxRoot $root -StageName $StageName -FinalName $FinalName -ApprovalName $ApprovalName -KeyPath $KeyPath -Location Published -AllowExpiredReadOnly
            if ($valid) {
                $state = 'publicada_verificada'
                $reason = 'destino_coincide_con_plan_firmado'
            }
        }
    } catch {
        $state = 'requiere_revision'
        $reason = 'validacion_del_plan_fallida'
    }
}
[pscustomobject]@{
    estado = $state
    motivo = $reason
    lectura_solamente = $true
} | ConvertTo-Json -Compress
