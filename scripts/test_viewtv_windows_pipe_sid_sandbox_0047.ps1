# VIEWTV 0047: pipe NT sandbox, ACL para un solo SID con token restringido.
# Sin cuentas nuevas, ficheros, ACL de produccion, sockets TCP ni qBit real.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not ('ViewtvRestrictedPipe0047' -as [type])){
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ViewtvRestrictedPipe0047 {
  [StructLayout(LayoutKind.Sequential)]
  public struct SidAttr { public IntPtr Sid; public uint Attr; }
  [DllImport("advapi32.dll",SetLastError=true)]
  [return:MarshalAs(UnmanagedType.Bool)]
  public static extern bool OpenProcessToken(IntPtr process,uint access,out IntPtr token);
  [DllImport("advapi32.dll",SetLastError=true)]
  [return:MarshalAs(UnmanagedType.Bool)]
  public static extern bool CreateRestrictedToken(
    IntPtr existing,uint flags,uint disableCount,
    [In] SidAttr[] disabled,uint deleteCount,IntPtr deleted,
    uint restrictedCount,IntPtr restricted,out IntPtr result);
  [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
  [return:MarshalAs(UnmanagedType.Bool)]
  public static extern bool ConvertStringSidToSid(string text,out IntPtr sid);
  [DllImport("kernel32.dll",SetLastError=true)]
  public static extern IntPtr LocalFree(IntPtr memory);
  [DllImport("kernel32.dll",SetLastError=true)]
  [return:MarshalAs(UnmanagedType.Bool)]
  public static extern bool CloseHandle(IntPtr handle);
  [DllImport("kernel32.dll")] public static extern IntPtr GetCurrentProcess();
}
'@
}
$pipe=$null
$baseToken=[IntPtr]::Zero
$restrictedToken=[IntPtr]::Zero
$sidHandle=[IntPtr]::Zero
$client=$null
$name='viewtv-0047-only-'+[Guid]::NewGuid().ToString('N')
if($name -cnotmatch '^viewtv-0047-only-[a-f0-9]{32}$'){
    throw 'Nombre de pipe no verificable.'
}
$owner=[Security.Principal.WindowsIdentity]::GetCurrent().User
if($null -eq $owner){throw 'SID de broker ficticio no verificable.'}
$exactHash='a'*40
function Check([bool]$ok,[string]$msg){
    if(-not $ok){throw $msg}
}
function Is-Allowed([string]$request){
    return ($request -ceq ('START '+$exactHash))
}
function Connect-Test([string]$request){
    $c=[IO.Pipes.NamedPipeClientStream]::new(
      '.', $name, [IO.Pipes.PipeDirection]::InOut,
      [IO.Pipes.PipeOptions]::None)
    try{
      $c.Connect(1500)
      $writer=[IO.StreamWriter]::new($c,[Text.UTF8Encoding]::new($false),1024,$true)
      try{
        $writer.NewLine=[string][char]10
        $writer.WriteLine($request)
        $writer.Flush()
      }finally{$writer.Dispose()}
      return $true
    } finally{$c.Dispose()}
}
try{
    $security=[IO.Pipes.PipeSecurity]::new()
    $security.SetAccessRuleProtection($true,$false)
    $security.AddAccessRule([IO.Pipes.PipeAccessRule]::new(
      $owner,[IO.Pipes.PipeAccessRights]::FullControl,
      [Security.AccessControl.AccessControlType]::Allow))
    $pipe=[IO.Pipes.NamedPipeServerStream]::new(
      $name,[IO.Pipes.PipeDirection]::InOut,1,
      [IO.Pipes.PipeTransmissionMode]::Byte,
      [IO.Pipes.PipeOptions]::Asynchronous,4096,4096,$security)
    $access=$pipe.GetAccessControl()
    $entries=@($access.GetAccessRules($true,$false,
      [Security.Principal.SecurityIdentifier]))
    Check ($entries.Count -eq 1) 'Pipe incluye ACEs adicionales.'
    Check ($entries[0].IdentityReference.Value -ceq $owner.Value) 'Pipe SID distinto.'
    Check ($entries[0].AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow) 'Pipe ACE no permitida.'
    Write-Output 'PIPE_ACL_UNICAMENTE_SID_DESIGNADO=PASS'

    Check ([ViewtvRestrictedPipe0047]::OpenProcessToken(
      [ViewtvRestrictedPipe0047]::GetCurrentProcess(),[uint32]0xA,
      [ref]$baseToken)) 'No se pudo leer token propio.'
    Check ([ViewtvRestrictedPipe0047]::ConvertStringSidToSid(
      $owner.Value,[ref]$sidHandle)) 'SID propio no traducible.'
    $disabled=[ViewtvRestrictedPipe0047+SidAttr]::new()
    $disabled.Sid=$sidHandle
    Check ([ViewtvRestrictedPipe0047]::CreateRestrictedToken(
      $baseToken,[uint32]1,[uint32]1,@($disabled),
      [uint32]0,[IntPtr]::Zero,[uint32]0,[IntPtr]::Zero,
      [ref]$restrictedToken)) 'No se pudo construir token restringido.'

    $accessDenied=$false
    $ctx=[Security.Principal.WindowsIdentity]::Impersonate($restrictedToken)
    try{
      try { $null=Connect-Test ('START '+$exactHash) }
      catch [UnauthorizedAccessException] {$accessDenied=$true}
      catch [IO.IOException] {
        if($_.Exception.HResult -eq -2147024891){$accessDenied=$true}
        else {throw}
      }
    }finally{$ctx.Undo()}
    Check $accessDenied 'Token sin SID habilitado pudo entrar en pipe.'
    Write-Output 'TOKEN_RESTRINGIDO_NO_CONECTA=PASS'

    $future=$pipe.BeginWaitForConnection($null,$null)
    $client=[IO.Pipes.NamedPipeClientStream]::new(
      '.', $name,[IO.Pipes.PipeDirection]::InOut,
      [IO.Pipes.PipeOptions]::None)
    $client.Connect(2000)
    $pipe.EndWaitForConnection($future)
    $writer=[IO.StreamWriter]::new(
      $client,[Text.UTF8Encoding]::new($false),1024,$true)
    $reader=[IO.StreamReader]::new(
      $pipe,[Text.UTF8Encoding]::new($false),$false,1024,$true)
    try{
      $writer.NewLine=[string][char]10
      $writer.WriteLine('START all')
      $writer.WriteLine('START '+$exactHash)
      $writer.Flush()
      $rejected=$reader.ReadLine()
      $request=$reader.ReadLine()
      Check (-not (Is-Allowed $rejected)) 'Broker mock permitio orden insegura.'
      Check (Is-Allowed $request) 'Broker mock recibio otra orden.'
      Check ($rejected -ceq 'START all') 'Fallo prueba de orden prohibida.'
    }finally{$writer.Dispose();$reader.Dispose()}
    Write-Output 'ORDEN_START_ALL_RECHAZADA_POR_POLICY=PASS'
    Write-Output 'SID_PERMITIDO_SOLO_HASH_SINTETICO=PASS'
    Write-Output 'GUI_WEBUI_QBIT_PRODUCCION_AISLADA=NO'
    Write-Output 'BROKER_PRODUCTIVO_INSTALADO=NO'
    Write-Output 'CUENTAS_LOCALES_CREADAS=0'
    Write-Output 'ACL_PRODUCTIVAS_MODIFICADAS=0'
    Write-Output 'POST_QBIT_REAL=0'
    Write-Output 'ARCHIVOS_REALES_ELIMINADOS=0'
}finally{
    if($null -ne $client){$client.Dispose()}
    if($null -ne $pipe){$pipe.Dispose()}
    if($sidHandle -ne [IntPtr]::Zero){
      $null=[ViewtvRestrictedPipe0047]::LocalFree($sidHandle)
    }
    if($restrictedToken -ne [IntPtr]::Zero){
      $null=[ViewtvRestrictedPipe0047]::CloseHandle($restrictedToken)
    }
    if($baseToken -ne [IntPtr]::Zero){
      $null=[ViewtvRestrictedPipe0047]::CloseHandle($baseToken)
    }
}
