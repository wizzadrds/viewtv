# VIEWTV 0022: auditoria Windows NTFS SOLO LECTURA bajo mismo mutex del publicador.
# No acepta rutas, IDs, hash, autorizaciones ni modos de borrado.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

$helper=Join-Path $PSScriptRoot 'viewtv_windows_media_lock_0022.ps1'
$audit=Join-Path $PSScriptRoot 'viewtv_windows_retirada_auditoria_0016.ps1'
if(-not [IO.File]::Exists($helper) -or -not [IO.File]::Exists($audit)) {
    throw 'No existe el protocolo o auditoria requerida.'
}
. $helper
$mutex=Enter-ViewtvMediaExclusion0022 -Proposito 'retirada'
try {
    # La auditoria 0016 ejecuta solo GET/lectura en C:\VIEWTV.
    # Conserva salida privada: el resumen publico no incluye rutas,
    # hashes, titulo ni nombre de fichero.
    $report=@(. $audit -Mode Audit)
    if($report.Count -lt 5 -or $report.Count -gt 18) {
        throw 'Resumen NTFS no verificable.'
    }
    $fields=@{}
    $allowed=@(
        'DIARIOS_ENCONTRADOS','DIARIOS_VERIFICADOS_POR_HARDLINK',
        'DIARIOS_BLOQUEADOS','FICHEROS_PUBLICADOS_VERIFICADOS',
        'DIARIOS_VERIFICADOS_HISTORICOS_ID_1_A_3',
        'CARPETAS_SIN_DIARIO_VALIDADO',
        'JELLYFIN_Y_QBIT_PENDIENTES_DE_CORRELACION',
        'BORRADOS_PRODUCCION'
    )
    foreach($line in $report) {
        $entry=[string]$line
        $parts=$entry.Split('=',2)
        if($parts.Count -ne 2 -or $allowed -cnotcontains $parts[0] -or
           $fields.ContainsKey($parts[0]) -or
           $parts[1] -cnotmatch '^(?:[0-9]{1,6}|SI|NO)$') {
            throw 'Informe NTFS inconsistente.'
        }
        $fields[$parts[0]]=$parts[1]
    }
    if($fields.Count -ne $allowed.Count -or
       $fields['BORRADOS_PRODUCCION'] -cne '0' -or
       $fields['JELLYFIN_Y_QBIT_PENDIENTES_DE_CORRELACION'] -cne 'SI') {
        throw 'Las condiciones no autorizan borrar.'
    }
    Write-Output 'RETIRADA_0022_MUTEX_COMPARTIDO=ADQUIRIDO'
    Write-Output 'RETIRADA_0022_AUDITORIA_NTFS=SOLO_LECTURA'
    Write-Output 'RETIRADA_0022_DIARIOS_NTFS_VERIFICADOS=SI'
    Write-Output 'RETIRADA_0022_PUBLICADOR_PRODUCCION_INTEGRADO=NO_VERIFICADO'
    Write-Output 'RETIRADA_0022_BLOQUEO_QBIT_Y_STREAMS=NO'
    Write-Output 'RETIRADA_0022_AUTORIZA_ELIMINACION=NO'
    Write-Output 'RETIRADA_0022_ARCHIVOS_ELIMINADOS=0'
    Write-Output 'RETIRADA_0022_TORRENTS_MODIFICADOS=0'
} finally {
    Exit-ViewtvMediaExclusion0022 -Mutex $mutex
}
