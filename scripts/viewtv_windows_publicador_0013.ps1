# Publicador Windows 0013: la autoridad NTFS vive fuera del worker/Docker.
# NO instalar mientras SQLite y API/worker sigan en 0012.
[CmdletBinding()]
param([ValidateSet('Preflight','Once','Loop','Library')][string]$Mode='Preflight')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Media = 'C:\VIEWTV\media'
$SourceRoot = 'C:\VIEWTV\media\descargas_temporales'
$Movies = 'C:\VIEWTV\media\Peliculas'
$Broker = 'C:\VIEWTV\publicador'
$Journal = 'C:\VIEWTV\publicador\journal'
$PolicyFile = 'C:\VIEWTV\publicador\aprobacion.json'
$WorkerId = 'publicador-windows-0013'
$script:NextScanCheck = $null

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ViewtvWin32Link {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  [return: MarshalAs(UnmanagedType.Bool)]
  public static extern bool CreateHardLinkW(string newName, string existingName, IntPtr security);
}
'@

function Assert-PlainDirectory([string]$Path) {
    $entry = [IO.DirectoryInfo]::new($Path)
    if (-not $entry.Exists -or
        ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Directorio no disponible o redirigido: publicación bloqueada.'
    }
}
function Assert-PlainFile([string]$Path, [long]$Size) {
    $entry = [IO.FileInfo]::new($Path)
    if (-not $entry.Exists -or
        ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        $entry.Length -ne $Size -or $Size -le 0) {
        throw 'El archivo origen no coincide: publicación bloqueada.'
    }
}
function Assert-Leaf([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value.Length -gt 150 -or
        $Value -in @('.', '..') -or $Value.Trim() -cne $Value -or
        $Value.EndsWith('.') -or $Value -match '[<>:"/\\|?*\x00-\x1f]' -or
        ($Value -split '\.')[0] -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$') {
        throw 'Nombre Windows no autorizado.'
    }
}
function Split-SafeRelative([string]$Relative) {
    if ([string]::IsNullOrWhiteSpace($Relative) -or
        $Relative.StartsWith('/') -or $Relative.Contains('\\') -or
        $Relative.Contains(':') -or $Relative.Length -gt 800) {
        throw 'Ruta relativa no autorizada.'
    }
    $parts = @($Relative.Split('/'))
    if ($parts.Count -lt 1 -or $parts.Count -gt 16) {
        throw 'Profundidad de ruta no autorizada.'
    }
    foreach ($part in $parts) { Assert-Leaf $part }
    return $parts
}
function Resolve-Source([string]$Relative, [long]$ExpectedSize) {
    $parts = @(Split-SafeRelative $Relative)
    $parent = $SourceRoot
    for ($i = 0; $i -lt $parts.Count - 1; $i++) {
        $parent = [IO.Path]::Combine($parent, $parts[$i])
        Assert-PlainDirectory $parent
    }
    $file = [IO.Path]::Combine($parent, $parts[-1])
    Assert-PlainFile $file $ExpectedSize
    return $file
}
function Assert-ProtectedDirectory([string]$Path) {
    Assert-PlainDirectory $Path
    $acl=Get-Acl -LiteralPath $Path
    $me=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null).Value
    $admins=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null).Value
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if (-not $acl.AreAccessRulesProtected -or $rules.Count -lt 1 -or
        $rules.Count -gt 3) {
        throw 'La ACL privada del publicador no es segura.'
    }
    foreach ($rule in $rules) {
        if ($rule.IsInherited -or $rule.AccessControlType -ne 'Allow' -or
            @($me,$system,$admins) -cnotcontains $rule.IdentityReference.Value) {
            throw 'Permisos del publicador no confinados.'
        }
    }
}
function Get-ViewtvPolicy {
    Assert-PlainDirectory 'C:\VIEWTV'
    Assert-PlainDirectory $Media
    Assert-PlainDirectory $SourceRoot
    Assert-PlainDirectory $Movies
    Assert-ProtectedDirectory $Broker
    Assert-ProtectedDirectory $Journal
    if ([IO.File]::Exists($PolicyFile) -eq $false) {
        throw 'Falta aprobación local de publicación.'
    }
    $policyAcl=Get-Acl -LiteralPath $PolicyFile
    $me=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $system=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::LocalSystemSid,$null).Value
    $admins=[Security.Principal.SecurityIdentifier]::new(
        [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid,$null).Value
    foreach ($rule in @($policyAcl.GetAccessRules(
        $true,$true,[Security.Principal.SecurityIdentifier]))) {
        if ($rule.AccessControlType -ne 'Allow' -or
            @($me,$system,$admins) -cnotcontains $rule.IdentityReference.Value) {
            throw 'La aprobación no tiene ACL privada.'
        }
    }
    $pfile=[IO.FileInfo]::new($PolicyFile)
    if (($pfile.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        $pfile.Length -gt 4096) {
        throw 'Aprobación no válida.'
    }
    $policy = [IO.File]::ReadAllText($PolicyFile) | ConvertFrom-Json
    if (@($policy.PSObject.Properties.Name).Count -ne 3 -or
        $policy.PSObject.Properties.Name -notcontains 'mode' -or
        $policy.PSObject.Properties.Name -notcontains 'after_id' -or
        $policy.PSObject.Properties.Name -notcontains 'allowed_download_id' -or
        $policy.mode -cnotin @('single','general') -or
        $policy.after_id -isnot [int] -or $policy.after_id -lt 1 -or
        ($policy.mode -eq 'single' -and
            ($policy.allowed_download_id -isnot [int] -or
             $policy.allowed_download_id -le $policy.after_id)) -or
        ($policy.mode -eq 'general' -and $policy.allowed_download_id -ne $null)) {
        throw 'Política de autorización no válida.'
    }
    $volume = [IO.DriveInfo]::new('C')
    if ($volume.DriveFormat -cne 'NTFS') {
        throw 'Publicación únicamente en NTFS.'
    }
    return $policy
}
function Assert-ApprovedId($Policy, [long]$DownloadId) {
    if ($DownloadId -le [long]$Policy.after_id -or
        ($Policy.mode -ceq 'single' -and
         $DownloadId -ne [long]$Policy.allowed_download_id)) {
        throw 'ID no autorizada por el host Windows.'
    }
}
function Invoke-ViewtvAuthority([string]$Operation, [long]$DownloadId=0, [int]$Attempt=0) {
    if ($Operation -cnotin @('status','claim','prepare','verify-source','renew','confirm','review','scan')) {
        throw 'Operación de autoridad desconocida.'
    }
    # Windows inicia el control mediante Docker Desktop; no necesita
    # invocar al worker ni confiar en rutas de publicación enviadas por él.
    $arguments = @('exec','viewtv-api-1',
      'python','-m','worker.organization_windows_cli',$Operation)
    if ($DownloadId -gt 0) {
        $arguments += @('--download-id', [string]$DownloadId,
                        '--attempt', [string]$Attempt)
    }
    $lines = @(& docker.exe @arguments)
    if ($LASTEXITCODE -ne 0 -or $lines.Count -ne 1 -or
        $lines[0].Length -gt 16384) {
        throw 'La autoridad independiente no respondió correctamente.'
    }
    $reply = $lines[0] | ConvertFrom-Json
    if ($null -eq $reply -or $reply.PSObject.Properties.Name -notcontains 'estado') {
        throw 'Respuesta no reconocida de la autoridad.'
    }
    return $reply
}
function Assert-Intent($Intent, $Policy, [long]$DownloadId, [int]$Attempt) {
    if ($Intent.version -ne 1 -or
        [long]$Intent.download_id -ne $DownloadId -or
        [int]$Intent.attempt -ne $Attempt -or
        [string]$Intent.worker_id -cne $WorkerId -or
        [string]$Intent.torrent_hash -cnotmatch '^(?:[a-f0-9]{40}|[a-f0-9]{64})$' -or
        [string]$Intent.library -cne 'Peliculas') {
        throw 'Identidad del trabajo incompatible.'
    }
    Assert-ApprovedId $Policy $DownloadId
    $expiry=[DateTime]::Parse([string]$Intent.lease_expires_utc,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
    if ($expiry -lt [DateTime]::UtcNow.AddSeconds(10)) {
        throw 'Lease de publicación vencido.'
    }
    $files=@($Intent.files)
    if ($files.Count -lt 1 -or $files.Count -gt 20) {
        throw 'Manifiesto de archivos inválido.'
    }
    $folder=''
    $names=@{}
    $videos=0
    foreach ($item in $files) {
        if ($item.size_bytes -isnot [long] -and $item.size_bytes -isnot [int]) {
            throw 'Tamaño de archivo inválido.'
        }
        if ([long]$item.size_bytes -le 0) { throw 'Tamaño no positivo.' }
        $sourceParts=@(Split-SafeRelative ([string]$item.source_relative))
        $targetParts=@(Split-SafeRelative ([string]$item.destination_relative))
        if ($targetParts.Count -ne 3 -or $targetParts[0] -cne 'Peliculas') {
            throw 'Destino de película no autorizado.'
        }
        if ($folder -and $folder -cne $targetParts[1]) {
            throw 'El plan intenta varias carpetas.'
        }
        $folder=$targetParts[1]
        $fileName=$targetParts[2]
        if ($names.ContainsKey($fileName.ToLowerInvariant())) {
            throw 'Colisión entre nombres de archivo.'
        }
        $names[$fileName.ToLowerInvariant()]=$true
        $extension=[IO.Path]::GetExtension($fileName).ToLowerInvariant()
        if ($extension -in @('.mkv','.mp4','.m4v','.avi')) {
            $videos++
        } elseif ($extension -notin @('.srt','.ass','.vtt')) {
            throw 'Extensión no admitida en publicación.'
        }
        $null=Resolve-Source ([string]$item.source_relative) ([long]$item.size_bytes)
    }
    if ($videos -ne 1) { throw 'Se exige un vídeo único.' }
    if ([IO.Directory]::Exists((Join-Path $Movies $folder)) -or
        [IO.File]::Exists((Join-Path $Movies $folder))) {
        # Los resultados ambiguos se concilian solo con el diario propio.
        $journalFile=Join-Path $Journal ('download-'+$DownloadId+'.json')
        if (-not [IO.File]::Exists($journalFile)) {
            throw 'Destino preexistente no registrado.'
        }
    }
    return $folder
}
function Get-PlanHash($Intent) {
    # Hash de identidad estable: NO usar caducidad ni intento.
    $body = [ordered]@{
        id = [long]$Intent.download_id
        torrent = [string]$Intent.torrent_hash
        library = [string]$Intent.library
        files = @($Intent.files)
    } | ConvertTo-Json -Compress -Depth 8
    $hash=[Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($hash.ComputeHash(
            [Text.Encoding]::UTF8.GetBytes($body))).Replace('-','').ToLowerInvariant()
    } finally { $hash.Dispose() }
}
function Write-NewJournal([string]$Path, $Record) {
    $content=$Record | ConvertTo-Json -Compress -Depth 7
    $bytes=[Text.Encoding]::UTF8.GetBytes($content)
    $stream=[IO.FileStream]::new($Path,[IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,[IO.FileShare]::None,4096,
        [IO.FileOptions]::WriteThrough)
    try {
        $stream.Write($bytes,0,$bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
}
function Verify-Published($Intent, [string]$Folder) {
    $published=Join-Path $Movies $Folder
    Assert-PlainDirectory $published
    $expected=@($Intent.files)
    $actual=@([IO.Directory]::GetFileSystemEntries($published))
    if ($actual.Count -ne $expected.Count) { throw 'Publicación incompleta.' }
    foreach ($item in $expected) {
        $name=([string]$item.destination_relative).Split('/')[-1]
        Assert-PlainFile (Join-Path $published $name) ([long]$item.size_bytes)
    }
}
function Complete-Publication([long]$Id, [int]$Attempt, $Intent, [string]$Folder) {
    Verify-Published $Intent $Folder
    $confirmed=Invoke-ViewtvAuthority 'confirm' $Id $Attempt
    if ($confirmed.estado -cne 'organizada') {
        throw 'La copia existe pero el lease ya no permite confirmarla.'
    }
    # El escaneo se puede repetir sin volver a publicar. HTTP 204 no es
    # prueba de descubrimiento ni de carátula.
    $scanned=Invoke-ViewtvAuthority 'scan' $Id $Attempt
    if ($scanned.estado -cne 'escaneo_solicitado') {
        throw 'Escaneo pendiente de reconciliar.'
    }
    $receipt=Join-Path $Journal ('scan-'+$Id+'.ok')
    if (-not [IO.File]::Exists($receipt)) {
        Write-NewJournal $receipt ([ordered]@{
            id=$Id; solicitado_utc=[DateTime]::UtcNow.ToString('o')
        })
    }
}
function Reconcile-Existing([long]$Id, [int]$Attempt, $Policy, [string]$JournalFile) {
    # Reconciliar desde diario privado, NO recalcular el plan por la
    # primera vez: el destino ya existe y el planner debe rechazarlo.
    $info=[IO.FileInfo]::new($JournalFile)
    if (($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        $info.Length -gt 16384) { throw 'Diario no verificable.' }
    $record=[IO.File]::ReadAllText($JournalFile)|ConvertFrom-Json
    if ($record.version -ne 1 -or $record.download_id -ne $Id -or
        [string]$record.stage_name -cnotmatch ('^\.viewtv-publicando-'+$Id+'-[a-f0-9]{32}$')) {
        throw 'Identidad del diario inválida.'
    }
    $intent=$record.intent
    if ($null -eq $intent -or [long]$intent.download_id -ne $Id -or
        [string]$intent.torrent_hash -cnotmatch '^(?:[a-f0-9]{40}|[a-f0-9]{64})$' -or
        [string]$record.manifest_sha256 -cne (Get-PlanHash $intent) -or
        [string]$intent.library -cne 'Peliculas') {
        throw 'Manifiesto del diario inválido.'
    }
    Assert-ApprovedId $Policy $Id
    $folder=([string]$intent.files[0].destination_relative).Split('/')[1]
    Assert-Leaf $folder
    if ([string]$record.folder -cne $folder -or
        [IO.Directory]::Exists((Join-Path $Movies $record.stage_name))) {
        throw 'Destino o staging ambiguos.'
    }
    $verified=Invoke-ViewtvAuthority 'verify-source' $Id $Attempt
    if ($verified.estado -cne 'fuente_verificada' -or
        [string]$verified.torrent_hash -cne [string]$intent.torrent_hash) {
        throw 'Torrent ya no corresponde al diario.'
    }
    foreach ($item in @($intent.files)) {
        $matches=@($verified.files | Where-Object {
            $_.source_relative -ceq $item.source_relative -and
            $_.size_bytes -eq $item.size_bytes
        })
        if ($matches.Count -ne 1) { throw 'Origen ya no coincide con el diario.' }
    }
    # Además, comprobar destino una sola vez y confirmar bajo lease NUEVO.
    Complete-Publication $Id $Attempt $intent $folder
    return 'reconciliada'
}
function Retry-PendingScans($Policy) {
    $now=[DateTime]::UtcNow
    if ($null -ne $script:NextScanCheck -and $now -lt $script:NextScanCheck) {
        return
    }
    $script:NextScanCheck=$now.AddMinutes(5)
    foreach ($file in @([IO.Directory]::GetFiles($Journal,'download-*.json'))) {
        $name=[IO.Path]::GetFileName($file)
        if ($name -cnotmatch '^download-([1-9][0-9]*)\.json$') { continue }
        $id=[long]$Matches[1]
        try { Assert-ApprovedId $Policy $id } catch { continue }
        if ([IO.File]::Exists((Join-Path $Journal ('scan-'+$id+'.ok')))) {
            continue
        }
        $details=[IO.FileInfo]::new($file)
        if (($details.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
            $details.Length -gt 16384) { continue }
        $record=[IO.File]::ReadAllText($file)|ConvertFrom-Json
        if ($record.download_id -ne $id -or
            $record.intent.download_id -ne $id) { continue }
        # La API rechaza el escaneo mientras no conste 'organizada'.
        try {
            $result=Invoke-ViewtvAuthority 'scan' $id 1
            if ($result.estado -ceq 'escaneo_solicitado') {
                Write-NewJournal (Join-Path $Journal ('scan-'+$id+'.ok')) (
                    [ordered]@{id=$id; solicitado_utc=[DateTime]::UtcNow.ToString('o')
                    })
            }
        } catch { }
    }
}
function Process-One {
    # 0022: no reclamar, reconciliar, publicar ni escanear mientras una
    # retirada u otro publicador posea la exclusion Windows compartida.
    # Solo se carga en una EJECUCION real; Mode=Library/Preflight
    # no modifica ni exige archivos de bloqueo de produccion.
    $guardLibrary=Join-Path $PSScriptRoot 'viewtv_windows_media_lock_0022.ps1'
    if(-not [IO.File]::Exists($guardLibrary)) {
        throw 'Falta protocolo de exclusion 0022: no publicar.'
    }
    . $guardLibrary
    $exclusive=Enter-ViewtvMediaExclusion0022 -Proposito 'publicador'
    try {
    $policy=Get-ViewtvPolicy
    Retry-PendingScans $policy
    $claim=Invoke-ViewtvAuthority 'claim'
    if ($claim.estado -ceq 'sin_trabajos' -or
        $claim.estado -ceq 'deshabilitado') { return $claim.estado }
    if ($claim.estado -cne 'reclamada') {
        throw 'La cola no ha reservado trabajo.'
    }
    $id=[long]$claim.download_id
    $attempt=[int]$claim.attempt
    Assert-ApprovedId $policy $id
    $journalFile=Join-Path $Journal ('download-'+$id+'.json')
    if ([IO.File]::Exists($journalFile)) {
        return Reconcile-Existing $id $attempt $policy $journalFile
    }
    $prepared=Invoke-ViewtvAuthority 'prepare' $id $attempt
    if ($prepared.estado -cne 'preparada') {
        throw 'El trabajo no ha superado la verificación.'
    }
    $intent=$prepared.intent
    $folder=Assert-Intent $intent $policy $id $attempt
    $digest=Get-PlanHash $intent
    # Si el journal aparece entre claim y reserva, CreateNew rechaza
    # sin sobrescribir y el siguiente ciclo solo intentará conciliar.
    if ([IO.Directory]::Exists((Join-Path $Movies $folder))) {
        throw 'Destino preexistente no autorizado.'
    }
    $stageName='.viewtv-publicando-'+$id+'-'+[Guid]::NewGuid().ToString('N')
    Write-NewJournal $journalFile ([ordered]@{
        version=1; download_id=$id; folder=$folder
        stage_name=$stageName; manifest_sha256=$digest; intent=$intent
        reserved_utc=[DateTime]::UtcNow.ToString('o')
    })
    $stage=Join-Path $Movies $stageName
    $final=Join-Path $Movies $folder
    [IO.Directory]::CreateDirectory($stage) | Out-Null
    foreach($item in @($intent.files)) {
        $source=Resolve-Source ([string]$item.source_relative) ([long]$item.size_bytes)
        $target=Join-Path $stage (([string]$item.destination_relative).Split('/')[-1])
        if(-not [ViewtvWin32Link]::CreateHardLinkW($target,$source,[IntPtr]::Zero)) {
            throw 'No se pudo crear un enlace duro NTFS; revisar staging.'
        }
        Assert-PlainFile $target ([long]$item.size_bytes)
    }
    $renew=Invoke-ViewtvAuthority 'renew' $id $attempt
    if ($renew.estado -cne 'renovada') { throw 'Lease perdido antes del movimiento.' }
    $latest=Invoke-ViewtvAuthority 'prepare' $id $attempt
    if ($latest.estado -cne 'preparada' -or
        (Get-PlanHash $latest.intent) -cne $digest) {
        throw 'Identidad cambiada antes de la publicación.'
    }
    if ([IO.Directory]::Exists($final) -or [IO.File]::Exists($final)) {
        throw 'Destino ocupado: no sobrescribir.'
    }
    [IO.Directory]::Move($stage,$final)
    Complete-Publication $id $attempt $intent $folder
    return 'publicada'
    } finally {
        Exit-ViewtvMediaExclusion0022 -Mutex $exclusive
    }
}

function Assert-AuthorityReady($Policy) {
    # Read-only: no reclamar un trabajo ni modificar SQLite en el preflight.
    $status=Invoke-ViewtvAuthority 'status'
    if ($status.estado -cne 'listo' -or
        [string]$status.modo -cne [string]$Policy.mode -or
        [long]$status.after_id -ne [long]$Policy.after_id -or
        ($Policy.mode -ceq 'single' -and
         [long]$status.allowed_download_id -ne [long]$Policy.allowed_download_id)) {
        throw 'La autoridad 0013 no coincide con la aprobación Windows.'
    }
}
if ($Mode -ceq 'Library') {
    # Solo carga funciones; el ensayo reemplaza todas las raíces con una
    # carpeta ficticia marcada bajo Public antes de ejecutar acciones.
    return
} elseif ($Mode -ceq 'Preflight') {
    $policy=Get-ViewtvPolicy
    Assert-AuthorityReady $policy
    Write-Output 'PREFLIGHT_PUBLICADOR_WINDOWS_0013_OK'
} elseif ($Mode -ceq 'Once') {
    try {
        Write-Output (Process-One)
    } catch {
        # Mantener diario y staging para reconciliación; no limpiar ni repetir.
        Write-Error 'Publicación detenida: requiere revisión del diario y lease.'
        exit 2
    }
} else {
    # No se permite un servicio 'saludable' que oculte un error de
    # autorización, SQLite, Docker o NTFS y siga trabajando a ciegas.
    try {
        $policy=Get-ViewtvPolicy
        Assert-AuthorityReady $policy
        while ($true) {
            $null=Process-One
            Start-Sleep -Seconds 30
        }
    } catch {
        [Console]::Error.WriteLine('PUBLICADOR_0013_DETENIDO_REQUIERE_REVISION')
        exit 2
    }
}
