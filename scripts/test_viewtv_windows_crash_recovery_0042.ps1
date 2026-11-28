# VIEWTV 0042: verifica en dos procesos nuevos un crash REAL de Windows.
# Todos los ficheros modificados los crea 0042 en TEMP; nunca acepta rutas.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

$target=Join-Path $PSScriptRoot 'viewtv_windows_crash_recovery_sandbox_0042.ps1'
$scriptInfo=[IO.FileInfo]::new($target)
if(-not $scriptInfo.Exists -or
   ($scriptInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
    throw 'No se encuentra el ensayo de crash autorizado.'
}
$exe=Join-Path $PSHOME 'powershell.exe'
if(-not [IO.File]::Exists($exe)){
    throw 'PowerShell nativo no esta disponible.'
}
$expected=@(
    'KILL_REAL_POST_PRIMER_UNLINK=PASS',
    'TERCER_HARDLINK_BLOQUEA_RECUPERACION=PASS',
    'RECUPERACION_IDEMPOTENTE_FILE_ID=PASS',
    'KILL_REAL_DURANTE_UNLINK_NATIVO=PASS',
    'RECUPERACION_NATIVA_RESTAURA_FILE_ID=PASS',
    'LECTOR_PREABIERTO_BLOQUEA_COMMIT=PASS',
    'DOS_UNLINKS_NATIVOS_Y_REPETICION=PASS',
    'SANDBOX_GUID_LIMPIADO=SI',
    'EJECUTOR_PRODUCCION_INSTALADO=NO',
    'BORRADOS_REALES=0',
    'TORRENTS_REALES_MODIFICADOS=0'
)
for($case=1;$case -le 2;$case++){
    $psi=[Diagnostics.ProcessStartInfo]::new()
    $psi.FileName=$exe
    $psi.Arguments=(
        '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+
        $target+'"'
    )
    $psi.UseShellExecute=$false
    $psi.CreateNoWindow=$true
    $psi.RedirectStandardOutput=$true
    $psi.RedirectStandardError=$true
    $process=[Diagnostics.Process]::Start($psi)
    try {
        if(-not $process.WaitForExit(100000)){
            $process.Kill()
            throw 'Timeout de crash ficticio.'
        }
        if($process.ExitCode -ne 0){
            throw 'El ensayo Windows termino con error.'
        }
        $out=$process.StandardOutput.ReadToEnd().Trim() -split "\r?\n"
        if($out.Count -ne $expected.Count){
            throw 'Contrato de salida de crash no coincide.'
        }
        for($i=0;$i -lt $expected.Count;$i++){
            if($out[$i].Trim() -cne $expected[$i]){
                throw 'Fallo o cambio de contrato de crash.'
            }
        }
        Write-Output ('ENSAYO_WINDOWS_CRASH_0042_'+$case+'=PASS')
    } finally {$process.Dispose()}
}
Write-Output 'KILL_POST_UNLINK_Y_KILL_WIN32_NATIVO=PASS'
Write-Output 'RECUPERACION_NTFS_DOS_VECES=PASS'
Write-Output 'CUATRO_RECUPERACIONES_EN_PROCESOS_NUEVOS=PASS'
Write-Output 'BORRADO_PRODUCTIVO_DESHABILITADO=SI'
Write-Output 'PELICULAS_REALES_BORRADAS=0'
Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
