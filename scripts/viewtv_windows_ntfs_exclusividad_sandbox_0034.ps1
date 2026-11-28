# VIEWTV 0034 — comprobación kernel NTFS, EXCLUSIVAMENTE DOS HARDLINKS TEMP.
# Sin parámetros. NUNCA selecciona un medio o descarga de C:\VIEWTV.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Importa Win32 File-ID/hardlinks. Ejecuta auditoría de producción SOLO LECTURA.
. (Join-Path $PSScriptRoot 'viewtv_windows_retirada_auditoria_0016.ps1') -Mode Audit |
    Out-Null

$parent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$root = [IO.Path]::Combine(
    $parent, 'viewtv-ntfs-0034-ficticio-' + [Guid]::NewGuid().ToString('N')
)
$origin = [IO.Path]::Combine($root,'original-ficticio.bin')
$published = [IO.Path]::Combine($root,'publicado-ficticio.bin')
$third = [IO.Path]::Combine($root,'tercero-ficticio.bin')
$marker = [IO.Path]::Combine($root,'marca-0034.txt')
$markValue = 'VIEWTV-NTFS-0034-FICTICIO-' + [IO.Path]::GetFileName($root)
$size = 256 * 1024
$created = $false

function Assert-Sandbox0034 {
    if (-not [IO.Directory]::Exists($root) -or
        -not [IO.Directory]::Exists($parent) -or
        $root.StartsWith('C:\VIEWTV\',[StringComparison]::OrdinalIgnoreCase) -or
        -not $root.StartsWith($parent + '\',[StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($root) -cnotmatch
          '^viewtv-ntfs-0034-ficticio-[a-f0-9]{32}$') {
        throw 'Fuera de sandbox temporal.'
    }
    foreach ($dir in @($parent,$root)) {
        $item = [IO.DirectoryInfo]::new($dir)
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Sandbox redirigido.'
        }
    }
    if (-not [IO.File]::Exists($marker) -or
        [IO.File]::ReadAllText($marker) -cne $markValue) {
        throw 'Marca de sandbox inválida.'
    }
    $allowed = @($origin,$published,$third,$marker)
    foreach ($name in [IO.Directory]::GetFileSystemEntries($root)) {
        $file = [IO.FileInfo]::new($name)
        if ($allowed -cnotcontains $name -or
            ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Sandbox contiene archivo ajeno.'
        }
    }
}

function Assert-TwoHardlinks0034 {
    $a = File-Fingerprint $origin
    $b = File-Fingerprint $published
    if ($a.volume -ne $b.volume -or $a.high -ne $b.high -or
        $a.low -ne $b.low -or $a.links -ne 2 -or
        $b.links -ne 2 -or $a.bytes -ne $size -or $b.bytes -ne $size) {
        throw 'El par NTFS no es exclusivo del ensayo.'
    }
    return $a
}

function Test-CannotOpen0034 {
    param([string]$Path, [IO.FileAccess]$Access)
    $didBlock = $false
    $handle = $null
    try {
        $handle = [IO.FileStream]::new(
            $Path, [IO.FileMode]::Open, $Access,
            ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete)
        )
    } catch [IO.IOException] {
        $didBlock = $true
    } finally {
        if ($null -ne $handle) { $handle.Dispose() }
    }
    if (-not $didBlock) {
        throw 'El kernel permitió abrir por hardlink bajo bloqueo exclusivo.'
    }
}

