# VIEWTV 0013: server-side lease preflight for HMAC pipe admission.
# Only WSL /tmp/viewtv-lease-gate-<GUID>/organization.sqlite3 test fixtures.
# NOT production: not atomic with claim, NTFS or qBittorrent.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Test-ViewtvBrokerSandboxLease(
    [string]$Database,[long]$DownloadId,[string]$Worker,
    [int]$Attempt,[string]$TorrentHash
) {
    if($Database -cnotmatch '^/tmp/viewtv-lease-gate-[a-f0-9]{32}/organization\.sqlite3$' -or
       $DownloadId -le 0 -or $Attempt -notin @(1,2,3) -or
       $Worker -cnotmatch '^[A-Za-z0-9_-]{1,128}$' -or
       $TorrentHash -cnotmatch '^(?:[a-f0-9]{40}|[a-f0-9]{64})$'){
        return $false
    }
    $repo='/home/viewtv/projects/viewtv-broker-0013-20261119'
    $python='/home/viewtv/projects/viewtv/backend/.venv/bin/python'
    $envAssignment='PYTHONPATH='+$repo+'/backend:'+$repo
    $arguments=@('--distribution','Ubuntu-24.04','--exec','/usr/bin/env',
        $envAssignment,$python,'-m','worker.organization_lease_gate_cli_sandbox',
        '--database',$Database,'--download-id',[string]$DownloadId,
        '--worker-id',$Worker,'--attempt',[string]$Attempt,
        '--torrent-hash',$TorrentHash)
    try {
        # Arguments passed separately, never interpolated into a shell.
        # Database is chosen by the test server, not the pipe request.
        $output=@(& wsl.exe @arguments 2>$null)
        if($LASTEXITCODE -ne 0 -or $output.Count -ne 1){return $false}
        $decision=$output[0]|ConvertFrom-Json
        $properties=@($decision.PSObject.Properties.Name)
        if($properties.Count -ne 2 -or
           $properties -notcontains 'allowed' -or
           $properties -notcontains 'code' -or
           $decision.allowed -isnot [bool] -or
           $decision.code -isnot [string]){
            return $false
        }
        return ($decision.allowed -eq $true -and
                $decision.code -ceq 'lease_vigente_en_consulta')
    } catch {
        return $false
    }
}
