# VIEWTV - Windows named-pipe admission & persistent nonce tests. SANDBOX ONLY.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$broker=Join-Path $PSScriptRoot 'viewtv_windows_pipe_broker_sandbox.ps1'
. $broker
$public=[IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
$temp=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
if($public -ine 'C:\Users\Public') {throw 'Solo Windows sandbox.'}
$journal=Join-Path $temp ('viewtv-pipe-broker-'+[Guid]::NewGuid().ToString('N'))
$marker=Join-Path $journal '.viewtv-pipe-only'
$mark='VIEWTV_PIPE_BROKER_TEST_ONLY_V1'+[char]10
$keyPath=$null
$otherKey=$null
$results=[ordered]@{}
function New-ValidPayload {
    return [ordered]@{
        version=1
        download_id=17
        attempt=1
        worker='worker-sandbox'
        sandbox=('viewtv-win-sandbox-'+'a'*32)
        stage='.viewtv-stage-17'
        final='Pelicula ficticia (2026)'
        manifest_sha256=('b'*64)
        nonce=[Guid]::NewGuid().ToString('N')
        expires_utc=[DateTime]::UtcNow.AddMinutes(3).ToString('o')
    }
}
function Signed($intent,[string]$key) {
    $json=$intent | ConvertTo-Json -Compress
    return New-ViewtvBrokerTestEnvelope $json $key
}
function Invoke-OneServer([string]$request) {
    $name='viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')
    $job=Start-Job -ArgumentList $broker,$name,$journal,$keyPath -ScriptBlock {
        param($script,$pipeName,$root,$secret)
        & $script -Mode Server -PipeName $pipeName -JournalRoot $root -KeyPath $secret
    }
    try {
        $response=& $broker -Mode Client -PipeName $name -EnvelopeText $request -KeyPath $keyPath
        $null=$job | Wait-Job -Timeout 12
        if($job.State -ne 'Completed') {
            $problems=($job.ChildJobs | ForEach-Object {
                if($_.JobStateInfo.Reason){$_.JobStateInfo.Reason.Message}
            }) -join '; '
            throw ('Servidor de prueba no terminó: '+$problems)
        }
        $null=$job | Receive-Job -ErrorAction Stop
        if(@($response).Count -ne 1) { throw 'Respuesta duplicada.' }
        return $response | ConvertFrom-Json
    } finally {
        if($job.State -eq 'Running'){$null=$job|Stop-Job}
        $job|Remove-Job -Force
    }
}
function Must-RejectResponse([scriptblock]$action) {
    $rejected=$false
    try { & $action | Out-Null } catch { $rejected=$true }
    if(-not $rejected){throw 'Se aceptó una respuesta de servidor no autenticada.'}
}
function Assert-State([string]$request,[string]$expected) {
    $result=Invoke-OneServer $request
    if($result.estado -cne $expected -or $result.publicacion_iniciada -ne $false){
        throw ('Estado inesperado: '+$result.estado+'; esperado '+$expected)
    }
}
try {
    if([IO.Directory]::Exists($journal)){throw 'Diario GUID preexistente.'}
    [IO.Directory]::CreateDirectory($journal)|Out-Null
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent().User
    $system=[Security.Principal.SecurityIdentifier]::new(
      [Security.Principal.WellKnownSidType]::LocalSystemSid,$null)
    $admins=[Security.Principal.SecurityIdentifier]::new(
      [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null)
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $inherit=[Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
      [Security.AccessControl.InheritanceFlags]::ObjectInherit
    foreach($sid in @($identity,$system,$admins)){
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
           $sid,[Security.AccessControl.FileSystemRights]::FullControl,
           $inherit,[Security.AccessControl.PropagationFlags]::None,
           [Security.AccessControl.AccessControlType]::Allow))
    }
    [IO.Directory]::SetAccessControl($journal,$acl)
    [IO.File]::WriteAllText($marker,$mark)
    $keyPath=New-ViewtvTestKey
    $otherKey=New-ViewtvTestKey

    # A pre-existing process must prevent the complete broker from starting,
    # not just the isolated native function. No nonce is ever reserved.
    $occupiedName='viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')
    $occupiedJob=Start-Job -ArgumentList $broker,$occupiedName -ScriptBlock {
        param($script,$name)
        . $script
        $native=New-ViewtvBrokerNativeFirstPipe $name (New-ViewtvBrokerPipeAcl)
        try {
            'READY'
            Start-Sleep -Seconds 8
        } finally {
            $native.Dispose()
        }
    }
    try {
        $clock=[Diagnostics.Stopwatch]::StartNew()
        $ready=$false
        while($clock.Elapsed.TotalSeconds -lt 7) {
            $signals=@(Receive-Job -Job $occupiedJob -Keep -ErrorAction Stop)
            if($signals -ccontains 'READY') {$ready=$true;break}
            if($occupiedJob.State -eq 'Failed'){
                throw 'No se pudo crear la instancia ocupante.'
            }
            Start-Sleep -Milliseconds 80
        }
        if(-not $ready){throw 'La instancia ocupante no pudo arrancar.'}
        $rejected=$false
        try {
            & $broker -Mode Server -PipeName $occupiedName -JournalRoot $journal -KeyPath $keyPath -AcceptTimeoutMs 700
        } catch [ComponentModel.Win32Exception] {
            $rejected=$true
        }
        if(-not $rejected) {
            throw 'El broker no rechazó una tubería de otro proceso.'
        }
        if(@(Get-ChildItem -LiteralPath $journal -Filter '.viewtv-nonce-*.json').Count -ne 0) {
            throw 'Se registró un nonce pese a una tubería previamente ocupada.'
        }
        $results['broker_primera_instancia_ocupada']='otro_proceso_rechazado'
    } finally {
        if($occupiedJob.State -eq 'Running'){$null=$occupiedJob|Stop-Job}
        $occupiedJob|Remove-Job -Force
    }

    $challenge=New-ViewtvBrokerTestChallenge
    $requestSample='solicitud de sandbox sin publicacion'
    $legitimateReply=New-ViewtvBrokerTestSignedResponse (
        'no_autorizada') $challenge $requestSample $keyPath
    $checked=Assert-ViewtvBrokerTestSignedResponse (
        $legitimateReply) $challenge $requestSample $keyPath
    if($checked.estado -cne 'no_autorizada' -or $checked.publicacion_iniciada){
        throw 'Respuesta de servidor válida no autenticada.'
    }
    $results['acuse_de_servidor_firmado']='verificado'

    $forgedStatus=$legitimateReply.Replace('no_autorizada',
        'intencion_registrada_sin_publicar')
    Must-RejectResponse {
        Assert-ViewtvBrokerTestSignedResponse (
            $forgedStatus) $challenge $requestSample $keyPath
    }
    $results['acuse_modificado']='rechazado'

    $staleChallenge=New-ViewtvBrokerTestChallenge
    Must-RejectResponse {
        Assert-ViewtvBrokerTestSignedResponse (
            $legitimateReply) $staleChallenge $requestSample $keyPath
    }
    $results['acuse_de_conexion_anterior']='rechazado'

    Must-RejectResponse {
        Assert-ViewtvBrokerTestSignedResponse (
            $legitimateReply) $challenge 'otra solicitud' $keyPath
    }
    $results['acuse_de_otra_peticion']='rechazado'

    Must-RejectResponse {
        Assert-ViewtvBrokerTestSignedResponse (
            $legitimateReply) $challenge $requestSample $otherKey
    }
    $results['acuse_con_clave_ajena']='rechazado'

    # An impostor process answers with an unsigned "success". The client
    # MUST reject it even though it connected to a correctly named pipe.
    $fakePipeName='viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')
    $fakeServer=Start-Job -ArgumentList $broker,$fakePipeName -ScriptBlock {
        param($scriptPath,$name)
        . $scriptPath
        $acl=New-ViewtvBrokerPipeAcl
        $server=[IO.Pipes.NamedPipeServerStream]::new(
            $name,[IO.Pipes.PipeDirection]::InOut,1,
            [IO.Pipes.PipeTransmissionMode]::Byte,[IO.Pipes.PipeOptions]::None,
            4096,4096,$acl)
        try {
            $server.WaitForConnection()
            $reader=[IO.BinaryReader]::new($server,[Text.Encoding]::UTF8,$true)
            $writer=[IO.BinaryWriter]::new(
                $server,[Text.UTF8Encoding]::new($false),$true)
            try {
                $nonce=$reader.ReadBytes(32)
                $len=$reader.ReadInt32()
                if($nonce.Length -ne 32 -or $len -lt 1 -or $len -gt 8192){
                    throw 'Prueba de servidor falso recibió solicitud inválida.'
                }
                $null=$reader.ReadBytes($len)
                $plain='{"estado":"intencion_registrada_sin_publicar","publicacion_iniciada":false}'
                $buffer=[Text.Encoding]::UTF8.GetBytes($plain)
                $writer.Write([int]$buffer.Length)
                $writer.Write($buffer)
                $writer.Flush()
            } finally { $reader.Dispose(); $writer.Dispose() }
        } finally { $server.Dispose() }
    }
    try {
        Start-Sleep -Milliseconds 200
        Must-RejectResponse {
            & $broker -Mode Client -PipeName $fakePipeName -KeyPath $keyPath -EnvelopeText 'peticion ficticia'
        }
        $null=$fakeServer | Wait-Job -Timeout 10
        if($fakeServer.State -ne 'Completed'){
            throw 'Proceso suplantador de prueba no terminó.'
        }
        $null=$fakeServer | Receive-Job -ErrorAction Stop
    } finally {
        if($fakeServer.State -eq 'Running'){$null=$fakeServer|Stop-Job}
        $fakeServer|Remove-Job -Force
    }
    $results['servidor_suplantador_sin_firma']='rechazado'

    $good=New-ValidPayload
    $envelope=Signed $good $keyPath
    Assert-State $envelope 'intencion_registrada_sin_publicar'
    $ledger=Join-Path $journal ('.viewtv-nonce-'+$good.nonce+'.json')
    if(-not [IO.File]::Exists($ledger)){
        throw 'No persistió registro de admisión.'
    }
    $results['solicitud_hmac_firma_valida']='registrada_sin_publicar'

    # New server process, same nonce; durable replay resistance.
    Assert-State $envelope 'replay_bloqueado'
    $results['replay_reinicio_proceso']='bloqueado'

    $tampered=$envelope.Replace('Pelicula ficticia (2026)','Pelicula distinta (2026)')
    Assert-State $tampered 'no_autorizada'
    $results['destino_manipulado']='rechazado'

    $changed=$envelope.Replace(('b'*64),('c'*64))
    Assert-State $changed 'no_autorizada'
    $results['manifiesto_manipulado']='rechazado'

    $expired=New-ValidPayload
    $expired.expires_utc=[DateTime]::UtcNow.AddSeconds(-5).ToString('o')
    Assert-State (Signed $expired $keyPath) 'no_autorizada'
    $results['caducidad']='rechazada'

    $future=New-ValidPayload
    $future.expires_utc=[DateTime]::UtcNow.AddMinutes(30).ToString('o')
    Assert-State (Signed $future $keyPath) 'no_autorizada'
    $results['vencimiento_lejano']='rechazado'

    $outside=New-ValidPayload
    $outside.final='..\Biblioteca real'
    Assert-State (Signed $outside $keyPath) 'no_autorizada'
    $results['escape_de_ruta']='rechazado'

    $reservedName=New-ValidPayload
    $reservedName.final='COM1.txt'
    Assert-State (Signed $reservedName $keyPath) 'no_autorizada'
    $results['nombre_reservado_windows']='rechazado'

    $badNonce=New-ValidPayload
    $badNonce.nonce='../../'
    Assert-State (Signed $badNonce $keyPath) 'no_autorizada'
    $results['nonce_malformado']='rechazado'

    Assert-State (Signed (New-ValidPayload) $otherKey) 'no_autorizada'
    $results['clave_ajena']='rechazada'

    Assert-State '{"payload": "no-valid-json", "signature": "no"}' 'no_autorizada'
    $results['json_malformado']='rechazado'

    $oversize='x'*10000
    Assert-State $oversize 'no_autorizada'
    $results['mensaje_excesivo']='rechazado'

    # A signed but DIFFERENT plan cannot reuse an already claimed nonce.
    $sameNonce=New-ValidPayload
    $sameNonce.nonce=$good.nonce
    $sameNonce.manifest_sha256='d'*64
    Assert-State (Signed $sameNonce $keyPath) 'replay_bloqueado'
    $results['nonce_mismo_plan_diferente']='bloqueado'

    $wrongType=New-ValidPayload
    $wrongType.download_id='17'
    Assert-State (Signed $wrongType $keyPath) 'no_autorizada'
    $results['id_como_texto']='rechazado'

    $wrongAttempt=New-ValidPayload
    $wrongAttempt.attempt='1'
    Assert-State (Signed $wrongAttempt $keyPath) 'no_autorizada'
    $results['intento_como_texto']='rechazado'

    # A fresh signed nonce CANNOT reopen the same download: global replay.
    $sameDownload=New-ValidPayload
    $sameDownload.nonce=[Guid]::NewGuid().ToString('N')
    Assert-State (Signed $sameDownload $keyPath) 'replay_bloqueado'
    $results['replay_download_id_nuevo_nonce']='bloqueado'
    $sameAttempt=New-ValidPayload
    $sameAttempt.attempt=2
    Assert-State (Signed $sameAttempt $keyPath) 'replay_bloqueado'
    $results['replay_download_id_nuevo_intento']='bloqueado'

    $otherDownloadSameNonce=New-ValidPayload
    $otherDownloadSameNonce.download_id=22
    $otherDownloadSameNonce.nonce=$good.nonce
    Assert-State (Signed $otherDownloadSameNonce $keyPath) 'replay_bloqueado'
    if([IO.File]::Exists((Join-Path $journal '.viewtv-download-22.json'))){
        throw 'Una solicitud de nonce repetido consumió otra descarga.'
    }
    $results['nonce_usado_descarga_diferente']='bloqueado_sin_reserva'

    $newGood=New-ValidPayload
    $newGood.download_id=18
    Assert-State (Signed $newGood $keyPath) 'intencion_registrada_sin_publicar'
    $results['otro_nonce_legitimo']='registrado'

    # Two separate broker/server processes race for a single signed nonce.
    $racingIntent=New-ValidPayload
    $racingIntent.download_id=19
    $racingPayload=Signed $racingIntent $keyPath
    $racingNames=@(
      ('viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')),
      ('viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N'))
    )
    $servers=@()
    $clients=@()
    try {
        foreach($name in $racingNames) {
            $servers+=Start-Job -ArgumentList $broker,$name,$journal,$keyPath -ScriptBlock {
                param($script,$pipeName,$root,$secret)
                & $script -Mode Server -PipeName $pipeName -JournalRoot $root -KeyPath $secret
            }
        }
        Start-Sleep -Milliseconds 200
        foreach($name in $racingNames) {
            $clients+=Start-Job -ArgumentList $broker,$name,$racingPayload,$keyPath -ScriptBlock {
                param($script,$pipeName,$payload,$secret)
                & $script -Mode Client -PipeName $pipeName -EnvelopeText $payload -KeyPath $secret
            }
        }
        $null=$clients|Wait-Job -Timeout 15
        $null=$servers|Wait-Job -Timeout 15
        foreach($job in @($clients)+@($servers)) {
            if($job.State -ne 'Completed') {
                throw 'Proceso de carrera de tubería no finalizó.'
            }
        }
        $statuses=@(
            foreach($job in $clients) {
                $record=Receive-Job -Job $job -ErrorAction Stop | ConvertFrom-Json
                $record.estado
            }
        )
        foreach($job in $servers){$null=$job|Receive-Job -ErrorAction Stop}
        if(@($statuses|Where-Object {$_ -ceq 'intencion_registrada_sin_publicar'}).Count -ne 1 -or
           @($statuses|Where-Object {$_ -ceq 'replay_bloqueado'}).Count -ne 1){
            throw 'Dos brokers admitieron el mismo nonce en paralelo.'
        }
        $results['dos_brokers_mismo_nonce']='una_sola_reserva'
    } finally {
        foreach($job in @($clients)+@($servers)) {
            if($job.State -eq 'Running'){$null=$job|Stop-Job}
            $job|Remove-Job -Force
        }
    }

    # Crash window: a flushed download reservation exists, but its nonce
    # record is absent. Recovery must deny all freshly signed requests.
    $interrupted=New-ValidPayload
    $interrupted.download_id=20
    $orphanPath=Join-Path $journal '.viewtv-download-20.json'
    $partial=[IO.FileStream]::new($orphanPath,[IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,[IO.FileShare]::None,4096,
        [IO.FileOptions]::WriteThrough)
    try {
        $partial.WriteByte(123)
        $partial.Flush($true)
    } finally {$partial.Dispose()}
    Assert-State (Signed $interrupted $keyPath) 'replay_bloqueado'
    if([IO.File]::Exists((Join-Path $journal ('.viewtv-nonce-'+$interrupted.nonce+'.json')))){
        throw 'Un registro incompleto de descarga produjo un nonce.'
    }
    $results['caida_entre_reservas']='rechazo_conservador'

    # Two independent brokers race with DIFFERENT nonces for the same
    # download_id. Both HMAC envelopes are valid; only one may be admitted.
    $raceA=New-ValidPayload
    $raceA.download_id=21
    $raceB=New-ValidPayload
    $raceB.download_id=21
    $raceA.nonce=[Guid]::NewGuid().ToString('N')
    $raceB.nonce=[Guid]::NewGuid().ToString('N')
    $raceMessages=@((Signed $raceA $keyPath),(Signed $raceB $keyPath))
    $separatePipeNames=@(
       ('viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')),
       ('viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N'))
    )
    $servers=@()
    $clients=@()
    try {
        foreach($name in $separatePipeNames){
            $servers+=Start-Job -ArgumentList $broker,$name,$journal,$keyPath -ScriptBlock {
                param($script,$pipeName,$root,$secret)
                & $script -Mode Server -PipeName $pipeName -JournalRoot $root -KeyPath $secret
            }
        }
        Start-Sleep -Milliseconds 200
        for($i=0;$i -lt 2;$i++){
            $clients+=Start-Job -ArgumentList $broker,$separatePipeNames[$i],$raceMessages[$i],$keyPath -ScriptBlock {
                param($script,$pipeName,$payload,$secret)
                & $script -Mode Client -PipeName $pipeName -EnvelopeText $payload -KeyPath $secret
            }
        }
        $null=$clients|Wait-Job -Timeout 15
        $null=$servers|Wait-Job -Timeout 15
        foreach($job in @($clients)+@($servers)){
            if($job.State -ne 'Completed'){
                throw 'La carrera de distintos nonces no finalizó.'
            }
        }
        $states=@(foreach($job in $clients){
            $record=Receive-Job -Job $job -ErrorAction Stop | ConvertFrom-Json
            $record.estado
        })
        foreach($job in $servers){$null=$job|Receive-Job -ErrorAction Stop}
        if(@($states|Where-Object {$_ -ceq 'intencion_registrada_sin_publicar'}).Count -ne 1 -or
           @($states|Where-Object {$_ -ceq 'replay_bloqueado'}).Count -ne 1){
            throw 'Dos brokers aceptaron la misma descarga con nonces distintos.'
        }
        $results['dos_brokers_distinto_nonce_misma_descarga']='una_sola_reserva'
    } finally {
        foreach($job in @($clients)+@($servers)){
            if($job.State -eq 'Running'){$null=$job|Stop-Job}
            $job|Remove-Job -Force
        }
    }

    $ledgers=@(Get-ChildItem -LiteralPath $journal -File -Filter '.viewtv-nonce-*.json')
    $downloads=@(Get-ChildItem -LiteralPath $journal -File -Filter '.viewtv-download-*.json')
    if($ledgers.Count -ne 4 -or $downloads.Count -ne 5){
        throw 'El diario no refleja cuatro admisiones y una reserva incompleta.'
    }
    if(([IO.FileInfo]::new($orphanPath)).Length -ne 1){
        throw 'El registro incompleto no ha quedado intacto.'
    }
    foreach($id in @(17,18,19,21)){
        $claim=Join-Path $journal ('.viewtv-download-'+$id+'.json')
        if(-not [IO.File]::Exists($claim)){
            throw 'Falta reserva durable por download_id.'
        }
        $data=([IO.File]::ReadAllText($claim)|ConvertFrom-Json)
        if([long]$data.download_id -ne $id -or
           $data.attempt -ne 1 -or
           [string]$data.nonce -cnotmatch '^[a-f0-9]{32}$'){
            throw 'Contenido de reserva por descarga incorrecto.'
        }
    }
    $results['reservas_nonce_y_descarga']=[pscustomobject]@{
        nonce=$ledgers.Count; download_id=$downloads.Count
    }
    $results | ConvertTo-Json -Compress
} finally {
    foreach($secret in @($keyPath,$otherKey)){
        if($secret -and [IO.File]::Exists($secret)){
            $directory=[IO.Path]::GetDirectoryName($secret)
            if([IO.Path]::GetDirectoryName($directory) -ieq $temp -and
               [IO.Path]::GetFileName($directory) -cmatch '^viewtv-test-key-[0-9a-f]{32}$' -and
               [IO.Path]::GetFileName($secret) -ceq 'key.bin' -and
               ([IO.DirectoryInfo]::new($directory).Attributes -band
                [IO.FileAttributes]::ReparsePoint) -eq 0){
                [IO.Directory]::Delete($directory,$true)
            }
        }
    }
    if([IO.Directory]::Exists($journal) -and
       [IO.Path]::GetDirectoryName($journal) -ieq $temp -and
       [IO.Path]::GetFileName($journal) -cmatch '^viewtv-pipe-broker-[a-f0-9]{32}$' -and
       ([IO.DirectoryInfo]::new($journal).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
       [IO.File]::Exists($marker) -and [IO.File]::ReadAllText($marker) -ceq $mark) {
        [IO.Directory]::Delete($journal,$true)
    }
}