if ([IO.Directory]::Exists($root) -or [IO.File]::Exists($root)) {
    throw 'GUID de sandbox ya existe.'
}
try {
    [IO.Directory]::CreateDirectory($root) | Out-Null
    $created = $true
    [IO.File]::WriteAllText($marker,$markValue)
    Assert-Sandbox0034

    $bytes = New-Object byte[] $size
    $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $writer = [IO.FileStream]::new(
        $origin,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,
        [IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough
    )
    try {
        $writer.Write($bytes,0,$bytes.Length)
        $writer.Flush($true)
    } finally { $writer.Dispose() }
    if (-not [ViewtvLinkAudit0016]::CreateHardLinkW(
        $published,$origin,[IntPtr]::Zero
    )) { throw 'No se pudo crear hardlink privado.' }
    Assert-Sandbox0034
    $identity = Assert-TwoHardlinks0034

    # Lector que ya existe por el nombre PUBLICADO debe impedir al
    # futuro ejecutor adquirir el File ID en exclusiva por ORIGEN.
    $reader = [IO.FileStream]::new(
        $published,[IO.FileMode]::Open,[IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite
    )
    $blocked = $false
    $guard = $null
    try {
        try {
            $guard = [IO.FileStream]::new(
                $origin,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,
                [IO.FileShare]::None
            )
        } catch [IO.IOException] { $blocked = $true }
        if (-not $blocked) { throw 'Lector anterior no frenó exclusión.' }
    } finally {
        if ($null -ne $guard) { $guard.Dispose() }
        $reader.Dispose()
    }
    Write-Output 'LECTOR_PREEXISTENTE_BLOQUEA_EXCLUSION=PASS'

    # Tercer hardlink, aunque tenga el mismo contenido, rompe la
    # identidad de dos nombres que exige la retirada de ViewTV.
    if (-not [ViewtvLinkAudit0016]::CreateHardLinkW(
        $third,$origin,[IntPtr]::Zero
    )) { throw 'No se pudo crear tercer enlace ficticio.' }
    $ref = File-Fingerprint $third
    if ($ref.links -ne 3 -or $ref.volume -ne $identity.volume -or
        $ref.high -ne $identity.high -or $ref.low -ne $identity.low) {
        throw 'Tercer enlace no verificado.'
    }
    $thirdRejected = $false
    try { $null = Assert-TwoHardlinks0034 }
    catch { $thirdRejected = $true }
    if (-not $thirdRejected) { throw 'Tercer enlace no fue rechazado.' }
    $auditRejected=$false
    try { $null=Test-SameHardlink $origin $published $size }
    catch { $auditRejected=$true }
    if(-not $auditRejected) { throw 'Auditoría base aceptó un tercer hardlink.' }
    Write-Output 'AUDITORIA_BASE_0016_RECHAZA_TERCERO=PASS'
    Assert-Sandbox0034
    [IO.File]::Delete($third)
    $null = Assert-TwoHardlinks0034
    Write-Output 'TERCER_HARDLINK_BLOQUEA_RETIRADA=PASS'

    # La misma identidad NTFS se protege desde ambos nombres.
    # Ningún unlink real se hace mientras está retenido el handle.
    $exclusive = [IO.FileStream]::new(
        $origin,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,
        [IO.FileShare]::None
    )
    try {
        Test-CannotOpen0034 $published ([IO.FileAccess]::Read)
        Test-CannotOpen0034 $published ([IO.FileAccess]::Write)
        Test-CannotOpen0034 $origin ([IO.FileAccess]::Read)
        Test-CannotOpen0034 $origin ([IO.FileAccess]::Write)
        Write-Output 'HARDLINKS_NTFS_NO_ADMITEN_LECTOR_NI_ESCRITOR_DURANTE_LOCK=PASS'
        # Crear nombres NTFS es una operación de metadatos diferente
        # de abrir datos; medir si el bloqueo exclusivo la impide.
        $newLinkUnderLock=[ViewtvLinkAudit0016]::CreateHardLinkW(
            $third,$origin,[IntPtr]::Zero
        )
        if($newLinkUnderLock) {
            Write-Output 'TERCER_HARDLINK_BAJO_FILESHARE_NONE=POSIBLE'
        } else {
            Write-Output 'TERCER_HARDLINK_BAJO_FILESHARE_NONE=BLOQUEADO'
        }
    } finally {
        $exclusive.Dispose()
    }
    if($newLinkUnderLock) {
        $finger=File-Fingerprint $third
        if($finger.links -ne 3 -or $finger.volume -ne $identity.volume -or
           $finger.high -ne $identity.high -or $finger.low -ne $identity.low) {
            throw 'Enlace creado durante exclusión con identidad ajena.'
        }
        [IO.File]::Delete($third)
    }
    $null = Assert-TwoHardlinks0034
    $reopened = [IO.FileStream]::new(
        $published,[IO.FileMode]::Open,[IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite
    )
    $reopened.Dispose()
    Write-Output 'SOLTAR_EXCLUSION_PERMITE_REAPERTURA=PASS'
    Write-Output 'EXCLUSION_SOLA_NO_PERMITE_UNLINK_ATOMICO=SI'
    Write-Output 'RESULTADO_EJECUTOR_REAL=NO_AUTORIZADO'
    Write-Output 'BORRADOS_PRODUCCION=0'
    Write-Output 'TORRENTS_MODIFICADOS=0'
} finally {
    if ($created -and [IO.Directory]::Exists($root)) {
        Assert-Sandbox0034
        foreach ($file in @($third,$published,$origin,$marker)) {
            if ([IO.File]::Exists($file)) { [IO.File]::Delete($file) }
        }
        [IO.Directory]::Delete($root,$false)
    }
}
