# VIEWTV 0043: 2 fallos tras segundo unlink nativo en sandboxes GUID.
# Ninguna ruta de medios ni argumento de usuario; se invoca solo TestAfterBoth.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$script=Join-Path $PSScriptRoot 'viewtv_windows_crash_recovery_sandbox_0042.ps1'
$info=[IO.FileInfo]::new($script)
if(-not $info.Exists -or
   ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
    throw 'Ensayo NTFS requerido no encontrado.'
}
$exe=Join-Path $PSHOME 'powershell.exe'
if(-not [IO.File]::Exists($exe)){throw 'PowerShell no disponible.'}
$expected=@(
    'KILL_REAL_POST_PRIMER_UNLINK=PASS',
    'TERCER_HARDLINK_BLOQUEA_RECUPERACION=PASS',
    'RECUPERACION_IDEMPOTENTE_FILE_ID=PASS',
    'KILL_REAL_DURANTE_UNLINK_NATIVO=PASS',
    'RECUPERACION_NATIVA_RESTAURA_FILE_ID=PASS',
    'LECTOR_PREABIERTO_BLOQUEA_COMMIT=PASS',
    'KILL_REAL_POST_SEGUNDO_UNLINK_NATIVE=PASS',
    'NOMBRE_REOCUPADO_BLOQUEA_RECONCILIACION=PASS',
    'RECONCILIACION_DOS_UNLINKS_SIN_REPETIR_BORRADO=PASS',
    'SANDBOX_GUID_LIMPIADO=SI',
    'EJECUTOR_PRODUCCION_INSTALADO=NO',
    'BORRADOS_REALES=0',
    'TORRENTS_REALES_MODIFICADOS=0'
)
for($case=1;$case -le 2;$case++){
    $start=[Diagnostics.ProcessStartInfo]::new()
    $start.FileName=$exe
    $start.Arguments=(
        '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+
        $script+'" -Mode TestAfterBoth'
    )
    $start.UseShellExecute=$false
    $start.CreateNoWindow=$true
    $start.RedirectStandardOutput=$true
    $start.RedirectStandardError=$true
    $process=[Diagnostics.Process]::Start($start)
    try{
        if(-not $process.WaitForExit(110000)){
            $process.Kill()
            throw 'Timeout de crash postcommit.'
        }
        if($process.ExitCode -ne 0){
            throw 'El ensayo postcommit termino con error.'
        }
        $lines=$process.StandardOutput.ReadToEnd().Trim() -split "\r?\n"
        if($lines.Count -ne $expected.Count){
            throw 'Salida postcommit inesperada.'
        }
        for($i=0;$i -lt $expected.Count;$i++){
            if($lines[$i].Trim() -cne $expected[$i]){
                throw 'Contrato de postcommit no satisfecho.'
            }
        }
        Write-Output ('RECUPERACION_POST_SEGUNDO_UNLINK_0043_'+$case+'=PASS')
    } finally {$process.Dispose()}
}
Write-Output 'KILL_REAL_TRAS_DOS_UNLINKS_NATIVOS=PASS'
Write-Output 'NOMBRE_REOCUPADO_NO_SE_BORRA=PASS'
Write-Output 'RECONCILIACION_SIN_REPETIR_UNLINK=PASS'
Write-Output 'DOS_SANDBOX_GUID_LIMPIADOS=SI'
Write-Output 'EJECUTOR_PRODUCCION_INSTALADO=NO'
Write-Output 'BORRADOS_REALES=0'
Write-Output 'TORRENTS_MODIFICADOS=0'
