# VIEWTV 0034 — suite Windows NTFS, EXCLUSIVAMENTE ficciones en TEMP.
# Ejecuta cada prueba en proceso nuevo; no admite rutas ni argumentos.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

$tests = @(
    @{
        name='exclusividad'
        script='viewtv_windows_ntfs_exclusividad_sandbox_0034.ps1'
        lines=@(
            'LECTOR_PREEXISTENTE_BLOQUEA_EXCLUSION=PASS'
            'TERCER_HARDLINK_BLOQUEA_RETIRADA=PASS'
            'HARDLINKS_NTFS_NO_ADMITEN_LECTOR_NI_ESCRITOR_DURANTE_LOCK=PASS'
            'TERCER_HARDLINK_BAJO_FILESHARE_NONE=POSIBLE'
            'SOLTAR_EXCLUSION_PERMITE_REAPERTURA=PASS'
            'EXCLUSION_SOLA_NO_PERMITE_UNLINK_ATOMICO=SI'
            'RESULTADO_EJECUTOR_REAL=NO_AUTORIZADO'
            'BORRADOS_PRODUCCION=0'
            'TORRENTS_MODIFICADOS=0'
        )
    },
    @{
        name='doble_handle'
        script='viewtv_windows_ntfs_dual_handle_sandbox_0034.ps1'
        lines=@(
            'DOS_HANDLES_DELETE_MISMO_FILE_ID=PASS'
            'LECTORES_BLOQUEADOS_DURANTE_DOBLE_RESERVA=PASS'
            'TERCER_LINK_DURANTE_RESERVA=POSIBLE'
            'AISLAMIENTO_PRODUCCION_POR_SHARE_DELETE=INSUFICIENTE'
            'RESTAURAR_PRIMER_UNLINK_TRAS_CIERRE_SIMULADO=PASS'
            'UNLINK_PRIMER_HARDLINK_CON_HANDLES_RETENIDOS=PASS'
            'UNLINK_SEGUNDO_HARDLINK_CON_HANDLES_RETENIDOS=PASS'
            'DIARIO_WRITE_THROUGH_Y_RECONCILIACION_FILE_ID=PASS'
            'ENSAYO_DOS_UNLINKS_NTFS_SIN_SOLTAR_HANDLES=PASS'
            'EJECUTOR_PRODUCCION_AUN_NO_IMPLEMENTADO=SI'
            'ARCHIVOS_REALES_ELIMINADOS=0'
            'TORRENTS_MODIFICADOS=0'
        )
    }
)
$runner=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
if(-not [IO.File]::Exists($runner)) {
    throw 'PowerShell nativo no verificable.'
}
foreach($case in $tests) {
    $target=Join-Path $PSScriptRoot ([string]$case.script)
    if(-not [IO.File]::Exists($target) -or
       ([IO.FileInfo]::new($target).Attributes -band
        [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Una prueba Windows 0034 no es un archivo regular.'
    }
    # Capturar sólo los indicadores. No publicar ninguna salida interna de
    # excepción ni de rutas Windows en caso de fallo.
    $observed=@(& $runner -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $target 2>$null)
    if($LASTEXITCODE -ne 0 -or
       $observed.Count -ne @($case.lines).Count) {
        throw ('Falla prueba 0034: '+$case.name)
    }
    for($i=0;$i -lt $observed.Count;$i++) {
        if([string]$observed[$i] -cne [string]$case.lines[$i]) {
            throw ('Informe NTFS 0034 contradictorio: '+$case.name)
        }
    }
    Write-Output ('PRUEBA_NTFS_0034_'+[string]$case.name+'=PASS')
}
Write-Output 'NTFS_0034_DOS_SUITES_SANDBOX=PASS'
Write-Output 'NUEVOS_HARDLINKS_CON_LOCK_PUEDEN_APARECER=SI'
Write-Output 'PREPARADO_PARA_BORRADO_REAL=NO'
Write-Output 'ARCHIVOS_REALES_ELIMINADOS=0'
Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
