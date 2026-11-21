# Ensayo no elevado sobre archivos ficticios propios en journal privado.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$dir='C:\VIEWTV\publicador\journal'
$before=Join-Path $dir '.viewtv-replace-sandbox-before-0013.txt'
$next=Join-Path $dir '.viewtv-replace-sandbox-next-0013.txt'
$status=Join-Path $dir '.viewtv-replace-sandbox-result-0013.txt'
if([IO.File]::Exists($before) -or [IO.File]::Exists($next) -or
   [IO.File]::Exists($status)) { throw 'SANDBOX_ALREADY_EXISTS' }
[IO.File]::WriteAllText($before,'antes',[Text.Encoding]::UTF8)
[IO.File]::WriteAllText($next,'despues',[Text.Encoding]::UTF8)
try {
    [IO.File]::Replace($next,$before,$null,$true)
    if([IO.File]::ReadAllText($before) -ne 'despues') {
        throw 'SANDBOX_REPLACE_NOT_VERIFIED'
    }
    [IO.File]::WriteAllText($status,'SANDBOX_REPLACE_OK',[Text.Encoding]::UTF8)
} catch {
    [IO.File]::WriteAllText($status,
        'SANDBOX_REPLACE_FAIL='+$_.Exception.GetType().Name,
        [Text.Encoding]::UTF8)
    exit 2
}
