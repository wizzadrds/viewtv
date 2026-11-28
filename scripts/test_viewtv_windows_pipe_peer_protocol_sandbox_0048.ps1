# VIEWTV 0048: SID del CLIENTE verificado por RunAsClient, no por JSON.
# Pipe efimera GUID, protocolo mock y nonces volatiles; cero qBit/archivos.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not ('ViewtvPeerProtocol0048' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.IO.Pipes;
using System.Security.Principal;
using System.Text.RegularExpressions;
public sealed class ViewtvPeerProtocol0048 {
    private readonly HashSet<string> consumed = new HashSet<string>(StringComparer.Ordinal);
    private static readonly Regex Grammar = new Regex(
        @"\AVT48\|MOCK_START\|[a-f0-9]{40}\|[a-f0-9]{32}\z",
        RegexOptions.CultureInvariant);
    private readonly string expectedSid;
    private readonly string expectedHash;
    public ViewtvPeerProtocol0048(string sid, string hash) {
        if (String.IsNullOrEmpty(sid) ||
            !Regex.IsMatch(hash ?? "", @"\A[a-f0-9]{40}\z")) {
            throw new ArgumentException("Identidad o hash de ensayo invalido");
        }
        expectedSid = sid;
        expectedHash = hash;
    }
    public static bool VerifyKernelPeer(
        NamedPipeServerStream pipe, string expectedSid) {
        if (pipe == null || !pipe.IsConnected || String.IsNullOrEmpty(expectedSid))
            return false;
        string peer = null;
        pipe.RunAsClient(delegate {
            using (WindowsIdentity who = WindowsIdentity.GetCurrent(true)) {
                if (who != null && who.User != null)
                    peer = who.User.Value;
            }
        });
        return String.Equals(peer, expectedSid, StringComparison.Ordinal);
    }
    public string Process(string line, bool realPeerAuthorized) {
        if (!realPeerAuthorized) return "DENIED_IDENTITY";
        if (line == null || line.Length > 128 ||
            !Grammar.IsMatch(line)) return "DENIED_FORMAT";
        string[] fields = line.Split('|');
        if (!String.Equals(fields[2], expectedHash, StringComparison.Ordinal))
            return "DENIED_HASH";
        if (!consumed.Add(fields[3])) return "DENIED_REPLAY";
        // No action, API call, file path, torrent client or real broker here.
        return "ACCEPTED_MOCK";
    }
}
'@
}
$owner=[Security.Principal.WindowsIdentity]::GetCurrent().User
if($null -eq $owner){throw 'SID del ensayo no disponible.'}
$name='viewtv-0048-peer-'+[Guid]::NewGuid().ToString('N')
if($name -cnotmatch '^viewtv-0048-peer-[a-f0-9]{32}$') {
    throw 'Nombre IPC inesperado.'
}
$hash='a'*40
$nonce1=[Guid]::NewGuid().ToString('N')
$nonce2=[Guid]::NewGuid().ToString('N')
$nonce3=[Guid]::NewGuid().ToString('N')
if($nonce1 -ceq $nonce2 -or $nonce2 -ceq $nonce3) {
    throw 'Nonce aleatorio repetido.'
}
$security=[IO.Pipes.PipeSecurity]::new()
$security.SetAccessRuleProtection($true,$false)
$security.AddAccessRule([IO.Pipes.PipeAccessRule]::new(
    $owner,[IO.Pipes.PipeAccessRights]::FullControl,
    [Security.AccessControl.AccessControlType]::Allow))
$rules=@($security.GetAccessRules(
    $true,$false,[Security.Principal.SecurityIdentifier]))
