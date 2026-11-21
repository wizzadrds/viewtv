# Prueba de acceso de servicio Windows LocalSystem a Docker Desktop,
# sin ejecutar el publicador ni tocar medios, torrents o SQLite.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$principal = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'El ensayo SCM requiere administrador.'
}
$public=[IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
if ($public -ine 'C:\Users\Public') { throw 'Ruta de sandbox inesperada.' }
$guid=[Guid]::NewGuid().ToString('N')
$root=Join-Path $public ('viewtv-svc-probe-'+$guid)
$service='ViewtvProbe'+$guid.Substring(0,12)
$script:created=$false
[IO.Directory]::CreateDirectory($root)|Out-Null
$marker=Join-Path $root '.viewtv-svc-probe-only'
[IO.File]::WriteAllText($marker,"VIEWTV_SVC_PROBE_TEST_ONLY_V1`n")
try {
    $docker=(Get-Command docker.exe -ErrorAction Stop).Source
    $result=Join-Path $root 'probe-status.txt'
    $exe=Join-Path $root 'probe.exe'
    $source=Join-Path $root 'probe.cs'
    $escapedDocker=$docker.Replace('\','\\')
    $escapedResult=$result.Replace('\','\\')
    $code=@"
using System;
using System.Diagnostics;
using System.IO;
using System.ServiceProcess;
using System.Threading;
public sealed class Probe : ServiceBase {
    public Probe() {
        ServiceName="$service"; CanStop=true;
    }
    protected override void OnStart(string[] args) {
        new Thread(() => {
            string outcome="ERROR";
            try {
                var p = new Process();
                p.StartInfo.FileName="$escapedDocker";
                p.StartInfo.Arguments="version --format \"{{.Server.Version}}\"";
                p.StartInfo.CreateNoWindow=true;
                p.StartInfo.UseShellExecute=false;
                p.StartInfo.RedirectStandardOutput=true;
                p.StartInfo.RedirectStandardError=true;
                p.Start();
                if (p.WaitForExit(10000)) {
                    outcome = p.ExitCode==0 ? "DOCKER_ACCESS_OK" : "DOCKER_ACCESS_DENIED";
                } else {
                    p.Kill(); outcome="DOCKER_TIMEOUT";
                }
                p.Dispose();
            } catch (Exception) { outcome="DOCKER_LAUNCH_FAILED"; }
            File.WriteAllText("$escapedResult", outcome);
        }) { IsBackground=true }.Start();
    }
    public static void Main(){ ServiceBase.Run(new Probe()); }
}
"@
    [IO.File]::WriteAllText($source,$code)
    $compiler='C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    & $compiler /nologo /target:exe /reference:System.ServiceProcess.dll ("/out:"+$exe) $source
    if($LASTEXITCODE -ne 0){throw 'No compila el servicio de prueba.'}
    & sc.exe create $service 'binPath=' $exe 'start=' 'demand' 'obj=' 'LocalSystem' | Out-Null
    if($LASTEXITCODE -ne 0){throw 'SCM_CREATE_FAILED'}
    $script:created=$true
    $startResult=@(& sc.exe start $service)
    $startExit=$LASTEXITCODE
    if($startExit -ne 0){
        $startResult | ForEach-Object { Write-Output $_ }
        throw ('SCM_START_FAILED_CODE_'+$startExit)
    }
    for($i=0;$i -lt 20 -and -not [IO.File]::Exists($result);$i++){
        Start-Sleep -Milliseconds 500
    }
    if(-not [IO.File]::Exists($result)){throw 'No respondió el servicio Windows.'}
    $answer=[IO.File]::ReadAllText($result)
    Write-Output ('WINDOWS_SERVICE_DOCKER_PROBE='+$answer)
    if($answer -cne 'DOCKER_ACCESS_OK'){throw 'Acceso al Docker del servicio no verificado.'}
} finally {
    if($script:created){
        & sc.exe stop $service | Out-Null
        Start-Sleep -Milliseconds 300
        & sc.exe delete $service | Out-Null
        Start-Sleep -Milliseconds 300
    }
    if ([IO.Directory]::Exists($root) -and
        [IO.Path]::GetDirectoryName($root) -ieq $public -and
        [IO.Path]::GetFileName($root) -cmatch '^viewtv-svc-probe-[a-f0-9]{32}$' -and
        [IO.File]::Exists($marker) -and
        [IO.File]::ReadAllText($marker) -ceq "VIEWTV_SVC_PROBE_TEST_ONLY_V1`n") {
        try { [IO.Directory]::Delete($root,$true) } catch {
            Write-Output 'SANDBOX_TEMP_PENDIENTE_REVISION'
        }
    }
}
