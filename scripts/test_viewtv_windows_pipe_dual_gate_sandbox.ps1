# VIEWTV 0013: BOTH lease + fake torrent GET gates on the real signed pipe.
# No production, NTFS publication, real torrent or service installation.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$broker=Join-Path $PSScriptRoot 'viewtv_windows_pipe_broker_sandbox.ps1'
. $broker
$repo='/home/viewtv/projects/viewtv-broker-0013-20261119'
$python='/home/viewtv/projects/viewtv/backend/.venv/bin/python'
$envAssignment='PYTHONPATH='+$repo+'/backend:'+$repo
$temp=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
$journal=Join-Path $temp ('viewtv-pipe-broker-'+[Guid]::NewGuid().ToString('N'))
$marker=Join-Path $journal '.viewtv-pipe-only'
$key=$null
$db=$null
$fixtureGuid=[Guid]::NewGuid().ToString('N')
$fixtureUrl=''
$fixtureJob=$null
$results=[ordered]@{}

function Fixture([string]$Action,[string]$Database) {
    $argsList=@('-d','Ubuntu-24.04','-e','/usr/bin/env',$envAssignment,
        $python,'-m','worker.organization_lease_gate_fixture_sandbox',$Action)
    if($Database){$argsList+=@('--database',$Database)}
    $output=@(& wsl.exe @argsList 2>$null)
    if($LASTEXITCODE -ne 0 -or $output.Count -ne 1){
        throw ('Error en SQLite sintética: '+$Action)
    }
    return ($output[0]|ConvertFrom-Json)
}
function QbitFixture([string]$Action,[string]$Mode='') {
    $argsList=@('--distribution','Ubuntu-24.04','--user','viewtv','--exec',
        '/usr/bin/env',$envAssignment,$python,'-m',
        'worker.organization_qbit_http_fixture_server_sandbox',
        '--action',$Action,'--guid',$script:fixtureGuid)
    if($Mode){$argsList+=@('--mode',$Mode)}
    $answer=@(& wsl.exe @argsList 2>$null)
    if($LASTEXITCODE -ne 0 -or $answer.Count -ne 1){
        throw ('Error en servidor qBittorrent ficticio: '+$Action)
    }
    return ($answer[0] | ConvertFrom-Json)
}
function Signed([object]$Payload){
    $json=$Payload|ConvertTo-Json -Compress
    return New-ViewtvBrokerTestEnvelope $json $key
}
function New-Payload([object]$f){
    return [ordered]@{
        version=3
        download_id=[int]$f.download_id
        attempt=[int]$f.attempt
        worker=[string]$f.worker_id
        sandbox=('viewtv-win-sandbox-'+$script:fixtureGuid)
        stage='.viewtv-stage-1'
        final='Video ficticio'
        manifest_sha256=('b'*64)
        nonce=[Guid]::NewGuid().ToString('N')
        expires_utc=[DateTime]::UtcNow.AddMinutes(3).ToString('o')
        torrent_hash=[string]$f.torrent_hash
    }
}
function Invoke-Server([string]$Request,[string]$Database,[string]$Policy='dual'){
    $pipeName='viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')
    $job=Start-Job -ArgumentList $broker,$pipeName,$journal,$key,$Database,$Policy,$script:fixtureUrl -ScriptBlock {
        param($script,$name,$root,$keyfile,$dbPath,$policy,$url)
        if($policy -ceq 'dual'){
            & $script -Mode Server -PipeName $name -JournalRoot $root -KeyPath $keyfile `
                -RequireSandboxLease -LeaseDatabase $dbPath `
                -RequireSandboxTorrent -TorrentFixtureUrl $url
        } elseif($policy -ceq 'lease'){
            & $script -Mode Server -PipeName $name -JournalRoot $root -KeyPath $keyfile `
                -RequireSandboxLease -LeaseDatabase $dbPath
        } else {
            & $script -Mode Server -PipeName $name -JournalRoot $root -KeyPath $keyfile
        }
    }
    try {
        $reply=& $broker -Mode Client -PipeName $pipeName -KeyPath $key -EnvelopeText $Request
        $null=$job | Wait-Job -Timeout 12
        if($job.State -ne 'Completed'){
            throw ('Servidor de lease sin terminar: '+$job.State)
        }
        $null=$job|Receive-Job -ErrorAction Stop
        if(@($reply).Count -ne 1){throw 'Respuesta repetida.'}
        return ($reply|ConvertFrom-Json)
    } catch {
        $clientError=$_.Exception.Message
        $null=$job|Wait-Job -Timeout 3
        $jobErrors=@()
        $null=$job|Receive-Job -ErrorAction SilentlyContinue -ErrorVariable jobErrors
        $reason=($job.ChildJobs|ForEach-Object {
            if($_.JobStateInfo.Reason){$_.JobStateInfo.Reason.Message}
        }) -join '; '
        throw ('Cliente: '+$clientError+'; servidor: '+$job.State+
               '; error: '+(@($jobErrors|ForEach-Object {$_.Exception.Message}) -join '; ')+
               '; motivo: '+$reason)
    } finally {
        if($job.State -eq 'Running'){$null=$job|Stop-Job}
        $job|Remove-Job -Force
    }
}
function Check([bool]$Ok,[string]$Message){
    if(-not $Ok){throw $Message}
}
function Expect([string]$Request,[string]$Database,[string]$State,
                [int]$ExpectedClaims,[string]$Policy='dual'){
    $reply=Invoke-Server $Request $Database $Policy
    Check ($reply.estado -ceq $State -and
           $reply.publicacion_iniciada -eq $false) ('Estado inesperado: '+$reply.estado)
    $claims=@(Get-ChildItem -LiteralPath $journal -File -Filter '.viewtv-download-*.json').Count
    $nonces=@(Get-ChildItem -LiteralPath $journal -File -Filter '.viewtv-nonce-*.json').Count
    Check ($claims -eq $ExpectedClaims -and $nonces -eq $ExpectedClaims) 'Se creó reserva sin autorización o falta reserva.'
}
try {
    Check (-not [IO.Directory]::Exists($journal)) 'Diario GUID ocupado.'
    [IO.Directory]::CreateDirectory($journal)|Out-Null
    $me=[Security.Principal.WindowsIdentity]::GetCurrent().User
    $sys=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null)
    $adm=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null)
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $inherit=[Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
             [Security.AccessControl.InheritanceFlags]::ObjectInherit
    foreach($sid in @($me,$sys,$adm)){
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $sid,[Security.AccessControl.FileSystemRights]::FullControl,
            $inherit,[Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow))
    }
    [IO.Directory]::SetAccessControl($journal,$acl)
    [IO.File]::WriteAllText($marker,('VIEWTV_PIPE_BROKER_TEST_ONLY_V1'+[char]10))
    $key=New-ViewtvTestKey
    $fixture=Fixture 'create' ''
    $db=[string]$fixture.database
    Check ($db -cmatch '^/tmp/viewtv-lease-gate-[a-f0-9]{32}/organization\.sqlite3$') 'Fixture fuera de sandbox.'
    # Separate WSL server: only synthetic GET responses on an unoccupied
    # high loopback port, NOT qBittorrent or production settings.
    $fixtureJob=Start-Job -ArgumentList $envAssignment,$python,$fixtureGuid,([int]$fixture.download_id),([string]$fixture.torrent_hash) -ScriptBlock {
        param($envPath,$pythonExe,$guid,$id,$hash)
        & wsl.exe --distribution Ubuntu-24.04 --user viewtv --exec /usr/bin/env $envPath $pythonExe -m worker.organization_qbit_http_fixture_server_sandbox --action serve --guid $guid --download-id $id --torrent-hash $hash
    }
    for($i=0;$i -lt 45;$i++){
        Start-Sleep -Milliseconds 250
        try {
            $ready=QbitFixture 'status'
            $fixtureUrl=[string]$ready.base_url
            break
        } catch {
            if($fixtureJob.State -eq 'Failed'){
                throw 'Servidor qBittorrent sintético falló antes de iniciar.'
            }
        }
    }
    Check ($fixtureUrl -cmatch '^http://127\.0\.0\.1:([0-9]{5})$' -and
           [int]$Matches[1] -ge 49152 -and [int]$Matches[1] -le 65535) 'La fuente HTTP ficticia no se inició.'
    $payload=New-Payload $fixture

    $old=New-Payload $fixture
    $old.version=1
    $old.Remove('torrent_hash')
    Expect (Signed $old) $db 'no_autorizada' 0
    $results['protocolo_v1_sin_lease']='rechazado'
    $oldV2=New-Payload $fixture
    $oldV2.version=2
    Expect (Signed $oldV2) $db 'no_autorizada' 0
    $results['protocolo_v2_sin_torrent']='rechazado'

    $wrongWorker=New-Payload $fixture
    $wrongWorker.worker='otro-worker'
    Expect (Signed $wrongWorker) $db 'no_autorizada' 0
    $results['worker_no_propietario']='rechazado'

    $wrongAttempt=New-Payload $fixture
    $wrongAttempt.attempt=2
    Expect (Signed $wrongAttempt) $db 'no_autorizada' 0
    $results['intento_no_vigente']='rechazado'

    $wrongTorrent=New-Payload $fixture
    $wrongTorrent.torrent_hash='c'*40
    Expect (Signed $wrongTorrent) $db 'no_autorizada' 0
    $results['torrent_hash_distinto_sqlite']='rechazado'

    $invalidDatabase='/tmp/viewtv-lease-gate-'+'f'*32+'/organization.sqlite3'
    Expect (Signed $payload) $invalidDatabase 'no_autorizada' 0
    $results['sqlite_no_existente']='rechazada'

    $ungated=New-Payload $fixture
    Expect (Signed $ungated) $db 'no_autorizada' 0 'lease'
    Expect (Signed $ungated) $db 'no_autorizada' 0 'legacy'
    $results['v3_sin_ambos_gates']='rechazado'

    # Neither the pipe client nor an unsigned envelope may choose the DB.
    $clientConfigRejected=$false
    try {
        & $broker -Mode Client -PipeName ('viewtv-test-pipe-'+'a'*32) -KeyPath $key -LeaseDatabase $db -EnvelopeText ''|Out-Null
    } catch {$clientConfigRejected=$true}
    Check $clientConfigRejected 'Cliente pudo elegir SQLite de autoridad.'
    $results['cliente_no_configura_fuente']='correcto'
    $clientUrlRejected=$false
    try {
        & $broker -Mode Client -PipeName ('viewtv-test-pipe-'+'a'*32) -KeyPath $key -TorrentFixtureUrl $fixtureUrl -EnvelopeText '' | Out-Null
    } catch {$clientUrlRejected=$true}
    Check $clientUrlRejected 'El cliente pudo elegir el servidor HTTP.'
    $results['cliente_no_configura_torrent']='correcto'
    $forgedSource=New-Payload $fixture
    $forgedSource['torrent_fixture_url']=$fixtureUrl
    Expect (Signed $forgedSource) $db 'no_autorizada' 0
    $results['sobre_no_selecciona_origen']='rechazado'

    $missingLeaseRejected=$false
    try {
        & $broker -Mode Server -PipeName ('viewtv-test-pipe-'+'a'*32) -JournalRoot $journal -KeyPath $key -RequireSandboxTorrent -TorrentFixtureUrl $fixtureUrl | Out-Null
    } catch {$missingLeaseRejected=$true}
    Check $missingLeaseRejected 'El servidor activó torrent sin lease.'
    $results['torrent_no_sustituye_lease']='rechazado'
    foreach($urlInsegura in @('http://127.0.0.1:08080','http://localhost:54321')){
        $inseguraRechazada=$false
        try {
            & $broker -Mode Server -PipeName ('viewtv-test-pipe-'+'a'*32) -JournalRoot $journal -KeyPath $key -RequireSandboxLease -LeaseDatabase $db -RequireSandboxTorrent -TorrentFixtureUrl $urlInsegura | Out-Null
        } catch {$inseguraRechazada=$true}
        Check $inseguraRechazada 'Broker aceptó una URL no restringida de ensayo.'
    }
    $results['servidor_rechaza_url_insegura']='correcto'

    foreach($badMode in @('bad_marker','foreign_tag','incomplete','wrong_hash','wrong_path','duplicate_files')) {
        $null=QbitFixture 'set-mode' $badMode
        $candidate=New-Payload $fixture
        Expect (Signed $candidate) $db 'no_autorizada' 0
        $results['torrent_'+$badMode]='rechazado_sin_reserva'
    }
    $null=QbitFixture 'set-mode' 'valid'
    $foreignSandbox=New-Payload $fixture
    $foreignSandbox.sandbox=('viewtv-win-sandbox-'+'f'*32)
    Expect (Signed $foreignSandbox) $db 'no_autorizada' 0
    $results['torrent_guid_ajeno']='rechazado'

    Expect (Signed $payload) $db 'intencion_registrada_sin_publicar' 1
    $results['lease_y_torrent_vigentes']='admitido_sin_publicar'
    $claim=[IO.File]::ReadAllText((Join-Path $journal ('.viewtv-download-'+$fixture.download_id+'.json')))|ConvertFrom-Json
    Check ($claim.version -eq 3 -and
           $claim.download_id -eq $fixture.download_id -and
           $claim.worker -ceq $fixture.worker_id -and
           $claim.attempt -eq $fixture.attempt -and
           $claim.torrent_hash -ceq $fixture.torrent_hash -and
           $claim.manifest_sha256 -ceq ('b'*64)) 'Reserva no ligada a identidad, torrent y manifiesto.'

    $replay=New-Payload $fixture
    Expect (Signed $replay) $db 'replay_bloqueado' 1
    $results['doble_gate_no_elude_replay']='bloqueado'
    $null=Fixture 'expire' $db
    $after=New-Payload $fixture
    Expect (Signed $after) $db 'no_autorizada' 1
    $results['lease_perdido_sin_nueva_reserva']='rechazado'

    Check (@(Get-ChildItem -LiteralPath $journal -File -Filter '.viewtv-nonce-*.json').Count -eq 1) 'Nonce duplicado.'
    $results|ConvertTo-Json -Compress
} finally {
    if($fixtureJob -ne $null){
        try { $null=QbitFixture 'stop' } catch {
            Write-Warning 'No se pudo solicitar el apagado de la fuente HTTP ficticia.'
        }
        $null=$fixtureJob | Wait-Job -Timeout 8
        if($fixtureJob.State -eq 'Running'){$null=$fixtureJob|Stop-Job}
        $fixtureJob|Remove-Job -Force
    }
    if($db){
        $null=Fixture 'cleanup' $db
    }
    if($key -and [IO.File]::Exists($key)){
        $keyFolder=[IO.Path]::GetDirectoryName($key)
        if([IO.Path]::GetDirectoryName($keyFolder) -ieq $temp -and
           [IO.Path]::GetFileName($keyFolder) -cmatch '^viewtv-test-key-[a-f0-9]{32}$' -and
           [IO.Path]::GetFileName($key) -ceq 'key.bin' -and
           ([IO.DirectoryInfo]::new($keyFolder).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0){
            [IO.Directory]::Delete($keyFolder,$true)
        }
    }
    if([IO.Directory]::Exists($journal) -and
       [IO.Path]::GetDirectoryName($journal) -ieq $temp -and
       [IO.Path]::GetFileName($journal) -cmatch '^viewtv-pipe-broker-[a-f0-9]{32}$' -and
       ([IO.DirectoryInfo]::new($journal).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
       [IO.File]::Exists($marker) -and
       [IO.File]::ReadAllText($marker) -ceq ('VIEWTV_PIPE_BROKER_TEST_ONLY_V1'+[char]10)){
        [IO.Directory]::Delete($journal,$true)
    }
}
