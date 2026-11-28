# VIEWTV 0049: intención durable de nonce para el IPC ficticio de 0048.
# Solo TEMP GUID, sin argumentos de ruta, sin broker ni qBit productivo.
[CmdletBinding()]
param(
    [ValidateSet('Test','CrashA','ReplayA','DifferentA','ReserveB',
                 'ReplayB','RaceC','CorruptD')][string]$Mode='Test',
    [ValidatePattern('^[a-f0-9]{32}$')][string]$RunId=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not ('ViewtvKillNonce0049' -as [type])){
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ViewtvKillNonce0049 {
 [DllImport("kernel32.dll")] public static extern IntPtr GetCurrentProcess();
 [DllImport("kernel32.dll",SetLastError=true)]
 [return:MarshalAs(UnmanagedType.Bool)]
 public static extern bool TerminateProcess(IntPtr process,uint exitCode);
}
'@
}
if($Mode -ceq 'Test'){
    if($RunId){throw 'Test no acepta identificador externo.'}
    $RunId=[Guid]::NewGuid().ToString('N')
}elseif(-not $RunId){throw 'Solo un hijo con RunId validado.'}
$temp=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$root=[IO.Path]::Combine($temp,'viewtv-0049-ficticio-'+$RunId)
if(-not $root.StartsWith($temp+'\',
    [StringComparison]::OrdinalIgnoreCase) -or
    [IO.Path]::GetFileName($root) -cnotmatch
    '^viewtv-0049-ficticio-[a-f0-9]{32}$'){
    throw 'Raiz del sandbox no verificable.'
}
$marker=[IO.Path]::Combine($root,'marcador-0049.txt')
$markValue='VIEWTV_0049_SOLO_FICTICIO_'+$RunId
$hash='a'*40
$otherHash='b'*40
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
if($null -eq $sid){throw 'Identidad Windows de ensayo ausente.'}
function Digest([string]$Value){
    $sha=[Security.Cryptography.SHA256]::Create()
    try{
        $bytes=[Text.Encoding]::UTF8.GetBytes($Value)
        return [BitConverter]::ToString($sha.ComputeHash($bytes)).
          Replace('-','').ToLowerInvariant()
    }finally{$sha.Dispose()}
}
$peerDigest=Digest $sid.Value
$nonce=@{
    A=$RunId
    B=(Digest ('B_'+$RunId)).Substring(0,32)
    C=(Digest ('C_'+$RunId)).Substring(0,32)
    D=(Digest ('D_'+$RunId)).Substring(0,32)
}
if(@($nonce.Values|Select-Object -Unique).Count -ne 4){
    throw 'Colision de nonces ficticios.'
}
$paths=@{}
foreach($key in @('A','B','C','D')){
    $paths[$key]=[IO.Path]::Combine(
        $root,'intencion-'+$nonce[$key]+'.txt')
}
$allowed=@($marker)+@($paths.Values)
function Write-Durable([string]$Path,[string]$Content) {
    $bytes=[Text.Encoding]::ASCII.GetBytes($Content)
    $stream=[IO.FileStream]::new(
        $Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,
        [IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough)
    try{
        $stream.Write($bytes,0,$bytes.Length)
        $stream.Flush($true)
    }finally{$stream.Dispose()}
}
function Assert-Root {
    $parent=[IO.DirectoryInfo]::new($temp)
    $dir=[IO.DirectoryInfo]::new($root)
    if(-not $parent.Exists -or -not $dir.Exists -or
       ($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
       ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
        throw 'Directorio temporal redirigido o inexistente.'
    }
    $info=[IO.FileInfo]::new($marker)
    if(-not $info.Exists -or $info.Length -gt 100 -or
       ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
       [IO.File]::ReadAllText($marker) -cne $markValue){
        throw 'Marca de sandbox incorrecta.'
    }
    foreach($entry in [IO.Directory]::GetFileSystemEntries($root)){
        $item=[IO.FileInfo]::new($entry)
        if($entry -cnotin $allowed -or -not $item.Exists -or
           ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
            throw 'Entrada desconocida o reparse point en sandbox.'
        }
    }
}
function Reserve([string]$Which,[string]$Hash){
    if($Which -cnotin @('A','B','C','D') -or
       $Hash -cnotmatch '^[a-f0-9]{40}$'){
        throw 'Solo comandos ficticios para un hash concreto.'
    }
    Assert-Root
    $path=$paths[$Which]
    $record='VT49|MOCK_START|'+$Hash+'|'+$nonce[$Which]+'|'+$peerDigest
    try{
        # CREATE_NEW + WriteThrough + Flush(true) preceden toda acción mock.
        Write-Durable $path $record
        return 'RESERVADO_MOCK'
    }catch [IO.IOException]{
        if(-not [IO.File]::Exists($path)){throw}
        Assert-Root
        $file=[IO.FileInfo]::new($path)
        if($file.Length -ne $record.Length){
            return 'DENEGADO_INTEGRIDAD'
        }
        $actual=[IO.File]::ReadAllText($path)
        if($actual -cne $record){
            return 'DENEGADO_INTEGRIDAD'
        }
        return 'DENEGADO_REPLAY'
    }
}
function Child([string]$Action) {
    if($Action -cnotin @('CrashA','ReplayA','DifferentA','ReserveB',
        'ReplayB','RaceC','CorruptD')){
        throw 'Modo de hijo no autorizado.'
    }
    $psi=[Diagnostics.ProcessStartInfo]::new()
    $psi.FileName=[IO.Path]::Combine($PSHOME,'powershell.exe')
    $psi.Arguments='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+
        $PSCommandPath+'" -Mode '+$Action+' -RunId '+$RunId
    $psi.UseShellExecute=$false
    $psi.CreateNoWindow=$true
    $psi.RedirectStandardOutput=$true
    $psi.RedirectStandardError=$true
    $proc=[Diagnostics.Process]::Start($psi)
    try{
        if(-not $proc.WaitForExit(30000)){
            $proc.Kill()
            throw 'Timeout del ensayo de nonce.'
        }
        return @{code=$proc.ExitCode;out=$proc.StandardOutput.ReadToEnd().Trim()}
    }finally{$proc.Dispose()}
}
if($Mode -ceq 'Test'){
    if([IO.Directory]::Exists($root) -or [IO.File]::Exists($root)){
        throw 'GUID de ensayo ocupado.'
    }
    [IO.Directory]::CreateDirectory($root)|Out-Null
    Write-Durable $marker $markValue
    Assert-Root
    $killed=Child 'CrashA'
    if($killed.code -eq 0 -or $killed.out){
        throw 'No se produjo la muerte abrupta del proceso.'
    }
    Assert-Root
    $file=[IO.FileInfo]::new($paths.A)
    if(-not $file.Exists -or $file.Length -lt 100){
        throw 'Crash antes de persistir el nonce.'
    }
    Write-Output 'MUERTE_REAL_TRAS_INTENCION_DURABLE=PASS'

    $again=Child 'ReplayA'
    if($again.code -ne 0 -or $again.out -cne 'DENEGADO_REPLAY'){
        throw 'Reinicio permitió nonce ya consumido.'
    }
    Write-Output 'REPLAY_TRAS_REINICIO_DENEGADO=PASS'
    $different=Child 'DifferentA'
    if($different.code -ne 0 -or
       $different.out -cne 'DENEGADO_INTEGRIDAD'){
        throw 'Se aceptó reusar nonce para otro hash.'
    }
    Write-Output 'NONCE_OTRO_HASH_RECHAZADO=PASS'

    $first=Child 'ReserveB'
    $second=Child 'ReplayB'
    if($first.code -ne 0 -or $first.out -cne 'RESERVADO_MOCK' -or
       $second.code -ne 0 -or $second.out -cne 'DENEGADO_REPLAY'){
        throw 'Nueva reserva/repetición de segundo nonce incorrecta.'
    }
    Write-Output 'OTRO_NONCE_INDEPENDIENTE_Y_UNICO=PASS'

    $procs=@()
    try{
        foreach($n in 1..4){
            $psi=[Diagnostics.ProcessStartInfo]::new()
            $psi.FileName=[IO.Path]::Combine($PSHOME,'powershell.exe')
            $psi.Arguments='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+
                $PSCommandPath+'" -Mode RaceC -RunId '+$RunId
            $psi.UseShellExecute=$false
            $psi.CreateNoWindow=$true
            $psi.RedirectStandardOutput=$true
            $psi.RedirectStandardError=$true
            $procs+=,[Diagnostics.Process]::Start($psi)
        }
        $responses=@()
        foreach($proc in $procs){
            if(-not $proc.WaitForExit(30000)){
                $proc.Kill()
                throw 'Timeout de carrera de nonce.'
            }
            if($proc.ExitCode -ne 0){
                throw 'Carrera de nonce terminó con error.'
            }
            $responses+=,$proc.StandardOutput.ReadToEnd().Trim()
        }
        # Los perdedores pueden leer una fila aún abierta y verla
        # incompleta. Ambos resultados deniegan el inicio; nunca son
        # una segunda reserva. Al terminar TODOS, corroborar el diario.
        $won=@($responses|Where-Object {$_ -ceq 'RESERVADO_MOCK'}).Count
        $blocked=@($responses|Where-Object {
            $_ -ceq 'DENEGADO_REPLAY' -or
            $_ -ceq 'DENEGADO_INTEGRIDAD'
        }).Count
        if($won -ne 1 -or $blocked -ne 3){
            throw 'CREATE_NEW aceptó más de una reserva de carrera.'
        }
        $canonical='VT49|MOCK_START|'+$hash+'|'+$nonce.C+'|'+$peerDigest
        if([IO.File]::ReadAllText($paths.C) -cne $canonical){
            throw 'Diario final de carrera incompleto o manipulado.'
        }
    }finally{
        foreach($proc in $procs){
            if($null -ne $proc){
                if(-not $proc.HasExited){$proc.Kill()}
                $proc.Dispose()
            }
        }
    }
    Write-Output 'CUATRO_PROCESOS_UNICA_RESERVA=PASS'

    Write-Durable $paths.D 'REGISTRO_FICTICIO_CORRUPTO'
    $corrupt=Child 'CorruptD'
    if($corrupt.code -ne 0 -or
       $corrupt.out -cne 'DENEGADO_INTEGRIDAD'){
        throw 'Diario alterado no bloqueó nonce.'
    }
    Write-Output 'BITACORA_CORRUPTA_FALLA_CERRADA=PASS'

    Assert-Root
    foreach($path in @($paths.A,$paths.B,$paths.C,$paths.D,$marker)){
        [IO.File]::Delete($path)
    }
    [IO.Directory]::Delete($root,$false)
    Write-Output 'SANDBOX_GUID_LIMPIADO=SI'
    Write-Output 'BROKER_PRODUCTIVO_INSTALADO=NO'
    Write-Output 'NONCE_PRODUCTIVO_DURABLE=NO'
    Write-Output 'QBIT_REAL_CONTACTADO=NO'
    Write-Output 'ARCHIVOS_REALES_ELIMINADOS=0'
    Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
}elseif($Mode -ceq 'CrashA'){
    if((Reserve 'A' $hash) -cne 'RESERVADO_MOCK'){
        throw 'Intento de crash sin reservar.'
    }
    [ViewtvKillNonce0049]::TerminateProcess(
        [ViewtvKillNonce0049]::GetCurrentProcess(),[uint32]89)|Out-Null
    throw 'Muerte de proceso no ejecutada.'
}elseif($Mode -ceq 'ReplayA'){
    Write-Output (Reserve 'A' $hash)
}elseif($Mode -ceq 'DifferentA'){
    Write-Output (Reserve 'A' $otherHash)
}elseif($Mode -ceq 'ReserveB'){
    Write-Output (Reserve 'B' $hash)
}elseif($Mode -ceq 'ReplayB'){
    Write-Output (Reserve 'B' $hash)
}elseif($Mode -ceq 'RaceC'){
    Write-Output (Reserve 'C' $hash)
}else{
    Write-Output (Reserve 'D' $hash)
}
