# Windows local pipe experiment only; no file creation or real service.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$name='viewtv-test-pipe-'+[Guid]::NewGuid().ToString('N')
$acl=[IO.Pipes.PipeSecurity]::new()
$acl.SetAccessRuleProtection($true,$false)
$me=[Security.Principal.WindowsIdentity]::GetCurrent().User
$acl.AddAccessRule([IO.Pipes.PipeAccessRule]::new(
  $me,[IO.Pipes.PipeAccessRights]::FullControl,
  [Security.AccessControl.AccessControlType]::Allow))
$option=[IO.Pipes.PipeOptions]0x80000
$first=$null
$second=$null
try {
    try {
        $first=[IO.Pipes.NamedPipeServerStream]::new(
            $name,[IO.Pipes.PipeDirection]::InOut,1,
            [IO.Pipes.PipeTransmissionMode]::Byte,$option,4096,4096,$acl)
        'FIRST_INSTANCE_FLAG_ACCEPTED'
        try {
            $second=[IO.Pipes.NamedPipeServerStream]::new(
                $name,[IO.Pipes.PipeDirection]::InOut,1,
                [IO.Pipes.PipeTransmissionMode]::Byte,$option,4096,4096,$acl)
            throw 'SECURITY_REGRESSION_SECOND_INSTANCE_ALLOWED'
        } catch [IO.IOException] {
            'SECOND_FIRST_INSTANCE_REJECTED'
        }
    } catch [ArgumentOutOfRangeException] {
        'FIRST_INSTANCE_FLAG_NOT_SUPPORTED_BY_DOTNET'
    }
} finally {
    if($second){$second.Dispose()}
    if($first){$first.Dispose()}
}
