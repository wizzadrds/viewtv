# VIEWTV 0050: end-to-end REAL Win32 peer SID + durable nonce, only TEMP.
# No user-supplied paths, qBit, media, users, service or production ACL.
[CmdletBinding()]
param(
    [ValidateSet('Test','Crash','Replay','Forged','OtherHash',
                 'NoPeer','Fresh','Race','Tampered')][string]$Mode='Test',
    [ValidatePattern('^[a-f0-9]{32}$')][string]$RunId=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

if(-not ('ViewtvPeerNonce0050' -as [type])){
    Add-Type -TypeDefinition @'
using System;
using System.IO.Pipes;
using System.Security.Principal;
using System.Runtime.InteropServices;
public static class ViewtvPeerNonce0050 {
    [DllImport("kernel32.dll")]
    public static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll",SetLastError=true)]
    [return:MarshalAs(UnmanagedType.Bool)]
    public static extern bool TerminateProcess(IntPtr p,uint status);
    public static bool Verify(NamedPipeServerStream pipe,string expectedSid) {
        if (pipe == null || !pipe.IsConnected || String.IsNullOrEmpty(expectedSid))
            return false;
        string peer = null;
        pipe.RunAsClient(delegate() {
            using (WindowsIdentity identity = WindowsIdentity.GetCurrent(true)) {
                if(identity != null && identity.User != null)
                    peer = identity.User.Value;
            }
        });
        return String.Equals(peer, expectedSid, StringComparison.Ordinal);
    }
}
'@
}
if($Mode -ceq 'Test'){
    if($RunId){throw 'Test no admite RunId de usuario.'}
    $RunId=[Guid]::NewGuid().ToString('N')
}elseif(-not $RunId){throw 'Falta ID del sandbox de ensayo.'}
$temp=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$root=[IO.Path]::Combine($temp,'viewtv-0050-ficticio-'+$RunId)
if(-not $root.StartsWith($temp+'\',
    [StringComparison]::OrdinalIgnoreCase) -or
   [IO.Path]::GetFileName($root) -cnotmatch
   '^viewtv-0050-ficticio-[a-f0-9]{32}$'){
    throw 'Directorio TEMP fuera del sandbox.'
}
$marker=[IO.Path]::Combine($root,'marcador-0050.txt')
$markerText='VIEWTV_0050_SOLO_SANDBOX_'+$RunId
$hash='a'*40
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
if($null -eq $sid){throw 'SID local de ensayo ausente.'}
function Sha256([string]$value){
    $h=[Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString(
            $h.ComputeHash([Text.Encoding]::UTF8.GetBytes($value))
        ).Replace('-','').ToLowerInvariant()
    }finally{$h.Dispose()}
}
$peerDigest=Sha256 $sid.Value
$nonces=@{
    crash=$RunId
    fresh=(Sha256 ('fresh_'+$RunId)).Substring(0,32)
    race=(Sha256 ('race_'+$RunId)).Substring(0,32)
}
if(@($nonces.Values|Select-Object -Unique).Count -ne 3){
    throw 'Nonces internos no únicos.'
}
$journal=@{}
foreach($value in $nonces.Values){
    $journal[$value]=[IO.Path]::Combine($root,'intencion-'+$value+'.txt')
}
$allowed=@($marker)+@($journal.Values)
function Write-Once([string]$path,[string]$value){
    $bytes=[Text.Encoding]::ASCII.GetBytes($value)
    $file=[IO.FileStream]::new(
        $path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,
        [IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough)
    try{
        $file.Write($bytes,0,$bytes.Length)
        $file.Flush($true)
    }finally{$file.Dispose()}
}
function Check-Root {
    $parent=[IO.DirectoryInfo]::new($temp)
    $dir=[IO.DirectoryInfo]::new($root)
    if(-not $parent.Exists -or -not $dir.Exists -or
       ($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
       ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
        throw 'TEMP no íntegro.'
    }
    $info=[IO.FileInfo]::new($marker)
    if(-not $info.Exists -or
       ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
       $info.Length -gt 100 -or
       [IO.File]::ReadAllText($marker) -cne $markerText){
        throw 'Marcador de TEMP incorrecto.'
    }
    foreach($entry in [IO.Directory]::GetFileSystemEntries($root)){
        $file=[IO.FileInfo]::new($entry)
        if($entry -cnotin $allowed -or -not $file.Exists -or
           ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
            throw 'Entrada no permitida en directorio ficticio.'
        }
    }
}
function Reserve([string]$nonce,[string]$torrentHash){
    Check-Root
    if(-not $journal.ContainsKey($nonce)){
        return 'DENIED_FORMAT'
    }
    $record='VT50|MOCK_START|'+$torrentHash+'|'+$nonce+'|'+$peerDigest
    $file=$journal[$nonce]
    try{
        Write-Once $file $record
        return 'ACCEPTED_MOCK'
    }catch [IO.IOException]{
        if(-not [IO.File]::Exists($file)){throw}
        Check-Root
        try{
            # Un cliente concurrente puede observar el registro mientras
            # el ganador lo escribe. Cualquier error de lectura DENIEGA.
            $stored=[IO.FileInfo]::new($file)
            if($stored.Length -ne $record.Length -or
               [IO.File]::ReadAllText($file) -cne $record){
                return 'DENIED_INTEGRITY'
            }
        }catch [IO.IOException]{
            return 'DENIED_INTEGRITY'
        }catch [UnauthorizedAccessException]{
            return 'DENIED_INTEGRITY'
        }
        return 'DENIED_REPLAY'
    }
}
function Run-Pipe([string]$frame,[bool]$forceDenied){
    # Un GUID nuevo por subproceso, sin endpoints TCP ni rutas del usuario.
    $name='viewtv-0050-peer-'+[Guid]::NewGuid().ToString('N')
    $acl=[IO.Pipes.PipeSecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $acl.AddAccessRule([IO.Pipes.PipeAccessRule]::new(
        $sid,[IO.Pipes.PipeAccessRights]::FullControl,
        [Security.AccessControl.AccessControlType]::Allow))
    $rules=@($acl.GetAccessRules($true,$false,
        [Security.Principal.SecurityIdentifier]))
    if($rules.Count -ne 1 -or
       $rules[0].IdentityReference.Value -cne $sid.Value){
        throw 'DACL del pipe no exclusiva.'
    }
    $server=$null;$client=$null;$reader=$null;$writer=$null
    try{
        $server=[IO.Pipes.NamedPipeServerStream]::new(
            $name,[IO.Pipes.PipeDirection]::InOut,1,
            [IO.Pipes.PipeTransmissionMode]::Byte,
            [IO.Pipes.PipeOptions]::Asynchronous,4096,4096,$acl)
        $waiting=$server.BeginWaitForConnection($null,$null)
        $client=[IO.Pipes.NamedPipeClientStream]::new(
            '.',$name,[IO.Pipes.PipeDirection]::InOut,
            [IO.Pipes.PipeOptions]::None,
            [Security.Principal.TokenImpersonationLevel]::Impersonation)
        $client.Connect(2000)
        $server.EndWaitForConnection($waiting)
        $writer=[IO.StreamWriter]::new(
            $client,[Text.UTF8Encoding]::new($false),1024,$true)
        $reader=[IO.StreamReader]::new(
            $server,[Text.UTF8Encoding]::new($false),$false,1024,$true)
        $writer.NewLine=[string][char]10
        $writer.WriteLine($frame)
        $writer.Flush()
        $received=$reader.ReadLine()
        $allowed=[ViewtvPeerNonce0050]::Verify($server,$sid.Value)
        # forceDenied is a NEGATIVE TEST of application refusal only.
        if(-not $allowed -or $forceDenied){return 'DENIED_IDENTITY'}
        if($null -eq $received -or $received.Length -gt 128 -or
           $received -cnotmatch '^VT50\|MOCK_START\|[a-f0-9]{40}\|[a-f0-9]{32}$'){
            return 'DENIED_FORMAT'
        }
        $parts=$received.Split('|')
        if($parts[2] -cne $hash){return 'DENIED_HASH'}
        $out=Reserve $parts[3] $hash
        if($Mode -ceq 'Crash' -and $out -ceq 'ACCEPTED_MOCK'){
            # Real process termination AFTER durable commit, BEFORE reply.
            [ViewtvPeerNonce0050]::TerminateProcess(
                [ViewtvPeerNonce0050]::GetCurrentProcess(),[uint32]90)|Out-Null
            throw 'Proceso no murió.'
        }
        return $out
    }finally{
        if($null -ne $writer){$writer.Dispose()}
        if($null -ne $reader){$reader.Dispose()}
        if($null -ne $client){$client.Dispose()}
        if($null -ne $server){$server.Dispose()}
    }
}
function Child([string]$action){
    if($action -cnotin @('Crash','Replay','Forged','OtherHash',
        'NoPeer','Fresh','Race','Tampered')){
        throw 'Subproceso no permitido.'
    }
    $psi=[Diagnostics.ProcessStartInfo]::new()
    $psi.FileName=[IO.Path]::Combine($PSHOME,'powershell.exe')
    $psi.Arguments='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+
        $PSCommandPath+'" -Mode '+$action+' -RunId '+$RunId
    $psi.UseShellExecute=$false
    $psi.CreateNoWindow=$true
    $psi.RedirectStandardOutput=$true
    $psi.RedirectStandardError=$true
    $proc=[Diagnostics.Process]::Start($psi)
    try{
        if(-not $proc.WaitForExit(25000)){
            $proc.Kill()
            throw 'Timeout de hijo IPC/nonce.'
        }
        return @{exit=$proc.ExitCode;out=$proc.StandardOutput.ReadToEnd().Trim()}
    }finally{$proc.Dispose()}
}
if($Mode -ceq 'Test'){
    if([IO.Directory]::Exists($root) -or [IO.File]::Exists($root)){
        throw 'GUID ya ocupado.'
    }
    [IO.Directory]::CreateDirectory($root)|Out-Null
    Write-Once $marker $markerText
    Check-Root
    $crash=Child 'Crash'
    if($crash.exit -eq 0 -or $crash.out){
        throw 'El hijo no murió en ventana posterior al commit.'
    }
    $expected='VT50|MOCK_START|'+$hash+'|'+$nonces.crash+'|'+$peerDigest
    if([IO.File]::ReadAllText($journal[$nonces.crash]) -cne $expected){
        throw 'No existe intención durable tras crash.'
    }
    Write-Output 'SID_PEER_Y_COMMIT_ANTES_DE_CRASH=PASS'
    $replayed=Child 'Replay'
    if($replayed.exit -ne 0 -or $replayed.out -cne 'DENIED_REPLAY'){
        throw 'Nonce repetido aceptado después del crash.'
    }
    Write-Output 'REPLAY_EN_NUEVA_PIPE_DENEGADO=PASS'
    $forged=Child 'Forged'
    if($forged.exit -ne 0 -or $forged.out -cne 'DENIED_FORMAT'){
        throw 'Campo SID falsificado aceptado.'
    }
    Write-Output 'SID_FALSO_EN_MENSAJE_DENEGADO=PASS'
    $wrong=Child 'OtherHash'
    if($wrong.exit -ne 0 -or $wrong.out -cne 'DENIED_HASH'){
        throw 'Hash distinto aceptado.'
    }
    Write-Output 'HASH_AJENO_DENEGADO=PASS'
    $noPeer=Child 'NoPeer'
    if($noPeer.exit -ne 0 -or $noPeer.out -cne 'DENIED_IDENTITY'){
        throw 'No se rechazo una identidad no verificada.'
    }
    Write-Output 'IDENTIDAD_NO_VERIFICADA_DENEGADA=PASS'
    $fresh=Child 'Fresh'
    if($fresh.exit -ne 0 -or $fresh.out -cne 'ACCEPTED_MOCK'){
        throw 'Nonce distinto no fue aceptado en sandbox.'
    }
    Write-Output 'NONCE_NUEVO_ACEPTADO_SOLO_MOCK=PASS'
    $procs=@()
    try{
        foreach($n in 1..4){
            $psi=[Diagnostics.ProcessStartInfo]::new()
            $psi.FileName=[IO.Path]::Combine($PSHOME,'powershell.exe')
            $psi.Arguments='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+
                $PSCommandPath+'" -Mode Race -RunId '+$RunId
            $psi.UseShellExecute=$false;$psi.CreateNoWindow=$true
            $psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
            $procs+=,[Diagnostics.Process]::Start($psi)
        }
        $response=@()
        foreach($proc in $procs){
            if(-not $proc.WaitForExit(25000)){
                $proc.Kill();throw 'Timeout carrera IPC.'
            }
            if($proc.ExitCode -ne 0){throw 'Hijo de carrera falló.'}
            $response+=,$proc.StandardOutput.ReadToEnd().Trim()
        }
        $winners=@($response|Where-Object {$_ -ceq 'ACCEPTED_MOCK'}).Count
        $blocked=@($response|Where-Object {
            $_ -ceq 'DENIED_REPLAY' -or $_ -ceq 'DENIED_INTEGRITY'
        }).Count
        $canonical='VT50|MOCK_START|'+$hash+'|'+$nonces.race+'|'+$peerDigest
        if($winners -ne 1 -or $blocked -ne 3 -or
           [IO.File]::ReadAllText($journal[$nonces.race]) -cne $canonical){
            throw 'Carrera IPC admitió varias reservas o cambió el diario.'
        }
    }finally{
        foreach($proc in $procs){
            if($null -ne $proc){
                if(-not $proc.HasExited){$proc.Kill()}
                $proc.Dispose()
            }
        }
    }
    Write-Output 'CUATRO_PIPE_CLIENTS_UNICA_RESERVA=PASS'
    # Tamper ONLY a synthetic sandbox journal; no production files.
    [IO.File]::WriteAllText($journal[$nonces.crash], 'INTENCION_FALSA')
    $bad=Child 'Tampered'
    if($bad.exit -ne 0 -or $bad.out -cne 'DENIED_INTEGRITY'){
        throw 'Journal manipulado pudo rearmer nonce.'
    }
    Write-Output 'JOURNAL_MANIPULADO_FALLA_CERRADA=PASS'
    Check-Root
    foreach($path in @($journal.Values)+@($marker)){
        [IO.File]::Delete($path)
    }
    [IO.Directory]::Delete($root,$false)
    Write-Output 'SANDBOX_GUID_LIMPIADO=SI'
    Write-Output 'BROKER_PRODUCTIVO_INSTALADO=NO'
    Write-Output 'QBIT_REAL_CONTACTADO=NO'
    Write-Output 'ARCHIVOS_REALES_ELIMINADOS=0'
    Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
}else{
    Check-Root
    $targetNonce=if($Mode -ceq 'Fresh'){$nonces.fresh}
                 elseif($Mode -ceq 'Race'){$nonces.race}
                 else {$nonces.crash}
    $useHash=if($Mode -ceq 'OtherHash'){'b'*40}else{$hash}
    $frame='VT50|MOCK_START|'+$useHash+'|'+$targetNonce
    if($Mode -ceq 'Forged'){$frame+='|SID='+$sid.Value}
    $answer=Run-Pipe $frame ($Mode -ceq 'NoPeer')
    Write-Output $answer
}
