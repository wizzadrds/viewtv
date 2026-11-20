# VIEWTV 0013 — server-owned GET-only fake torrent preflight (sandbox).
# Never uses real qBittorrent credentials, URLs, downloads or production.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Test-ViewtvBrokerSandboxTorrent(
    [string]$FixtureUrl,[string]$SandboxGuid,
    [long]$DownloadId,[string]$TorrentHash
) {
    if($FixtureUrl -cnotmatch '^http://127\.0\.0\.1:([0-9]{5})$' -or
       [int]$Matches[1] -lt 49152 -or [int]$Matches[1] -gt 65535 -or
       $SandboxGuid -cnotmatch '^[a-f0-9]{32}$' -or $DownloadId -le 0 -or
       $TorrentHash -cnotmatch '^(?:[a-f0-9]{40}|[a-f0-9]{64})$'){
        return $false
    }
    $repo='/home/viewtv/projects/viewtv-broker-0013-20261119'
    $python='/home/viewtv/projects/viewtv/backend/.venv/bin/python'
    $pythonPath='PYTHONPATH='+$repo+'/backend:'+$repo
    $arguments=@('--distribution','Ubuntu-24.04','--user','viewtv',
        '--exec','/usr/bin/env',$pythonPath,$python,'-m',
        'worker.organization_qbit_http_probe_cli_sandbox',
        '--base-url',$FixtureUrl,'--sandbox-guid',$SandboxGuid,
        '--download-id',[string]$DownloadId,'--torrent-hash',$TorrentHash)
    try {
        # Each argument is passed separately, NOT interpreted by a shell.
        # FixtureUrl belongs to the SERVER configuration, never the envelope.
        $lines=@(& wsl.exe @arguments 2>$null)
        if($LASTEXITCODE -ne 0 -or $lines.Count -ne 1){return $false}
        $reply=$lines[0] | ConvertFrom-Json
        $fields=@($reply.PSObject.Properties.Name)
        if($fields.Count -ne 2 -or
           $fields -notcontains 'allowed' -or
           $fields -notcontains 'code' -or
           $reply.allowed -isnot [bool] -or
           $reply.code -isnot [string]){
            return $false
        }
        return ($reply.allowed -eq $true -and
                $reply.code -ceq 'torrent_ficticio_vigente_en_consulta')
    } catch {
        return $false
    }
}
