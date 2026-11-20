# Only Windows temporary GUID sandbox. No persistent service or real media.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$broker=Join-Path $PSScriptRoot 'viewtv_windows_pipe_broker_sandbox.ps1'
. $broker
$temp=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
$journal=Join-Path $temp ('viewtv-pipe-broker-'+[Guid]::NewGuid().ToString('N'))
$marker=Join-Path $journal '.viewtv-pipe-only'
$markerValue='VIEWTV_PIPE_BROKER_TEST_ONLY_V1'+[char]10
$key=$null
$checks=[ordered]@{}
$running=@()

function Run-StalledClient([string]$Scenario) {
    $pipeName='viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')
    $server=Start-Job -ArgumentList $broker,$pipeName,$journal,$key -ScriptBlock {
        param($program,$name,$root,$keyPath)
        & $program -Mode Server -PipeName $name -JournalRoot $root -KeyPath $keyPath -AcceptTimeoutMs 1400 -ReadTimeoutMs 1200
    }
    $script:running+= $server
    $client=$null
    try {
        if($Scenario -ne 'no_connection') {
            $client=[IO.Pipes.NamedPipeClientStream]::new(
                '.',$pipeName,[IO.Pipes.PipeDirection]::InOut)
            $client.Connect(3000)
            $writer=[IO.BinaryWriter]::new($client,[Text.UTF8Encoding]::new($false),$true)
            try {
                switch ($Scenario) {
                    'connected_no_bytes' {}
                    'partial_challenge' {$writer.Write([byte[]](1,2,3))}
                    'challenge_only' {
                        $writer.Write((New-ViewtvBrokerTestChallenge))
                    }
                    'partial_length' {
                        $writer.Write((New-ViewtvBrokerTestChallenge))
                        $writer.Write([byte[]](1,0))
                    }
                    'short_body' {
                        $writer.Write((New-ViewtvBrokerTestChallenge))
                        $writer.Write([int]200)
                        $writer.Write([byte[]](1,2,3))
                    }
                    default { throw 'Caso de bloqueo no reconocido.' }
                }
                $writer.Flush()
                if($server.State -ne 'Running') {
                    throw 'El broker terminó antes de evaluar la conexión.'
                }
                # Keep socket open: simulate an uncooperative peer.
                $null=$server|Wait-Job -Timeout 6
                if($server.State -ne 'Completed') {
                    throw 'El broker quedó retenido por el cliente inactivo.'
                }
            } finally {$writer.Dispose()}
        } else {
            $null=$server|Wait-Job -Timeout 6
            if($server.State -ne 'Completed') {
                throw 'El broker no agotó la espera de conexión.'
            }
        }
        $null=$server|Receive-Job -ErrorAction Stop
        $checks[$Scenario]='termina_sin_reserva'
        if(@(Get-ChildItem -LiteralPath $journal -Filter '.viewtv-nonce-*.json').Count -ne 0){
            throw 'El broker reservó un nonce de un cliente incompleto.'
        }
    } finally {
        if($client){$client.Dispose()}
        if($server.State -eq 'Running'){$null=$server|Stop-Job}
        $server|Remove-Job -Force
    }
}
try {
    if([IO.Directory]::Exists($journal)){throw 'Raíz GUID ya existente.'}
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
    [IO.File]::WriteAllText($marker,$markerValue)
    $key=New-ViewtvTestKey
    foreach($scenario in @(
        'no_connection','connected_no_bytes','partial_challenge',
        'challenge_only','partial_length','short_body'
    )){
        Run-StalledClient $scenario
    }

    # Invalid server timeout cannot silently become infinite.
    foreach($invalid in @(0,200,15001)){
        $rejected=$false
        try {
            & $broker -Mode Server -PipeName (
                'viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')
            ) -JournalRoot $journal -KeyPath $key -AcceptTimeoutMs $invalid
        } catch { $rejected=$true }
        if(-not $rejected){throw 'Un timeout de servidor inválido fue aceptado.'}
    }
    $checks['timeout_invalido']='rechazado'

    # A malicious server can accept and never reply. The client must reject
    # rather than wait indefinitely; it cannot manufacture an admission.
    $fakeName='viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')
    $fake=Start-Job -ArgumentList $fakeName -ScriptBlock {
        param($name)
        $server=[IO.Pipes.NamedPipeServerStream]::new(
            $name,[IO.Pipes.PipeDirection]::InOut,1,
            [IO.Pipes.PipeTransmissionMode]::Byte,[IO.Pipes.PipeOptions]::None)
        try {
            $server.WaitForConnection()
            Start-Sleep -Milliseconds 5500
        } finally {$server.Dispose()}
    }
    try {
        Start-Sleep -Milliseconds 250
        $rejected=$false
        $watch=[Diagnostics.Stopwatch]::StartNew()
        try {
            & $broker -Mode Client -PipeName $fakeName -KeyPath $key -EnvelopeText 'ficticio' | Out-Null
        } catch {$rejected=$true}
        if(-not $rejected -or $watch.Elapsed.TotalSeconds -gt 8){
            throw 'Un servidor sin respuesta retuvo o engañó al cliente.'
        }
        $null=$fake|Wait-Job -Timeout 9
        if($fake.State -ne 'Completed'){throw 'Servidor ficticio no terminó.'}
        $null=$fake|Receive-Job -ErrorAction Stop
        $checks['servidor_no_responde']='cliente_rechaza'
    } finally {
        if($fake.State -eq 'Running'){$null=$fake|Stop-Job}
        $fake|Remove-Job -Force
    }
    $checks | ConvertTo-Json -Compress
} finally {
    foreach($job in $running){
        if($job.State -eq 'Running'){$null=$job|Stop-Job}
        $job|Remove-Job -Force -ErrorAction SilentlyContinue
    }
    if($key -and [IO.File]::Exists($key)){
        $keyDir=[IO.Path]::GetDirectoryName($key)
        if([IO.Path]::GetDirectoryName($keyDir) -ieq $temp -and
           [IO.Path]::GetFileName($keyDir) -cmatch '^viewtv-test-key-[0-9a-f]{32}$' -and
           [IO.Path]::GetFileName($key) -ceq 'key.bin' -and
           ([IO.DirectoryInfo]::new($keyDir).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0){
            [IO.Directory]::Delete($keyDir,$true)
        }
    }
    if([IO.Directory]::Exists($journal) -and
       [IO.Path]::GetDirectoryName($journal) -ieq $temp -and
       [IO.Path]::GetFileName($journal) -cmatch '^viewtv-pipe-broker-[a-f0-9]{32}$' -and
       ([IO.DirectoryInfo]::new($journal).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
       [IO.File]::Exists($marker) -and
       [IO.File]::ReadAllText($marker) -ceq $markerValue) {
       $names=@(Get-ChildItem -LiteralPath $journal -Force | ForEach-Object Name)
       if($names.Count -eq 1 -and $names[0] -ceq '.viewtv-pipe-only'){
           [IO.File]::Delete($marker)
           [IO.Directory]::Delete($journal,$false)
       }
    }
}
