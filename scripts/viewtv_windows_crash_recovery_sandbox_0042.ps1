# VIEWTV 0042: crash REAL proceso hijo al retirar primer hardlink.
# Solo dos nombres FICTICIOS en TEMP GUID. NO tiene modo de produccion.
[CmdletBinding()]
param(
    [ValidateSet('Test','TestAfterBoth','Crash','Recover','KillNative','RecoverNative','Finish','KillBoth','ReconcileBoth')][string]$Mode='Test',
    [ValidatePattern('^[a-f0-9]{32}$')][string]$RunId=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$requestedMode=$Mode
. (Join-Path $PSScriptRoot 'viewtv_windows_retirada_auditoria_0016.ps1') -Mode Audit | Out-Null
$Mode=$requestedMode

if(-not ('ViewtvKillCrash0042' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class ViewtvKillCrash0042 {
  [StructLayout(LayoutKind.Sequential)]
  public struct Disposition { public uint Flags; }
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true,
    EntryPoint="CreateFileW")]
  public static extern SafeFileHandle Open(
    string name,uint access,uint share,IntPtr security,
    uint create,uint flags,IntPtr template);
  [DllImport("kernel32.dll",SetLastError=true)]
  [return:MarshalAs(UnmanagedType.Bool)]
  public static extern bool SetFileInformationByHandle(
    SafeFileHandle handle,int kind,ref Disposition record,uint size);
  [DllImport("kernel32.dll")] public static extern IntPtr GetCurrentProcess();
  [DllImport("kernel32.dll",SetLastError=true)]
  [return:MarshalAs(UnmanagedType.Bool)]
  public static extern bool TerminateProcess(IntPtr process,uint exitCode);
}
'@
}
if($Mode -in @('Test','TestAfterBoth')) {
    if($RunId){throw 'Test no acepta GUID externo.'}
    $RunId=[Guid]::NewGuid().ToString('N')
} elseif(-not $RunId){throw 'Modo hijo exige GUID.'}
$parent=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$root=[IO.Path]::Combine($parent,'viewtv-0042-ficticio-'+$RunId)
if(-not $root.StartsWith($parent+'\',[StringComparison]::OrdinalIgnoreCase) -or
   $root.StartsWith('C:\VIEWTV\',[StringComparison]::OrdinalIgnoreCase) -or
   [IO.Path]::GetFileName($root) -cnotmatch
     '^viewtv-0042-ficticio-[a-f0-9]{32}$') {throw 'Sandbox no autorizado.'}
$original=Join-Path $root 'original-ficticio.bin'
$published=Join-Path $root 'publicado-ficticio.bin'
$third=Join-Path $root 'tercero-ficticio.bin'
$marker=Join-Path $root 'marcador-0042.txt'
$intent=Join-Path $root '01-intencion.json'
$cut=Join-Path $root '02-corte-intencion.json'
$restored=Join-Path $root '03-recuperado.json'
$nativeIntent=Join-Path $root '04-nativo-intencion.json'
$nativeRestored=Join-Path $root '05-nativo-recuperado.json'
$committing=Join-Path $root '06-commit-intencion.json'
$done=Join-Path $root '07-finalizado.json'
$allowed=@($original,$published,$third,$marker,$intent,$cut,$restored,
           $nativeIntent,$nativeRestored,$committing,$done)
$markValue='VIEWTV_0042_SANDBOX_'+$RunId
$expectedSize=131072L

function Assert-Sandbox {
    Assert-PlainDirectory $parent
    Assert-PlainDirectory $root
    $markFile=[IO.FileInfo]::new($marker)
    if(-not $markFile.Exists -or $markFile.Length -gt 100 -or
       $markFile.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint) -or
       [IO.File]::ReadAllText($marker) -cne $markValue) {
        throw 'Marca de sandbox incorrecta.'
    }
    foreach($path in [IO.Directory]::GetFileSystemEntries($root)) {
        $info=[IO.FileInfo]::new($path)
        if($path -cnotin $allowed -or -not $info.Exists -or
           ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
            throw 'Entrada inesperada en el sandbox.'
        }
    }
}
function Write-Once([string]$Path,[string]$Data) {
    $bytes=[Text.Encoding]::UTF8.GetBytes($Data)
    $h=[IO.FileStream]::new($Path,[IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,[IO.FileShare]::None,4096,
        [IO.FileOptions]::WriteThrough)
    try{$h.Write($bytes,0,$bytes.Length);$h.Flush($true)}
    finally{$h.Dispose()}
}
function Hash-File([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Write-Phase([string]$Path,[string]$Step,$Proof) {
    $data=[ordered]@{
        version=1;run=$RunId;phase=$Step;volume=[long]$Proof.volume
        high=[long]$Proof.high;low=[long]$Proof.low
        size=$expectedSize;sha256=[string]$Proof.sha256
    }|ConvertTo-Json -Compress
    Write-Once $Path $data
}
function Read-Phase([string]$Path,[string]$Step) {
    Assert-Sandbox
    $f=[IO.FileInfo]::new($Path)
    if(-not $f.Exists -or $f.Length -lt 100 -or $f.Length -gt 512){
        throw 'Fase ausente o extensa.'
    }
    $p=[IO.File]::ReadAllText($Path)|ConvertFrom-Json
    if(@($p.PSObject.Properties).Count -ne 8 -or
       $p.version -ne 1 -or $p.run -cne $RunId -or
       $p.phase -cne $Step -or $p.size -ne $expectedSize -or
       [string]$p.sha256 -cnotmatch '^[a-f0-9]{64}$' -or
       [long]$p.volume -lt 0 -or [long]$p.high -lt 0 -or
       [long]$p.low -lt 0) {throw 'Fase alterada.'}
    return $p
}
function Assert-Name([string]$Path,$Proof,[int]$Links) {
    $id=File-Fingerprint $Path
    if($id.links -ne $Links -or $id.bytes -ne $expectedSize -or
       $id.volume -ne $Proof.volume -or $id.high -ne $Proof.high -or
       $id.low -ne $Proof.low -or
       (Hash-File $Path) -cne $Proof.sha256){
        throw 'File ID, hardlinks o contenido incompatibles.'
    }
}
function Assert-Pair($Proof) {
    Assert-Name $original $Proof 2
    Assert-Name $published $Proof 2
}
function Child([string]$Action) {
    # .NET evita que STDERR del hijo denegado provoque ErrorAction=Stop
    # en el padre. Solo se observa el codigo, nunca se reemite su texto.
    if($Action -cnotin @('Crash','Recover','KillNative','RecoverNative','Finish','KillBoth','ReconcileBoth')){
        throw 'Subproceso no permitido.'
    }
    $exe=Join-Path $PSHOME 'powershell.exe'
    $start=[Diagnostics.ProcessStartInfo]::new()
    $start.FileName=$exe
    $start.Arguments=(
        '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+
        $PSCommandPath+'" -Mode '+$Action+' -RunId '+$RunId
    )
    $start.UseShellExecute=$false
    $start.CreateNoWindow=$true
    $start.RedirectStandardError=$true
    $start.RedirectStandardOutput=$true
    $proc=[Diagnostics.Process]::Start($start)
    try {
        if(-not $proc.WaitForExit(30000)){
            $proc.Kill()
            throw 'Subproceso excedio limite de prueba.'
        }
        return $proc.ExitCode
    } finally {$proc.Dispose()}
}
function Open-Delete([string]$Path) {
    $h=[ViewtvKillCrash0042]::Open(
        $Path,[uint32]0x10080,[uint32]4,[IntPtr]::Zero,
        [uint32]3,[uint32]0,[IntPtr]::Zero)
    if($null -eq $h -or $h.IsInvalid){
        if($null -ne $h){$h.Dispose()}
        throw 'No pudo abrirse handle DELETE.'
    }
    return $h
}
function Native-Id($Handle) {
    $info=[ViewtvLinkAudit0016+FileInfoNative]::new()
    if(-not [ViewtvLinkAudit0016]::GetFileInformationByHandle(
        $Handle,[ref]$info)){throw 'Identidad nativa ilegible.'}
    return $info
}
if($Mode -in @('Test','TestAfterBoth')) {
    if([IO.Directory]::Exists($root) -or [IO.File]::Exists($root)){
        throw 'GUID ocupado.'
    }
    [IO.Directory]::CreateDirectory($root)|Out-Null
    Write-Once $marker $markValue
    Assert-Sandbox
    $bytes=New-Object byte[] $expectedSize
    $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
    try{$rng.GetBytes($bytes)}finally{$rng.Dispose()}
    $writer=[IO.FileStream]::new($original,[IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,[IO.FileShare]::None,4096,
        [IO.FileOptions]::WriteThrough)
    try{$writer.Write($bytes,0,$bytes.Length);$writer.Flush($true)}
    finally{$writer.Dispose()}
    if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
        $published,$original,[IntPtr]::Zero)){throw 'Hardlink ficticio fallo.'}
    $info=File-Fingerprint $original
    $proof=[pscustomobject]@{
        volume=$info.volume;high=$info.high;low=$info.low
        sha256=(Hash-File $original)
    }
    Assert-Pair $proof
    Write-Phase $intent 'PREPARADO' $proof
    $exit=Child 'Crash'
    if($exit -eq 0){throw 'Hijo no murio.'}
    $null=Read-Phase $cut 'CORTE_PREPARADO'
    Assert-Name $original $proof 1
    if([IO.File]::Exists($published) -or [IO.File]::Exists($restored)){
        throw 'Corte no demostro ventana sin publicado.'
    }
    Write-Output 'KILL_REAL_POST_PRIMER_UNLINK=PASS'
    if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
        $third,$original,[IntPtr]::Zero)){throw 'No pudo crear tercer link.'}
    if((Child 'Recover') -eq 0){throw 'Recupero pese a tercer hardlink.'}
    if([IO.File]::Exists($published) -or [IO.File]::Exists($restored)){
        throw 'Recuperacion insegura hizo cambios.'
    }
    [IO.File]::Delete($third)
    Assert-Name $original $proof 1
    Write-Output 'TERCER_HARDLINK_BLOQUEA_RECUPERACION=PASS'
    if((Child 'Recover') -ne 0 -or (Child 'Recover') -ne 0){
        throw 'Recuperacion en procesos nuevos fallo.'
    }
    $null=Read-Phase $restored 'RECUPERADO'
    Assert-Pair $proof
    Write-Output 'RECUPERACION_IDEMPOTENTE_FILE_ID=PASS'
    if((Child 'KillNative') -eq 0){
        throw 'Unlink nativo no interrumpio el proceso hijo.'
    }
    $null=Read-Phase $nativeIntent 'PRIMER_UNLINK_NATIVO_PREPARADO'
    if([IO.File]::Exists($original) -or [IO.File]::Exists($nativeRestored)){
        throw 'Primer unlink Win32 interrumpido no confirmado.'
    }
    Assert-Name $published $proof 1
    Write-Output 'KILL_REAL_DURANTE_UNLINK_NATIVO=PASS'
    if((Child 'RecoverNative') -ne 0 -or
       (Child 'RecoverNative') -ne 0){
        throw 'Recuperacion Win32 no fue idempotente.'
    }
    $null=Read-Phase $nativeRestored 'WIN32_RECUPERADO'
    Assert-Pair $proof
    Write-Output 'RECUPERACION_NATIVA_RESTAURA_FILE_ID=PASS'
    $reader=[IO.FileStream]::new($published,[IO.FileMode]::Open,
        [IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
    try {
        if((Child 'Finish') -eq 0){throw 'Lector preabierto no bloqueo.'}
    } finally {$reader.Dispose()}
    Assert-Pair $proof
    if([IO.File]::Exists($committing)){
        throw 'Se escribio commit sin handles.'
    }
    Write-Output 'LECTOR_PREABIERTO_BLOQUEA_COMMIT=PASS'
    if($Mode -ceq 'TestAfterBoth'){
        if((Child 'KillBoth') -eq 0){
            throw 'El segundo unlink no interrumpio al hijo.'
        }
        $null=Read-Phase $committing 'COMMIT_PREPARADO'
        if([IO.File]::Exists($done) -or
           [IO.File]::Exists($original) -or
           [IO.File]::Exists($published)){
            throw 'El crash post-commit no dejo ambos nombres ausentes.'
        }
        Write-Output 'KILL_REAL_POST_SEGUNDO_UNLINK_NATIVE=PASS'
        # Otra identidad de archivo que ocupa el nombre impide finalizar.
        # Este fichero falso pertenece exclusivamente al ensayo TEMP.
        $intrusion='VIEWTV_0043_NOMBRE_REOCUPADO_'+$RunId
        Write-Once $original $intrusion
        if((Child 'ReconcileBoth') -eq 0){
            throw 'Se acepto nombre reocupado por otro File ID.'
        }
        if([IO.File]::Exists($done) -or
           [IO.File]::ReadAllText($original) -cne $intrusion){
            throw 'Conciliacion insegura modifico fichero ajeno de prueba.'
        }
        [IO.File]::Delete($original)
        Write-Output 'NOMBRE_REOCUPADO_BLOQUEA_RECONCILIACION=PASS'
        if((Child 'ReconcileBoth') -ne 0 -or
           (Child 'ReconcileBoth') -ne 0){
            throw 'Conciliacion post-commit no fue idempotente.'
        }
        $null=Read-Phase $done 'FINALIZADO'
        if([IO.File]::Exists($original) -or
           [IO.File]::Exists($published) -or
           [IO.File]::Exists($third)){
            throw 'Queda referencia o suplantacion de laboratorio.'
        }
        Write-Output 'RECONCILIACION_DOS_UNLINKS_SIN_REPETIR_BORRADO=PASS'
    } else {
        if((Child 'Finish') -ne 0 -or (Child 'Finish') -ne 0){
            throw 'Finalizacion nativa o repetida fallo.'
        }
        $null=Read-Phase $done 'FINALIZADO'
        if([IO.File]::Exists($original) -or
           [IO.File]::Exists($published) -or
           [IO.File]::Exists($third)){throw 'Archivo ficticio remanente.'}
        Write-Output 'DOS_UNLINKS_NATIVOS_Y_REPETICION=PASS'
    }
    Assert-Sandbox
    foreach($file in @($done,$committing,$nativeRestored,
        $nativeIntent,$restored,$cut,$intent,$marker)){
        [IO.File]::Delete($file)
    }
    [IO.Directory]::Delete($root,$false)
    Write-Output 'SANDBOX_GUID_LIMPIADO=SI'
    Write-Output 'EJECUTOR_PRODUCCION_INSTALADO=NO'
    Write-Output 'BORRADOS_REALES=0'
    Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
} elseif($Mode -ceq 'Crash') {
    $proof=Read-Phase $intent 'PREPARADO'
    Assert-Pair $proof
    Write-Phase $cut 'CORTE_PREPARADO' $proof
    [IO.File]::Delete($published)
    Assert-Name $original $proof 1
    [ViewtvKillCrash0042]::TerminateProcess(
        [ViewtvKillCrash0042]::GetCurrentProcess(),[uint32]77)|Out-Null
    throw 'TerminateProcess no termino hijo.'
} elseif($Mode -ceq 'Recover') {
    $proof=Read-Phase $intent 'PREPARADO'
    $null=Read-Phase $cut 'CORTE_PREPARADO'
    if([IO.File]::Exists($restored)) {
        $null=Read-Phase $restored 'RECUPERADO'
        Assert-Pair $proof
        Write-Output 'RECUPERACION_REPETIDA=PASS'
        return
    }
    if([IO.File]::Exists($published)){
        throw 'Publicacion existia antes de recuperar.'
    }
    Assert-Name $original $proof 1
    if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
        $published,$original,[IntPtr]::Zero)){
        throw 'No se creo hardlink en recuperacion.'
    }
    Assert-Pair $proof
    Write-Phase $restored 'RECUPERADO' $proof
    Write-Output 'RECUPERACION_RESTAURA_PUBLICACION=PASS'
} elseif($Mode -ceq 'KillNative') {
    $proof=Read-Phase $restored 'RECUPERADO'
    Assert-Pair $proof
    $one=$null
    $two=$null
    try {
        $one=Open-Delete $original
        $two=Open-Delete $published
        $a=Native-Id $one
        $b=Native-Id $two
        if($a.VolumeSerial -ne $b.VolumeSerial -or
           $a.IndexHigh -ne $b.IndexHigh -or
           $a.IndexLow -ne $b.IndexLow -or
           $a.Links -ne 2 -or $b.Links -ne 2 -or
           $a.VolumeSerial -ne $proof.volume -or
           $a.IndexHigh -ne $proof.high -or
           $a.IndexLow -ne $proof.low) {
            throw 'Unlink Win32 con identidad no consistente.'
        }
        # La fase duradera precede al cambio de metadatos nativos.
        Write-Phase $nativeIntent 'PRIMER_UNLINK_NATIVO_PREPARADO' $proof
        $disposition=[ViewtvKillCrash0042+Disposition]::new()
        $disposition.Flags=[uint32]3
        if(-not [ViewtvKillCrash0042]::SetFileInformationByHandle(
            $one,21,[ref]$disposition,[uint32]4)) {
            throw 'No se retiro el primer enlace Win32.'
        }
        [ViewtvKillCrash0042]::TerminateProcess(
            [ViewtvKillCrash0042]::GetCurrentProcess(),[uint32]78)|Out-Null
        throw 'No se mato el proceso despues de unlink Win32.'
    } finally {
        if($null -ne $two){$two.Dispose()}
        if($null -ne $one){$one.Dispose()}
    }
} elseif($Mode -ceq 'RecoverNative') {
    $proof=Read-Phase $restored 'RECUPERADO'
    $null=Read-Phase $nativeIntent 'PRIMER_UNLINK_NATIVO_PREPARADO'
    if([IO.File]::Exists($nativeRestored)){
        $null=Read-Phase $nativeRestored 'WIN32_RECUPERADO'
        Assert-Pair $proof
        Write-Output 'WIN32_RECUPERACION_REPETIDA=PASS'
        return
    }
    if([IO.File]::Exists($original)){
        throw 'Enlace de origen aun existe: no se reintenta.'
    }
    Assert-Name $published $proof 1
    if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
        $original,$published,[IntPtr]::Zero)){
        throw 'No se pudo reconstruir el origen ficticio.'
    }
    Assert-Pair $proof
    Write-Phase $nativeRestored 'WIN32_RECUPERADO' $proof
    Write-Output 'WIN32_RECUPERACION_RESTAURADA=PASS'
} elseif($Mode -ceq 'KillBoth') {
    # Posible muerte REAL entre el segundo unlink Win32 y su acuse duradero.
    # Nunca se ejecuta sobre ficheros ajenos al sandbox marcado.
    $null=Read-Phase $intent 'PREPARADO'
    $null=Read-Phase $cut 'CORTE_PREPARADO'
    $null=Read-Phase $restored 'RECUPERADO'
    $null=Read-Phase $nativeIntent 'PRIMER_UNLINK_NATIVO_PREPARADO'
    $proof=Read-Phase $nativeRestored 'WIN32_RECUPERADO'
    if([IO.File]::Exists($committing) -or [IO.File]::Exists($done)){
        throw 'Commit anterior encontrado.'
    }
    Assert-Pair $proof
    $one=$null
    $two=$null
    try {
        $one=Open-Delete $original
        $two=Open-Delete $published
        $a=Native-Id $one
        $b=Native-Id $two
        if($a.VolumeSerial -ne $b.VolumeSerial -or
           $a.IndexHigh -ne $b.IndexHigh -or
           $a.IndexLow -ne $b.IndexLow -or
           $a.Links -ne 2 -or $b.Links -ne 2 -or
           ($a.Attributes -band 0x400) -ne 0 -or
           ($b.Attributes -band 0x400) -ne 0 -or
           $a.VolumeSerial -ne $proof.volume -or
           $a.IndexHigh -ne $proof.high -or
           $a.IndexLow -ne $proof.low){
            throw 'Los dos handles no equivalen al File ID certificado.'
        }
        Write-Phase $committing 'COMMIT_PREPARADO' $proof
        $disp=[ViewtvKillCrash0042+Disposition]::new()
        $disp.Flags=[uint32]3
        if(-not [ViewtvKillCrash0042]::SetFileInformationByHandle(
            $one,21,[ref]$disp,[uint32]4)){
            throw 'Primer unlink de commit fallido.'
        }
        if(-not [ViewtvKillCrash0042]::SetFileInformationByHandle(
            $two,21,[ref]$disp,[uint32]4)){
            throw 'Segundo unlink de commit fallido.'
        }
        # Terminar sin cerrar handles, ni comprobar ausencia desde el hijo,
        # ni escribir FINALIZADO: fuerza reconciliacion tras la muerte.
        [ViewtvKillCrash0042]::TerminateProcess(
            [ViewtvKillCrash0042]::GetCurrentProcess(),[uint32]79)|Out-Null
        throw 'Kill posterior a segundo unlink no terminado.'
    } finally {
        if($null -ne $two){$two.Dispose()}
        if($null -ne $one){$one.Dispose()}
    }
} elseif($Mode -ceq 'ReconcileBoth') {
    # No repetir NINGUN unlink tras un commit incierto. Solo corroborar
    # dos nombres ausentes y cierre de fases del laboratorio aislado.
    $null=Read-Phase $intent 'PREPARADO'
    $null=Read-Phase $cut 'CORTE_PREPARADO'
    $null=Read-Phase $restored 'RECUPERADO'
    $null=Read-Phase $nativeIntent 'PRIMER_UNLINK_NATIVO_PREPARADO'
    $proof=Read-Phase $nativeRestored 'WIN32_RECUPERADO'
    $commit=Read-Phase $committing 'COMMIT_PREPARADO'
    if(
        $commit.volume -ne $proof.volume -or
        $commit.high -ne $proof.high -or
        $commit.low -ne $proof.low -or
        $commit.sha256 -cne $proof.sha256 -or
        [IO.File]::Exists($original) -or
        [IO.File]::Exists($published) -or
        [IO.File]::Exists($third)
    ){
        throw 'No se confirma ausencia o identidad del commit.'
    }
    if([IO.File]::Exists($done)){
        $last=Read-Phase $done 'FINALIZADO'
        if(
            $last.volume -ne $proof.volume -or
            $last.high -ne $proof.high -or
            $last.low -ne $proof.low -or
            $last.sha256 -cne $proof.sha256
        ){throw 'Diario final incompatible.'}
        Write-Output 'RECONCILIACION_REPETIDA_SIN_UNLINK=PASS'
        return
    }
    Write-Phase $done 'FINALIZADO' $proof
    Write-Output 'RECONCILIACION_SIN_UNLINK=PASS'
} else {
    $null=Read-Phase $intent 'PREPARADO'
    $null=Read-Phase $cut 'CORTE_PREPARADO'
    $null=Read-Phase $restored 'RECUPERADO'
    $null=Read-Phase $nativeIntent 'PRIMER_UNLINK_NATIVO_PREPARADO'
    $proof=Read-Phase $nativeRestored 'WIN32_RECUPERADO'
    if([IO.File]::Exists($done)){
        $null=Read-Phase $done 'FINALIZADO'
        if([IO.File]::Exists($original) -or [IO.File]::Exists($published)){
            throw 'Journal final contradice el disco.'
        }
        Write-Output 'COMMIT_REPETIDO_SIN_OPERACIONES=PASS'
        return
    }
    Assert-Pair $proof
    $one=$null
    $two=$null
    try {
        $one=Open-Delete $original
        $two=Open-Delete $published
        $a=Native-Id $one
        $b=Native-Id $two
        if($a.VolumeSerial -ne $b.VolumeSerial -or
           $a.IndexHigh -ne $b.IndexHigh -or
           $a.IndexLow -ne $b.IndexLow -or
           $a.Links -ne 2 -or $b.Links -ne 2 -or
           ($a.Attributes -band 0x400) -ne 0 -or
           ($b.Attributes -band 0x400) -ne 0 -or
           $a.VolumeSerial -ne $proof.volume -or
           $a.IndexHigh -ne $proof.high -or
           $a.IndexLow -ne $proof.low){
            throw 'Dos handles no equivalentes al diario.'
        }
        Write-Phase $committing 'COMMIT_PREPARADO' $proof
        $disp=[ViewtvKillCrash0042+Disposition]::new()
        $disp.Flags=[uint32]3
        if(-not [ViewtvKillCrash0042]::SetFileInformationByHandle(
            $one,21,[ref]$disp,[uint32]4)){
            throw 'Primer unlink kernel fallo.'
        }
        if(-not [ViewtvKillCrash0042]::SetFileInformationByHandle(
            $two,21,[ref]$disp,[uint32]4)){
            throw 'Segundo unlink kernel fallo.'
        }
    } finally {
        if($null -ne $two){$two.Dispose()}
        if($null -ne $one){$one.Dispose()}
    }
    if([IO.File]::Exists($original) -or [IO.File]::Exists($published)){
        throw 'Unlink dual no elimino ambos nombres ficticios.'
    }
    Write-Phase $done 'FINALIZADO' $proof
    Write-Output 'DOS_UNLINKS_NATIVOS_FICTICIOS=PASS'
}
