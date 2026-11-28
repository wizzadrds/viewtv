# VIEWTV 0013: two real, disposable local SIDs; GUID SANDBOX ONLY.
# Requires explicit switch. Never touches services, production or foreign accounts.
[CmdletBinding()]
param([switch]$AuthorizeEphemeralAccounts)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'viewtv_windows_copy_acl_gate_sandbox.ps1')
. (Join-Path $PSScriptRoot 'viewtv_windows_pinned_identity_sandbox.ps1')
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
if(-not ('ViewtvHardlinkSid0037' -as [type])){
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class ViewtvHardlinkSid0037 {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true,
      EntryPoint="CreateHardLinkW")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool Make(string newName,string existingName,
                                    IntPtr security);

    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true,
      EntryPoint="CreateFileW")]
    public static extern SafeFileHandle OpenForDelete(
        string name, uint access, uint sharing, IntPtr security,
        uint creation, uint flags, IntPtr template);

    [StructLayout(LayoutKind.Sequential)]
    public struct FileDisposition {
        public uint Flags;
    }

    [DllImport("kernel32.dll", SetLastError=true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetFileInformationByHandle(
        SafeFileHandle handle,int infoClass,ref FileDisposition info,uint size);
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
    # Give the private parent only SYSTEM, Administrators and the REAL broker SID.
    $vaultAcl=[Security.AccessControl.DirectorySecurity]::new()
    $vaultAcl.SetAccessRuleProtection($true,$false)
    $vaultAcl.SetOwner($admin)
    foreach($identity in @($admin,$system,$brokerSid)){
        $vaultAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $identity,$full,([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
                             [Security.AccessControl.InheritanceFlags]::ObjectInherit),
            [Security.AccessControl.PropagationFlags]::None,$allow))
    }
    [IO.Directory]::SetAccessControl($vault,$vaultAcl)
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

    # Enroll two REAL distinct SIDs in a private, fixed-path registry.
    $registry=Join-Path $vault '.viewtv-copy-identity.json'
    $text=([ordered]@{
        version=1
        sandbox=[IO.Path]::GetFileName($root)
        copy_sid=$copySid.Value
        broker_sid=$brokerSid.Value
        expires_utc=[DateTime]::UtcNow.AddMinutes(30).ToString('o')
    } | ConvertTo-Json -Compress)
    [IO.File]::WriteAllText($registry,$text,[Text.UTF8Encoding]::new($false))
    $registryAcl=[Security.AccessControl.FileSecurity]::new()
    $registryAcl.SetAccessRuleProtection($true,$false)
    $registryAcl.SetOwner($admin)
    foreach($identity in @($admin,$system,$brokerSid)){
        $registryAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $identity,$full,$allow))
    }
    [IO.File]::SetAccessControl($registry,$registryAcl)
    Check (Is-Denied $tokenCopy {
       [IO.File]::ReadAllText($registry)
    }) 'El copiador leyó el registro privado.'
    Check (Is-Denied $tokenCopy {
       [IO.File]::WriteAllText($registry,'SID_MANIPULADO')
    }) 'El copiador modificó el registro privado.'
    $results['copia_no_lee_ni_altera_registro']='denegada'
    $resolved=As-User $tokenBroker {
        Get-ViewtvSandboxPinnedCopySid $root $vault
    }
    Check ($resolved -ceq $copySid.Value) 'Broker real no resolvió SID inscrito.'
    $results['broker_real_lee_sid_privado']='verificado'
    $stage=Join-Path $root '.viewtv-stage-1'
    [IO.Directory]::CreateDirectory($stage)|Out-Null
    Protect-TestItem $stage $true $modify $full
    $video=Join-Path $stage 'ficticio.mkv'
    As-User $tokenCopy {
      [IO.File]::WriteAllText($video,'FICHERO_SINTETICO_0013')
    } | Out-Null
    $unsafeRejected=$false
    try { $null=Assert-ViewtvSandboxHandoffCopyGate $root $stage $copySid.Value $brokerSid.Value }
    catch {$unsafeRejected=$true}
    Check $unsafeRejected 'El gate aceptó permiso de copia todavía escribible.'
    $results['gate_antes_de_sellado']='rechazado'
    # Revoke even READ from the copy SID; moved directories retain explicit DACLs.
    Protect-TestItem $video $false $null $full
    Protect-TestItem $stage $true $null $full
    # Negative: one remaining READ ACE on a single file is still a violation.
    $injectedAcl=[IO.File]::GetAccessControl($video)
    $injectedAcl.AddAccessRule(
        [Security.AccessControl.FileSystemAccessRule]::new($copySid,$read,$allow))
    [IO.File]::SetAccessControl($video,$injectedAcl)
    $readRefused=$false
    try { $null=Assert-ViewtvSandboxHandoffCopyGate $root $stage $copySid.Value $brokerSid.Value }
    catch {$readRefused=$true}
    Check $readRefused 'El gate permitió ACE de lectura del SID real.'
    $results['gate_ace_lectura_sid_real']='rechazada'
    Protect-TestItem $video $false $null $full
    $null=Assert-ViewtvSandboxHandoffCopyGate $root $stage $copySid.Value $brokerSid.Value
    $results['gate_acls_selladas']='correcto'
    Check (Is-Denied $tokenCopy {
      [IO.File]::AppendAllText($video,'INYECTADO')
    }) 'Copia pudo escribir staging sellado.'
    $results['copia_sellada']='escritura_denegada'
    $hash=(Get-FileHash $video -Algorithm SHA256).Hash
    $escrow=Join-Path $vault '.viewtv-handoff-1'
    As-User $tokenBroker {[IO.Directory]::Move($stage,$escrow)} | Out-Null
    $null=Assert-ViewtvSandboxHandoffCopyGate $root $escrow $copySid.Value $brokerSid.Value
    $results['gate_escrow_privado']='correcto'
    Check (Is-Denied $tokenCopy {
      [IO.File]::ReadAllText((Join-Path $escrow 'ficticio.mkv'))
    }) 'Copia pudo acceder al escrow tras move.'
    $results['handoff_con_broker_real']='correcto'
    $final=Join-Path $root 'ResultadoFicticio'
    As-User $tokenBroker {[IO.Directory]::Move($escrow,$final)} | Out-Null
    $null=Assert-ViewtvSandboxHandoffCopyGate $root $final $copySid.Value $brokerSid.Value
    $results['gate_destino_publicado']='correcto'
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

    # 0037: probar la diferencia entre leer bytes de un hardlink y poder
    # añadir OTRA referencia NTFS en un directorio distinto y escribible.
    # Todo bajo este mismo sandbox GUID; ninguna ruta de medios reales.
    $readOnly=Join-Path $root 'media-0037-ficticia'
    $writable=Join-Path $root 'trabajo-propio-0037'
    [IO.Directory]::CreateDirectory($readOnly)|Out-Null
    [IO.Directory]::CreateDirectory($writable)|Out-Null
    Protect-TestItem $readOnly $true $read $full
    Protect-TestItem $writable $true $modify $full
    $source=Join-Path $readOnly 'video-0037-ficticio.bin'
    [IO.File]::WriteAllText($source,'VIDEO_SINTETICO_0037')
    Protect-TestItem $source $false $read $full
    $payload=As-User $tokenCopy {[IO.File]::ReadAllText($source)}
    Check ($payload -ceq 'VIDEO_SINTETICO_0037') 'El lector no puede leer con ACL Read.'
    $blockedPath=Join-Path $readOnly 'nuevo-link-0037.bin'
    $inProtected=As-User $tokenCopy {
        [ViewtvHardlinkSid0037]::Make($blockedPath,$source,[IntPtr]::Zero)
    }
    if($inProtected) {
        throw 'El SID lector creó un enlace dentro del directorio sellado.'
    }
    $results['lector_lee_sin_escribir_en_directorio_sellado']='PASS'
    $external=Join-Path $writable 'tercer-hardlink-0037.bin'
    $canRelink=As-User $tokenCopy {
        [ViewtvHardlinkSid0037]::Make($external,$source,[IntPtr]::Zero)
    }
    if($canRelink) {
        Check ([IO.File]::Exists($external)) 'Hardlink externo no verificable.'
        Check ([IO.File]::ReadAllText($external) -ceq 'VIDEO_SINTETICO_0037') (
            'El tercer hardlink ficticio tiene contenido inesperado.'
        )
        $results['lector_crea_link_desde_directorio_propio']='POSIBLE'
        [IO.File]::Delete($external)
    } else {
        Check (-not [IO.File]::Exists($external)) (
            'La API declaró denegación pero dejó un enlace creado.'
        )
        $results['lector_crea_link_desde_directorio_propio']='DENEGADO'
    }
    $authorized=Join-Path $writable 'broker-link-0037.bin'
    $brokerCreated=As-User $tokenBroker {
        [ViewtvHardlinkSid0037]::Make($authorized,$source,[IntPtr]::Zero)
    }
    Check $brokerCreated 'El broker no pudo crear un enlace de ensayo.'
    Check ([IO.File]::ReadAllText($authorized) -ceq 'VIDEO_SINTETICO_0037') (
        'El link del broker no corresponde al origen.'
    )
    [IO.File]::Delete($authorized)
    $results['broker_distinto_sid_crea_link_de_ensayo']='PASS'

    # 0037: eliminación de DOS nombres ficticios con identidad BROKER
    # realmente distinta; mientras ambos handles estén retenidos, el
    # lector sigue sin FILE_WRITE_ATTRIBUTES sobre el File ID protegido.
    $published=Join-Path $readOnly 'publicado-0037-ficticio.bin'
    $createdPublished=As-User $tokenBroker {
        [ViewtvHardlinkSid0037]::Make($published,$source,[IntPtr]::Zero)
    }
    Check $createdPublished 'El broker no creó la pareja NTFS de sandbox.'
    Check ((As-User $tokenCopy {
        [IO.File]::ReadAllText($published)
    }) -ceq 'VIDEO_SINTETICO_0037') (
        'El lector legítimo no pudo reproducir la copia ficticia.'
    )
    $one=$null
    $two=$null
    try {
        $one=As-User $tokenBroker {
            [ViewtvHardlinkSid0037]::OpenForDelete(
                $source,[uint32]0x10080,[uint32]4,[IntPtr]::Zero,
                [uint32]3,[uint32]0,[IntPtr]::Zero
            )
        }
        Check ($null -ne $one -and -not $one.IsInvalid) (
            'Broker no adquirió handle DELETE de origen.'
        )
        $two=As-User $tokenBroker {
            [ViewtvHardlinkSid0037]::OpenForDelete(
                $published,[uint32]0x10080,[uint32]4,[IntPtr]::Zero,
                [uint32]3,[uint32]0,[IntPtr]::Zero
            )
        }
        Check ($null -ne $two -and -not $two.IsInvalid) (
            'Broker no adquirió segundo handle DELETE.'
        )
        $cannotRead=$false
        try {
            $opened=As-User $tokenCopy {
                [IO.File]::Open(
                    $published,[IO.FileMode]::Open,[IO.FileAccess]::Read,
                    [IO.FileShare]::ReadWrite
                )
            }
            if($null -ne $opened){$opened.Dispose()}
        } catch [IO.IOException] {$cannotRead=$true}
        Check $cannotRead 'Lector pudo abrir bajo la reserva Win32.'
        $foreignDuring=Join-Path $writable 'enlace-durante-0037.bin'
        $canRelinkDuring=As-User $tokenCopy {
            [ViewtvHardlinkSid0037]::Make(
                $foreignDuring,$source,[IntPtr]::Zero
            )
        }
        Check (-not $canRelinkDuring -and
               -not [IO.File]::Exists($foreignDuring)) (
            'Lector pudo crear un tercer enlace durante el commit.'
        )
        $results['lector_no_relink_durante_handles_delete']='PASS'
        $disposition=[ViewtvHardlinkSid0037+FileDisposition]::new()
        $disposition.Flags=[uint32]3
        $firstDeleted=As-User $tokenBroker {
            [ViewtvHardlinkSid0037]::SetFileInformationByHandle(
                $one,21,[ref]$disposition,[uint32]4
            )
        }
        Check $firstDeleted 'Fallo primer unlink del broker en sandbox.'
        $secondDeleted=As-User $tokenBroker {
            [ViewtvHardlinkSid0037]::SetFileInformationByHandle(
                $two,21,[ref]$disposition,[uint32]4
            )
        }
        Check $secondDeleted 'Fallo segundo unlink del broker en sandbox.'
    } finally {
        if($null -ne $two){$two.Dispose()}
        if($null -ne $one){$one.Dispose()}
    }
    Check (-not [IO.File]::Exists($source) -and
           -not [IO.File]::Exists($published)) (
        'La retirada ficticia de broker no terminó ambos nombres.'
    )
    $results['doble_unlink_broker_sid_aislado']='PASS'
    $results['ninguna_acl_ni_cuenta_productiva_modificada']='SI'
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