if($rules.Count -ne 1 -or
    $rules[0].IdentityReference.Value -cne $owner.Value -or
    $rules[0].AccessControlType -ne
        [Security.AccessControl.AccessControlType]::Allow) {
    throw 'Pipe no tiene DACL con SID exclusivo.'
}
$protocol=[ViewtvPeerProtocol0048]::new($owner.Value,$hash)
$pipe=$null
$client=$null
$reader=$null
$writer=$null
try {
    $pipe=[IO.Pipes.NamedPipeServerStream]::new(
        $name,[IO.Pipes.PipeDirection]::InOut,1,
        [IO.Pipes.PipeTransmissionMode]::Byte,
        [IO.Pipes.PipeOptions]::Asynchronous,4096,4096,$security)
    $waiting=$pipe.BeginWaitForConnection($null,$null)
    $client=[IO.Pipes.NamedPipeClientStream]::new(
        '.', $name, [IO.Pipes.PipeDirection]::InOut,
        [IO.Pipes.PipeOptions]::None,
        [Security.Principal.TokenImpersonationLevel]::Impersonation)
    $client.Connect(2000)
    $pipe.EndWaitForConnection($waiting)
    $realSidOk=[ViewtvPeerProtocol0048]::VerifyKernelPeer(
        $pipe,$owner.Value)
    if(-not $realSidOk){throw 'SID real del cliente de pipe no concuerda.'}
    Write-Output 'SID_DEL_CLIENTE_OBTENIDO_POR_WIN32=PASS'

    $writer=[IO.StreamWriter]::new(
        $client,[Text.UTF8Encoding]::new($false),1024,$true)
    $reader=[IO.StreamReader]::new(
        $pipe,[Text.UTF8Encoding]::new($false),$false,1024,$true)
    $writer.NewLine=[string][char]10
    # Todas las peticiones son ficticias. La suplantacion sucede en el
    # servidor, no se utiliza la identidad que afirme el cliente.
    $frames=@(
        ('VT48|MOCK_START|'+$hash+'|'+$nonce1),
        ('VT48|MOCK_START|'+$hash+'|'+$nonce1),
        ('VT48|MOCK_START|'+$hash+'|'+$nonce2+'|SID='+$owner.Value),
        ('VT48|MOCK_START|all|'+$nonce2),
        ('VT48|MOCK_START|'+('b'*40)+'|'+$nonce2),
        ('VT48|MOCK_START|'+$hash+'|'+$nonce2),
        ('VT48|MOCK_START|'+$hash+'|'+$nonce3)
    )
    $expected=@(
        'ACCEPTED_MOCK','DENIED_REPLAY','DENIED_FORMAT',
        'DENIED_FORMAT','DENIED_HASH','ACCEPTED_MOCK',
        'ACCEPTED_MOCK'
    )
    for($i=0;$i -lt $frames.Count;$i++) {
        $writer.WriteLine($frames[$i])
        $writer.Flush()
        $received=$reader.ReadLine()
        if($null -eq $received -or $received.Length -gt 512) {
            throw 'Longitud del mensaje de pipe invalida.'
        }
        $answer=$protocol.Process($received,$realSidOk)
        if($answer -cne $expected[$i]){
            throw 'El protocolo no rechazo o acepto lo esperado.'
        }
    }
    if($protocol.Process(
        'VT48|MOCK_START|'+$hash+'|'+[Guid]::NewGuid().ToString('N'),
        $false) -cne 'DENIED_IDENTITY') {
        throw 'Identidad de sistema ausente no se bloqueo.'
    }
    Write-Output 'SID_EN_PAYLOAD_NO_ES_AUTORIDAD=PASS'
    Write-Output 'START_ALL_Y_HASH_AJENO_DENEGADOS=PASS'
    Write-Output 'NONCE_REUTILIZADO_DENEGADO=PASS'
    Write-Output 'SID_NO_VERIFICADO_DENEGADO=PASS'
    Write-Output 'SOLO_MOCK_START_SIN_EFECTOS=PASS'
    Write-Output 'REPLAY_DURABLE_TRAS_REINICIO_INSTALADO=NO'
    Write-Output 'BROKER_SID_DISTINTO_PRODUCTIVO=NO'
    Write-Output 'QBIT_REAL_CONTACTADO=NO'
    Write-Output 'ARCHIVOS_REALES_ELIMINADOS=0'
    Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
} finally {
    if($null -ne $writer){$writer.Dispose()}
    if($null -ne $reader){$reader.Dispose()}
    if($null -ne $client){$client.Dispose()}
    if($null -ne $pipe){$pipe.Dispose()}
}
