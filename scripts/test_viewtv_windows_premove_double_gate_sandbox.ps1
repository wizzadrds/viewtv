# VIEWTV: final authorization before NTFS renames, only marked sandbox.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_final_gate_sandbox.ps1')
$brokerScript=Join-Path $PSScriptRoot 'viewtv_windows_pipe_broker_sandbox.ps1'
. $brokerScript
$publisher=Join-Path $PSScriptRoot 'viewtv_windows_publish_sandbox.ps1'
$public=[IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
if($public -ine 'C:\Users\Public'){throw 'Public root differs.'}
$root=Join-Path $public ('viewtv-win-sandbox-'+[Guid]::NewGuid().ToString('N'))
$marker=Join-Path $root '.viewtv-win-sandbox-only'
$vault=Join-Path $root '.viewtv-broker-handoff'
$gateFile=Join-Path $vault '.viewtv-final-authority.json'
$key=$null
$db=$null
$fixtureUrl=''
$fixtureJob=$null
$journal=$null
$journals=@()
$temp=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
$result=[ordered]@{}
$repo='/home/viewtv/projects/viewtv-broker-0013-20261119'
$python='/home/viewtv/projects/viewtv/backend/.venv/bin/python'
$envPath='PYTHONPATH='+$repo+'/backend:'+$repo
$current=[Security.Principal.WindowsIdentity]::GetCurrent().User
$admin=[Security.Principal.SecurityIdentifier]::new([Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null)
$system=[Security.Principal.SecurityIdentifier]::new([Security.Principal.WellKnownSidType]::LocalSystemSid,$null)
$restricted=[Security.Principal.SecurityIdentifier]::new([Security.Principal.WellKnownSidType]::RestrictedCodeSid,$null)
$fakeCopier='S-1-5-21-123456789-234567891-345678912-1234'
$allow=[Security.AccessControl.AccessControlType]::Allow
$full=[Security.AccessControl.FileSystemRights]::FullControl
$read=[Security.AccessControl.FileSystemRights]::ReadAndExecute
function Check([bool]$Ok,[string]$Message){if(-not $Ok){throw $Message}}
function Protect-Private([string]$Path,[bool]$Directory,[bool]$AllowRestricted=$false){
    $acl=if($Directory){[Security.AccessControl.DirectorySecurity]::new()}else{[Security.AccessControl.FileSecurity]::new()}
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner($admin)
    foreach($sid in @($current,$admin,$system)){
        $rule=if($Directory){
            [Security.AccessControl.FileSystemAccessRule]::new($sid,$full,([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit),[Security.AccessControl.PropagationFlags]::None,$allow)
        }else{
            [Security.AccessControl.FileSystemAccessRule]::new($sid,$full,$allow)
        }
        $acl.AddAccessRule($rule)
    }
    if($AllowRestricted){
        $rule=if($Directory){
            [Security.AccessControl.FileSystemAccessRule]::new($restricted,$read,[Security.AccessControl.InheritanceFlags]::None,[Security.AccessControl.PropagationFlags]::None,$allow)
        }else{
            [Security.AccessControl.FileSystemAccessRule]::new($restricted,$read,$allow)
        }
        $acl.AddAccessRule($rule)
    }
    if($Directory){[IO.Directory]::SetAccessControl($Path,$acl)}
    else {[IO.File]::SetAccessControl($Path,$acl)}
}
function Call-Lease([string]$Action,[string]$Database=''){
    $argsList=@('--distribution','Ubuntu-24.04','--user','viewtv','--exec','/usr/bin/env',$envPath,$python,'-m','worker.organization_lease_gate_fixture_sandbox',$Action)
    if($Database){$argsList+=@('--database',$Database)}
    $response=@(& wsl.exe @argsList 2>$null)
    if($LASTEXITCODE -ne 0 -or $response.Count -ne 1){throw ('Lease fixture '+$Action)}
    return ($response[0]|ConvertFrom-Json)
}
function Call-Http([string]$Action,[string]$Mode=''){
    $argsList=@('--distribution','Ubuntu-24.04','--user','viewtv','--exec','/usr/bin/env',$envPath,$python,'-m','worker.organization_qbit_http_fixture_server_sandbox','--action',$Action,'--guid',$script:fixtureGuid)
    if($Mode){$argsList+=@('--mode',$Mode)}
    $response=@(& wsl.exe @argsList 2>$null)
    if($LASTEXITCODE -ne 0 -or $response.Count -ne 1){throw ('HTTP fixture '+$Action)}
    return ($response[0]|ConvertFrom-Json)
}
function New-Stage([int]$Id,[string]$Final){
    $name='.viewtv-stage-'+$Id
    $folder=Join-Path $root $name
    [IO.Directory]::CreateDirectory($folder)|Out-Null
    $video=Join-Path $folder 'ficticio.mkv'
    [IO.File]::WriteAllBytes($video,[Text.Encoding]::UTF8.GetBytes(('VIDEO'+$Id)*1024))
    $approval=New-ViewtvTestApproval $root $name $Final $key
    Protect-Private $video $false $true
    Protect-Private $folder $true $true
    return [pscustomobject]@{stage=$name;folder=$folder;video=$video;final=$Final;approval=$approval}
}
function Set-Identity(){
    $data=([ordered]@{version=1;sandbox=[IO.Path]::GetFileName($root);copy_sid=$fakeCopier;broker_sid=$current.Value;expires_utc=[DateTime]::UtcNow.AddMinutes(30).ToString('o')}|ConvertTo-Json -Compress)
    $file=Join-Path $vault '.viewtv-copy-identity.json'
    [IO.File]::WriteAllText($file,$data,[Text.UTF8Encoding]::new($false))
    Protect-Private $file $false
}
function Set-GateConfig([object]$Stage,[string]$BrokerSid='', [string]$Digest=''){
    $approval=[IO.File]::ReadAllText((Join-Path $root $Stage.approval))|ConvertFrom-Json
    $hasher=[Security.Cryptography.SHA256]::Create()
    try {
        $actualDigest=[BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($approval.payload))).Replace('-','').ToLowerInvariant()
    } finally {$hasher.Dispose()}
    if($Digest){$actualDigest=$Digest}
    if(-not $BrokerSid){$BrokerSid=$current.Value}
    $record=[ordered]@{
        version=1
        sandbox=[IO.Path]::GetFileName($root)
        broker_sid=$BrokerSid
        stage=[string]$Stage.stage
        final=[string]$Stage.final
        download_id=[int]$fixture.download_id
        attempt=[int]$fixture.attempt
        worker=[string]$fixture.worker_id
        torrent_hash=[string]$fixture.torrent_hash
        approval_sha256=$actualDigest
        journal_root=$journal
        lease_database=$db
        torrent_fixture_url=$fixtureUrl
        expires_utc=[DateTime]::UtcNow.AddMinutes(30).ToString('o')
    }
    $data=$record|ConvertTo-Json -Compress
    [IO.File]::WriteAllText($gateFile,$data,[Text.UTF8Encoding]::new($false))
    Protect-Private $gateFile $false
}
function New-AdmissionJournal(){
    $path=Join-Path $temp ('viewtv-pipe-broker-'+[Guid]::NewGuid().ToString('N'))
    if([IO.Directory]::Exists($path)){throw 'Diario de prueba GUID ocupado.'}
    [IO.Directory]::CreateDirectory($path)|Out-Null
    $script:journals+=,$path
    Protect-Private $path $true
    [IO.File]::WriteAllText((Join-Path $path '.viewtv-pipe-only'),
        ('VIEWTV_PIPE_BROKER_TEST_ONLY_V1'+[char]10))
    return $path
}
function Admit-Stage([object]$Stage){
    $signed=[IO.File]::ReadAllText((Join-Path $root $Stage.approval))|ConvertFrom-Json
    $plan=$signed.payload|ConvertFrom-Json
    $hasher=[Security.Cryptography.SHA256]::Create()
    try {
        $digest=[BitConverter]::ToString($hasher.ComputeHash(
            [Text.Encoding]::UTF8.GetBytes($signed.payload))
        ).Replace('-','').ToLowerInvariant()
    } finally {$hasher.Dispose()}
    $message=([ordered]@{
        version=3
        download_id=[int]$fixture.download_id
        attempt=[int]$fixture.attempt
        worker=[string]$fixture.worker_id
        sandbox=[IO.Path]::GetFileName($root)
        stage=[string]$Stage.stage
        final=[string]$Stage.final
        manifest_sha256=$digest
        nonce=[string]$plan.nonce
        expires_utc=[DateTime]::UtcNow.AddMinutes(3).ToString('o')
        torrent_hash=[string]$fixture.torrent_hash
    }|ConvertTo-Json -Compress)
    $envelope=New-ViewtvBrokerTestEnvelope $message $key
    $pipe='viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')
    $job=Start-Job -ArgumentList $brokerScript,$pipe,$journal,$key,$db,$fixtureUrl -ScriptBlock {
        param($script,$name,$rootJournal,$secret,$database,$url)
        & $script -Mode Server -PipeName $name -JournalRoot $rootJournal -KeyPath $secret -RequireSandboxLease -LeaseDatabase $database -RequireSandboxTorrent -TorrentFixtureUrl $url
    }
    try {
        $answer=& $brokerScript -Mode Client -PipeName $pipe -EnvelopeText $envelope -KeyPath $key
        $null=$job|Wait-Job -Timeout 12
        if($job.State -ne 'Completed'){throw 'El broker v3 no terminó.'}
        $null=$job|Receive-Job -ErrorAction Stop
        $reply=$answer|ConvertFrom-Json
        Check ($reply.estado -ceq 'intencion_registrada_sin_publicar' -and
               $reply.publicacion_iniciada -eq $false) 'El broker no admitió el plan real.'
    } finally {
        if($job.State -eq 'Running'){$null=$job|Stop-Job}
        $job|Remove-Job -Force
    }
}
function Strict-Publish([object]$Stage){
    $parameters=@{SandboxRoot=$root;StageName=$Stage.stage;FinalName=$Stage.final;ApprovalName=$Stage.approval;KeyPath=$key;BrokerHandoff=$true;RequireFinalSandboxAuthority=$true}
    & $publisher @parameters
}
function Expect-StrictDenial([object]$Stage,[string]$Reason){
    $denied=$false
    try {Strict-Publish $Stage | Out-Null} catch {$denied=$true}
    $handoff=Join-Path $vault ('.viewtv-handoff-'+$Stage.stage.Substring('.viewtv-stage-'.Length))
    Check ($denied -and [IO.Directory]::Exists($Stage.folder) -and -not [IO.Directory]::Exists((Join-Path $root $Stage.final)) -and -not [IO.Directory]::Exists($handoff)) ('Una entrega insegura llegó a publicarse: '+$Reason)
}
try {
    Check (-not [IO.Directory]::Exists($root)) 'Colisión de GUID.'
    [IO.Directory]::CreateDirectory($root)|Out-Null
    Protect-Private $root $true
    [IO.File]::WriteAllText($marker,('VIEWTV_WINDOWS_SANDBOX_ONLY_V1'+[char]10))
    $key=New-ViewtvTestKey
    [IO.Directory]::CreateDirectory($vault)|Out-Null
    Protect-Private $vault $true
    Set-Identity

    $fixture=Call-Lease 'create'
    $db=[string]$fixture.database
    Check ($db -cmatch '^/tmp/viewtv-lease-gate-[a-f0-9]{32}/organization\.sqlite3$') 'SQLite no ficticia.'
    $fixtureGuid=[IO.Path]::GetFileName($root).Substring('viewtv-win-sandbox-'.Length)
    $fixtureJob=Start-Job -ArgumentList $envPath,$python,$fixtureGuid,([int]$fixture.download_id),([string]$fixture.torrent_hash) -ScriptBlock {
        param($envAssignment,$pythonExe,$guid,$id,$hash)
        & wsl.exe --distribution Ubuntu-24.04 --user viewtv --exec /usr/bin/env $envAssignment $pythonExe -m worker.organization_qbit_http_fixture_server_sandbox --action serve --guid $guid --download-id $id --torrent-hash $hash
    }
    for($i=0;$i -lt 45;$i++){
        Start-Sleep -Milliseconds 250
        try {$source=Call-Http 'status';$fixtureUrl=[string]$source.base_url;break} catch {}
    }
    Check ($fixtureUrl -cmatch '^http://127\.0\.0\.1:[0-9]{5}$') 'No hay servidor falso.'
    $journal=New-AdmissionJournal
    $first=New-Stage 1 'ResultadoUno'
    # Strict policy cannot run through historical direct publication.
    $directRejected=$false
    try {
        $params=@{SandboxRoot=$root;StageName=$first.stage;FinalName=$first.final;ApprovalName=$first.approval;KeyPath=$key;RequireFinalSandboxAuthority=$true}
        & $publisher @params | Out-Null
    } catch {$directRejected=$true}
    Check ($directRejected -and [IO.Directory]::Exists($first.folder)) 'Modo estricto eludió handoff.'
    $result['doble_gate_requiere_handoff']='rechazado'
    Expect-StrictDenial $first 'Sin autoridad final'
    $result['configuracion_final_obligatoria']='rechazada'

    Set-GateConfig $first 'S-1-5-21-123456789-234567891-345678912-9999'
    Expect-StrictDenial $first 'SID de broker ajeno'
    $result['broker_ajeno']='rechazado'

    Set-GateConfig $first '' ('a'*64)
    Expect-StrictDenial $first 'Manifest firmado no coincide'
    $result['hash_plan_no_coincide']='rechazado'

    Set-GateConfig $first
    $users=[Security.Principal.SecurityIdentifier]::new([Security.Principal.WellKnownSidType]::BuiltinUsersSid,$null)
    $configAcl=[IO.File]::GetAccessControl($gateFile)
    $configAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($users,$read,$allow))
    [IO.File]::SetAccessControl($gateFile,$configAcl)
    Expect-StrictDenial $first 'Configuración con Users'
    $result['configuracion_ace_users']='rechazada'
    Set-GateConfig $first

    Expect-StrictDenial $first 'Sin la pareja de reservas v3'
    $result['reservas_v3_obligatorias']='rechazadas'
    Admit-Stage $first
    $result['admision_real_pipe_v3']='registrada'
    $nonce=([IO.File]::ReadAllText((Join-Path $root $first.approval)) | ConvertFrom-Json).payload | ConvertFrom-Json
    $noncePath=Join-Path $journal ('.viewtv-nonce-'+[string]$nonce.nonce+'.json')
    $claimPath=Join-Path $journal ('.viewtv-download-'+[int]$fixture.download_id+'.json')
    Check ([IO.File]::Exists($claimPath) -and [IO.File]::Exists($noncePath)) 'Faltan dos reservas reales.'
    $rawClaim=[IO.File]::ReadAllText($claimPath)
    $rawNonce=[IO.File]::ReadAllText($noncePath)
    $altered=$rawClaim | ConvertFrom-Json
    $altered.worker='worker-otro'
    [IO.File]::WriteAllText($claimPath,($altered|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
    Expect-StrictDenial $first 'La reserva no coincide con el worker'
    $result['reserva_worker_falsificado']='rechazada'
    [IO.File]::WriteAllText($claimPath,$rawClaim,[Text.UTF8Encoding]::new($false))
    $alteredVersion=$rawClaim | ConvertFrom-Json
    $alteredVersion.version=2
    [IO.File]::WriteAllText($claimPath,($alteredVersion|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
    Expect-StrictDenial $first 'Reserva versión v2 no concede publicar'
    $result['reserva_v2_reutilizada']='rechazada'
    [IO.File]::WriteAllText($claimPath,$rawClaim,[Text.UTF8Encoding]::new($false))
    $alteredTorrent=$rawClaim | ConvertFrom-Json
    $alteredTorrent.torrent_hash='c'*40
    [IO.File]::WriteAllText($claimPath,($alteredTorrent|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
    Expect-StrictDenial $first 'Hash torrent distinto en la reserva'
    $result['reserva_torrent_incorrecto']='rechazada'
    [IO.File]::WriteAllText($claimPath,$rawClaim,[Text.UTF8Encoding]::new($false))
    $alteredNonce=$rawNonce | ConvertFrom-Json
    $alteredNonce.manifest_sha256='c'*64
    [IO.File]::WriteAllText($noncePath,($alteredNonce|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
    Expect-StrictDenial $first 'Nonce no corresponde al plan'
    $result['reserva_nonce_ajeno']='rechazada'
    [IO.File]::WriteAllText($noncePath,$rawNonce,[Text.UTF8Encoding]::new($false))
    [IO.File]::Move($noncePath,($noncePath+'.hidden'))
    Expect-StrictDenial $first 'No hay nonce durable'
    $result['reserva_parcial_sin_nonce']='rechazada'
    [IO.File]::Move(($noncePath+'.hidden'),$noncePath)
    $users=[Security.Principal.SecurityIdentifier]::new([Security.Principal.WellKnownSidType]::BuiltinUsersSid,$null)
    $claimAcl=[IO.File]::GetAccessControl($claimPath)
    $claimAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($users,$read,$allow))
    [IO.File]::SetAccessControl($claimPath,$claimAcl)
    Expect-StrictDenial $first 'Registro visible a Users'
    $result['reserva_ace_users']='rechazada'
    Protect-Private $claimPath $false

    $null=Call-Http 'set-mode' 'foreign_tag'
    Expect-StrictDenial $first 'Torrent pertenece a otra descarga'
    $result['torrent_ajeno_pre_move']='rechazado'
    $null=Call-Http 'set-mode' 'valid'
    Strict-Publish $first | Out-Null
    Check ([IO.File]::Exists((Join-Path $root 'ResultadoUno\ficticio.mkv')) -and -not [IO.Directory]::Exists($first.folder)) 'Entrega estricta no publicada.'
    $result['doble_gate_pre_dos_moves']='publicado_en_sandbox'

    # Inject a changed fake HTTP state AFTER a synthetic first rename.
    # This calls the same gate used in the publisher before its final move.
    $second=New-Stage 2 'ResultadoDos'
    # A distinct lab journal is required for a second synthetic admission
    # using the same fixture download_id. Real services need ONE global one.
    $journal=New-AdmissionJournal
    Set-GateConfig $second
    Admit-Stage $second
    $null=Assert-ViewtvSandboxFinalGate $root $vault $second.stage $second.final $second.approval $key
    $escrow=Join-Path $vault '.viewtv-handoff-2'
    [IO.Directory]::Move($second.folder,$escrow)
    $null=Call-Http 'set-mode' 'incomplete'
    $blocked=$false
    try {$null=Assert-ViewtvSandboxFinalGate $root $vault $second.stage $second.final $second.approval $key} catch {$blocked=$true}
    Check ($blocked -and [IO.Directory]::Exists($escrow) -and -not [IO.Directory]::Exists((Join-Path $root $second.final))) 'Torrent incompleto autorizó publicación.'
    $result['cambio_torrent_en_escrow']='denegado_para_revision'

    $null=Call-Http 'set-mode' 'valid'
    $null=Call-Lease 'expire' $db
    $blocked=$false
    try {$null=Assert-ViewtvSandboxFinalGate $root $vault $second.stage $second.final $second.approval $key} catch {$blocked=$true}
    Check ($blocked -and [IO.Directory]::Exists($escrow)) 'Lease caducado autorizó movimiento.'
    $result['lease_caducado_en_escrow']='denegado_para_revision'
    $result|ConvertTo-Json -Compress
} finally {
    if($fixtureJob -ne $null){
        try {$null=Call-Http 'stop'} catch {Write-Warning 'Apagado de HTTP ficticio no confirmado.'}
        $null=$fixtureJob|Wait-Job -Timeout 8
        if($fixtureJob.State -eq 'Running'){$null=$fixtureJob|Stop-Job}
        $fixtureJob|Remove-Job -Force
    }
    if($db){$null=Call-Lease 'cleanup' $db}
    foreach($path in $journals){
        $mark=Join-Path $path '.viewtv-pipe-only'
        if([IO.Directory]::Exists($path) -and
           [IO.Path]::GetDirectoryName($path) -ieq $temp -and
           [IO.Path]::GetFileName($path) -cmatch '^viewtv-pipe-broker-[a-f0-9]{32}$' -and
           ([IO.DirectoryInfo]::new($path).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
           [IO.File]::Exists($mark) -and
           [IO.File]::ReadAllText($mark) -ceq ('VIEWTV_PIPE_BROKER_TEST_ONLY_V1'+[char]10)){
            foreach($entry in (Get-ChildItem -LiteralPath $path -Recurse -Force)){
                if(($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
                    throw 'Diario con reparse, no se limpia.'
                }
            }
            [IO.Directory]::Delete($path,$true)
        }
    }
    if($key -and [IO.File]::Exists($key) -and [IO.Path]::GetFileName($key) -ceq 'key.bin' -and [IO.Path]::GetFileName([IO.Path]::GetDirectoryName($key)) -cmatch '^viewtv-test-key-[a-f0-9]{32}$' -and [IO.Path]::GetDirectoryName([IO.Path]::GetDirectoryName($key)) -ieq $env:TEMP){
        [IO.Directory]::Delete([IO.Path]::GetDirectoryName($key),$true)
    }
    if([IO.Directory]::Exists($root) -and [IO.Path]::GetDirectoryName($root) -ieq $public -and [IO.Path]::GetFileName($root) -cmatch '^viewtv-win-sandbox-[a-f0-9]{32}$' -and ([IO.DirectoryInfo]::new($root).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and [IO.File]::Exists($marker) -and [IO.File]::ReadAllText($marker) -ceq ('VIEWTV_WINDOWS_SANDBOX_ONLY_V1'+[char]10)){
        foreach($entry in (Get-ChildItem -LiteralPath $root -Recurse -Force)){
            if(($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Sandbox contiene enlace, no limpiar automáticamente.'}
        }
        [IO.Directory]::Delete($root,$true)
    }
}
