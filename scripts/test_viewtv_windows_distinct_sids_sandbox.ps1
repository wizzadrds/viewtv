# VIEWTV 0013: two real, disposable local SIDs; GUID SANDBOX ONLY.
# Requires explicit switch. Never touches services, production or foreign accounts.
[CmdletBinding()]
param([switch]$AuthorizeEphemeralAccounts)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not $AuthorizeEphemeralAccounts){throw 'Se requiere -AuthorizeEphemeralAccounts.'}
$principal=[Security.Principal.WindowsPrincipal]::new(
  [Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
    throw 'Se requiere sesión administrativa.'
}
$public=[IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
if($public -ine 'C:\Users\Public'){throw 'Public inesperado.'}
$nonce=[Guid]::NewGuid().ToString('N')
$root=Join-Path $public ('viewtv-win-sandbox-'+$nonce)
$marker=Join-Path $root '.viewtv-win-sandbox-only'
$copyName='vtcp'+$nonce.Substring(0,11)
$brokerName='vtbr'+$nonce.Substring(11,11)
$created=@{}
$tokenCopy=[IntPtr]::Zero
$tokenBroker=[IntPtr]::Zero
$held=$null
$results=[ordered]@{}
$admin=[Security.Principal.SecurityIdentifier]::new(
 [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null)
$system=[Security.Principal.SecurityIdentifier]::new(
 [Security.Principal.WellKnownSidType]::LocalSystemSid,$null)
$operator=[Security.Principal.WindowsIdentity]::GetCurrent().User
$allow=[Security.AccessControl.AccessControlType]::Allow
$full=[Security.AccessControl.FileSystemRights]::FullControl
$read=[Security.AccessControl.FileSystemRights]::ReadAndExecute
$modify=[Security.AccessControl.FileSystemRights]::Modify

if(-not ('ViewtvDistinctSidsTest' -as [type])){
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ViewtvDistinctSidsTest {
    [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    [return:MarshalAs(UnmanagedType.Bool)]
    public static extern bool LogonUser(string name,string domain,
      string password,int kind,int provider,out IntPtr token);
    [DllImport("kernel32.dll", SetLastError=true)]
    [return:MarshalAs(UnmanagedType.Bool)]
    public static extern bool CloseHandle(IntPtr token);
}
'@
}
function New-Secret {
    $bytes=New-Object byte[] 32
    $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
    try {$rng.GetBytes($bytes)} finally {$rng.Dispose()}
    $s=[Convert]::ToBase64String($bytes)+'aA9!'
    [Array]::Clear($bytes,0,$bytes.Length)
    return $s
}
function Get-TestToken([string]$Name,[string]$Password) {
    $token=[IntPtr]::Zero
    if(-not [ViewtvDistinctSidsTest]::LogonUser(
      $Name,[Environment]::MachineName,$Password,3,0,[ref]$token)){
        throw ('LogonUser Win32='+[Runtime.InteropServices.Marshal]::GetLastWin32Error())
    }
    return $token
}
function As-User([IntPtr]$Token,[scriptblock]$Action){
    $ctx=[Security.Principal.WindowsIdentity]::Impersonate($Token)
    try {
        $p=[Security.Principal.WindowsPrincipal]::new(
          [Security.Principal.WindowsIdentity]::GetCurrent())
        if($p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
            throw 'La identidad temporal es administradora.'
        }
        return (& $Action)
    } finally {$ctx.Undo()}
}
function Check([bool]$Condition,[string]$Reason){
    if(-not $Condition){throw $Reason}
}
function Is-Denied([IntPtr]$Token,[scriptblock]$Action){
    try {$null=As-User $Token $Action; return $false}
    catch [UnauthorizedAccessException] {return $true}
}
function Protect-TestItem([string]$Path,[bool]$Directory,
  [object]$CopyAccess,[object]$BrokerAccess){
    $acl=if($Directory){[Security.AccessControl.DirectorySecurity]::new()}
         else {[Security.AccessControl.FileSecurity]::new()}
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner($admin)
    $rules=@(@($operator,$full),@($admin,$full),@($system,$full))
    if($null -ne $CopyAccess){$rules+=,@($script:copySid,$CopyAccess)}
    if($null -ne $BrokerAccess){$rules+=,@($script:brokerSid,$BrokerAccess)}
    foreach($entry in $rules){
        $sid=[Security.Principal.SecurityIdentifier]$entry[0]
        $right=[Security.AccessControl.FileSystemRights]$entry[1]
        $r=if($Directory){
            [Security.AccessControl.FileSystemAccessRule]::new(
               $sid,$right,
               ([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
                [Security.AccessControl.InheritanceFlags]::ObjectInherit),
               [Security.AccessControl.PropagationFlags]::None,$allow)
        } else {
            [Security.AccessControl.FileSystemAccessRule]::new($sid,$right,$allow)
        }
        $acl.AddAccessRule($r)
    }
    if($Directory){[IO.Directory]::SetAccessControl($Path,$acl)}
    else {[IO.File]::SetAccessControl($Path,$acl)}
}
try {
    foreach($n in @($copyName,$brokerName)){
        Check (-not (Get-LocalUser -Name $n -ErrorAction SilentlyContinue)) 'Nombre de cuenta ocupado.'
    }
    foreach($name in @($copyName,$brokerName)){
        $pass=New-Secret
        $secure=ConvertTo-SecureString $pass -AsPlainText -Force
        try {
            $account=New-LocalUser -Name $name -Password $secure -Description 'VIEWTV-0013-EPHEMERAL' -AccountNeverExpires
            $created[$name]=$account.SID.Value
        } finally {$secure.Dispose()}
        if($name -ceq $copyName){$tokenCopy=Get-TestToken $name $pass}
        else {$tokenBroker=Get-TestToken $name $pass}
        $pass=$null
    }
    $copySid=(Get-LocalUser -Name $copyName).SID
    $brokerSid=(Get-LocalUser -Name $brokerName).SID
    $observedCopy=As-User $tokenCopy {
       [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    }
    $observedBroker=As-User $tokenBroker {
       [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    }
    Check ($copySid.Value -cne $brokerSid.Value -and
           $observedCopy -ceq $copySid.Value -and
           $observedBroker -ceq $brokerSid.Value -and
           $copySid.Value -cne $operator.Value) 'SIDs o tokens incorrectos.'
    $results['dos_sids_no_administrativos']='verificado'
    Check (-not [IO.Directory]::Exists($root)) 'Sandbox GUID ya existe.'
    [IO.Directory]::CreateDirectory($root)|Out-Null
    [IO.File]::WriteAllText($marker,('VIEWTV_WINDOWS_SANDBOX_ONLY_V1'+[char]10))
    Protect-TestItem $root $true $read $full
    $vault=Join-Path $root '.viewtv-broker-handoff'
    [IO.Directory]::CreateDirectory($vault)|Out-Null
    Protect-TestItem $vault $true $null $full
    $fake=Join-Path $vault 'contenido-ficticio.txt'
    [IO.File]::WriteAllText($fake,'ESTO_NO_ES_UN_SECRETO')
    Protect-TestItem $fake $false $null $full
    Check (Is-Denied $tokenCopy {[IO.File]::ReadAllText($fake)}) 'Copia pudo leer vault.'
    Check (Is-Denied $tokenCopy {
      [IO.Directory]::CreateDirectory((Join-Path $vault 'intruso'))
    }) 'Copia pudo escribir vault.'
    Check (Is-Denied $tokenCopy {
      [IO.Directory]::CreateDirectory((Join-Path $root 'DestinoProhibido'))
    }) 'Copia pudo publicar en root.'
    Check ((As-User $tokenBroker {[IO.File]::ReadAllText($fake)}) -ceq
           'ESTO_NO_ES_UN_SECRETO') 'Broker sin lectura en vault.'
    $results['vault_y_destino_privados']='copia_denegada'
    $stage=Join-Path $root '.viewtv-stage-1'
    [IO.Directory]::CreateDirectory($stage)|Out-Null
    Protect-TestItem $stage $true $modify $full
    $video=Join-Path $stage 'ficticio.mkv'
    As-User $tokenCopy {
      [IO.File]::WriteAllText($video,'FICHERO_SINTETICO_0013')
    } | Out-Null
    # Revoke even READ from the copy SID; moved directories retain explicit DACLs.
    Protect-TestItem $video $false $null $full
    Protect-TestItem $stage $true $null $full
    Check (Is-Denied $tokenCopy {
      [IO.File]::AppendAllText($video,'INYECTADO')
    }) 'Copia pudo escribir staging sellado.'
    $results['copia_sellada']='escritura_denegada'
    $hash=(Get-FileHash $video -Algorithm SHA256).Hash
    $escrow=Join-Path $vault '.viewtv-handoff-1'
    As-User $tokenBroker {[IO.Directory]::Move($stage,$escrow)} | Out-Null
    Check (Is-Denied $tokenCopy {
      [IO.File]::ReadAllText((Join-Path $escrow 'ficticio.mkv'))
    }) 'Copia pudo acceder al escrow tras move.'
    $results['handoff_con_broker_real']='correcto'
    $final=Join-Path $root 'ResultadoFicticio'
    As-User $tokenBroker {[IO.Directory]::Move($escrow,$final)} | Out-Null
    Check ((Get-FileHash (Join-Path $final 'ficticio.mkv') -Algorithm SHA256).Hash -ceq $hash) 'Hash tras move alterado.'
    Check (Is-Denied $tokenCopy {
      [IO.File]::AppendAllText((Join-Path $final 'ficticio.mkv'),'INYECTADO')
    }) 'Copia pudo alterar resultado publicado.'
    $results['publicacion_sin_modificacion']='correcto'
    $stage2=Join-Path $root '.viewtv-stage-2'
    [IO.Directory]::CreateDirectory($stage2)|Out-Null
    Protect-TestItem $stage2 $true $modify $full
    $video2=Join-Path $stage2 'abierto.mkv'
    As-User $tokenCopy {
       [IO.File]::WriteAllText($video2,'FICTICIO_HANDLE')
    } | Out-Null
    $held=As-User $tokenCopy {
       [IO.File]::Open($video2,[IO.FileMode]::Open,
         [IO.FileAccess]::Write,
         ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    }
    Protect-TestItem $video2 $false $null $full
    Protect-TestItem $stage2 $true $null $full
    $escrow2=Join-Path $vault '.viewtv-handoff-2'
    $blocked=$false
    try {As-User $tokenBroker {
      [IO.Directory]::Move($stage2,$escrow2)
    } | Out-Null} catch [IO.IOException] {$blocked=$true}
    Check ($blocked -and [IO.Directory]::Exists($stage2) -and
           -not [IO.Directory]::Exists($escrow2)) 'Escritor abierto no bloqueó Move.'
    $results['escritor_preabierto']='bloquea_move'
    $held.Dispose()
    $held=$null
    As-User $tokenBroker {[IO.Directory]::Move($stage2,$escrow2)} | Out-Null
    $results['cierre_voluntario']='move_correcto'
    $results | ConvertTo-Json -Compress
} finally {
    if($held -ne $null){$held.Dispose()}
    foreach($tok in @($tokenCopy,$tokenBroker)){
        if($tok -ne [IntPtr]::Zero){[void][ViewtvDistinctSidsTest]::CloseHandle($tok)}
    }
    try {
        if([IO.Directory]::Exists($root) -and
           [IO.Path]::GetDirectoryName($root) -ieq $public -and
           [IO.Path]::GetFileName($root) -ceq ('viewtv-win-sandbox-'+$nonce) -and
           ([IO.DirectoryInfo]::new($root).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0 -and
           [IO.File]::Exists($marker) -and
           [IO.File]::ReadAllText($marker) -ceq ('VIEWTV_WINDOWS_SANDBOX_ONLY_V1'+[char]10)){
            foreach($f in Get-ChildItem -LiteralPath $root -Recurse -Force){
                if(($f.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
                    throw 'Enlace inesperado: no se borrará sandbox.'
                }
            }
            [IO.Directory]::Delete($root,$true)
        }
    } finally {
        foreach($name in @($created.Keys)){
            $u=Get-LocalUser -Name $name -ErrorAction SilentlyContinue
            if($u -and $u.SID.Value -ceq $created[$name] -and
               $u.Description -ceq 'VIEWTV-0013-EPHEMERAL'){
                Remove-LocalUser -Name $name
            } elseif($u) {
                throw 'Se preserva una cuenta cuya identidad cambió.'
            }
        }
    }
}
