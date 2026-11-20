# Windows first instance and native pipe ACL: random ephemeral pipes only.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_pipe_broker_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_pipe_first_instance_sandbox.ps1')
$results=[ordered]@{}
$acl=New-ViewtvBrokerPipeAcl
$name='viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')
$first=$null
$client=$null
try {
    $first=New-ViewtvBrokerNativeFirstPipe $name $acl
    if (-not $first.GetAccessControl().AreAccessRulesProtected) {
        throw 'La primera instancia no conserva la DACL protegida.'
    }
    $results['primera_instancia_nativa']='creada_acl_protegida'
    $secondRejected=$false
    try {
        $second=New-ViewtvBrokerNativeFirstPipe $name $acl
        $second.Dispose()
    } catch [ComponentModel.Win32Exception] {
        $secondRejected=$true
    }
    if(-not $secondRejected){throw 'Se creó una segunda primera instancia.'}
    $results['segunda_primera_instancia']='rechazada'

    $wait=$first.WaitForConnectionAsync()
    $client=[IO.Pipes.NamedPipeClientStream]::new(
        '.',$name,[IO.Pipes.PipeDirection]::InOut,
        [IO.Pipes.PipeOptions]::Asynchronous)
    $client.Connect(3000)
    if(-not $wait.Wait(3000) -or -not $first.IsConnected){
        throw 'La instancia nativa no admite una conexión real.'
    }
    $results['conexion_con_pipe_nativo']='correcta'
} finally {
    if($client){$client.Dispose()}
    if($first){$first.Dispose()}
}

# Existing first instance created by standard framework wins the name;
# native first instance MUST fail. No files or services are created.
$otherName='viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')
$fake=[IO.Pipes.NamedPipeServerStream]::new(
    $otherName,[IO.Pipes.PipeDirection]::InOut,1,
    [IO.Pipes.PipeTransmissionMode]::Byte,[IO.Pipes.PipeOptions]::Asynchronous,
    4096,4096,$acl)
try {
    $preemptRejected=$false
    try {
        $unexpected=New-ViewtvBrokerNativeFirstPipe $otherName $acl
        $unexpected.Dispose()
    } catch [ComponentModel.Win32Exception] {
        $preemptRejected=$true
    }
    if(-not $preemptRejected){throw 'El pipe nativo aceptó un nombre ya ocupado.'}
    $results['nombre_preocupado']='rechazado'
} finally {$fake.Dispose()}

# Native creation should work again once the old first instance is closed.
$recreated=New-ViewtvBrokerNativeFirstPipe $otherName $acl
try {
    $results['nombre_tras_cerrar']='reutilizable'
} finally {$recreated.Dispose()}

$results | ConvertTo-Json -Compress
