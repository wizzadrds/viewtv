# Test-only Windows authorization for publishing VIEWTV sandbox folders.
# The signing key lives in a private Windows TEMP folder outside Docker mounts.
# This is not a production security boundary or a production credential store.
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'viewtv_windows_stage_identity_sandbox.ps1')

function Assert-TestKeyPath([string]$KeyPath) {
    $tempRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
    $full = [System.IO.Path]::GetFullPath($KeyPath)
    $directory = [System.IO.Path]::GetDirectoryName($full)
    if (
        [System.IO.Path]::GetFileName($full) -cne 'key.bin' -or
        [System.IO.Path]::GetDirectoryName($directory) -ine $tempRoot -or
        [System.IO.Path]::GetFileName($directory) -cnotmatch '^viewtv-test-key-[0-9a-f]{32}$' -or
        -not [System.IO.File]::Exists($full)
    ) {
        throw 'Clave de autorización de pruebas no válida.'
    }
    $info = [System.IO.FileInfo]::new($full)
    if (($info.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'No se admiten claves redirigidas.'
    }
    $key = [System.IO.File]::ReadAllBytes($full)
    if ($key.Length -ne 32) {
        throw 'Tamaño de clave de prueba inválido.'
    }
    return $key
}

function New-ViewtvTestKey {
    $tempRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
    $directory = Join-Path $tempRoot ('viewtv-test-key-' + [Guid]::NewGuid().ToString('N'))
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    $keyFile = Join-Path $directory 'key.bin'
    $secret = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($secret) } finally { $rng.Dispose() }
    [System.IO.File]::WriteAllBytes($keyFile, $secret)
    return $keyFile
}

function New-ViewtvTestApproval {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$SandboxRoot,
        [Parameter(Mandatory=$true)][string]$StageName,
        [Parameter(Mandatory=$true)][string]$FinalName,
        [Parameter(Mandatory=$true)][string]$KeyPath,
        [int]$ExpiryMinutes = 5
    )
    if ($StageName -cnotmatch '^\.viewtv-stage-[1-9][0-9]{0,9}$' -or
        $ExpiryMinutes -lt -10 -or $ExpiryMinutes -gt 10) {
        throw 'Parámetros de autorización inválidos.'
    }
    $key = Assert-TestKeyPath $KeyPath
    $root = [System.IO.Path]::GetFullPath($SandboxRoot).TrimEnd('\')
    $stage = Join-Path $root $StageName
    $files = @()
    foreach ($file in @([System.IO.Directory]::GetFiles($stage))) {
        $info = [System.IO.FileInfo]::new($file)
        if (($info.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'No se autorizan enlaces.'
        }
        $files += [ordered]@{
            name = $info.Name
            size = [long]$info.Length
            sha256 = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $payload = [ordered]@{
        version = 1
        sandbox = [System.IO.Path]::GetFileName($root)
        stage = $StageName
        final = $FinalName
        stage_identity = (Get-ViewtvTestStageFingerprint $root $StageName)
        nonce = [Guid]::NewGuid().ToString('N')
        expires_utc = [DateTime]::UtcNow.AddMinutes($ExpiryMinutes).ToString('o')
        files = @($files)
    } | ConvertTo-Json -Compress -Depth 6
    $hmac = New-Object System.Security.Cryptography.HMACSHA256 (,$key)
    try {
        $signature = [Convert]::ToBase64String(
            $hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($payload))
        )
    } finally { $hmac.Dispose() }
    $approval = [ordered]@{
        payload = $payload
        signature = $signature
    } | ConvertTo-Json -Compress -Depth 4
    $stageId = $StageName.Substring('.viewtv-stage-'.Length)
    $approvalName = ".viewtv-approval-$stageId.json"
    $approvalPath = Join-Path $root $approvalName
    if ([System.IO.File]::Exists($approvalPath)) {
        throw 'Ya existe una autorización anterior para este trabajo.'
    }
    [System.IO.File]::WriteAllText(
        $approvalPath, $approval, [System.Text.Encoding]::UTF8
    )
    return $approvalName
}

function Assert-ViewtvTestApproval {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$SandboxRoot,
        [Parameter(Mandatory=$true)][string]$StageName,
        [Parameter(Mandatory=$true)][string]$FinalName,
        [Parameter(Mandatory=$true)][string]$ApprovalName,
        [Parameter(Mandatory=$true)][string]$KeyPath,
        [ValidateSet('Stage','Published')][string]$Location = 'Stage',
        [switch]$AllowExpiredReadOnly
    )
    if ($ApprovalName -cnotmatch '^\.viewtv-approval-[1-9][0-9]{0,9}\.json$' -or
        $StageName -cnotmatch '^\.viewtv-stage-[1-9][0-9]{0,9}$' -or
        $ApprovalName -cne ('.viewtv-approval-' +
            $StageName.Substring('.viewtv-stage-'.Length) + '.json')) {
        throw 'Identidad de aprobación no válida.'
    }
    $root = [System.IO.Path]::GetFullPath($SandboxRoot).TrimEnd('\')
    $approvalPath = Join-Path $root $ApprovalName
    if (-not [System.IO.File]::Exists($approvalPath)) {
        throw 'No existe autorización firmada.'
    }
    $info = [System.IO.FileInfo]::new($approvalPath)
    if (($info.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -or
        $info.Length -gt 32768) {
        throw 'Archivo de autorización inseguro.'
    }

    $key = Assert-TestKeyPath $KeyPath
    $envelope = [System.IO.File]::ReadAllText($approvalPath) | ConvertFrom-Json
    if ($envelope.PSObject.Properties.Name -notcontains 'payload' -or
        $envelope.PSObject.Properties.Name -notcontains 'signature' -or
        $envelope.payload -isnot [string] -or
        $envelope.signature -isnot [string]) {
        throw 'Autorización mal formada.'
    }
    $hmac = New-Object System.Security.Cryptography.HMACSHA256 (,$key)
    try {
        $expected = $hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes(
            $envelope.payload
        ))
    } finally { $hmac.Dispose() }
    try {
        $received = [Convert]::FromBase64String($envelope.signature)
    } catch {
        throw 'Firma de autorización inválida.'
    }
    # Constant-time comparison (also works in Windows PowerShell 5.1).
    if ($received.Length -ne $expected.Length) {
        throw 'Firma de autorización inválida.'
    }
    $difference = 0
    for ($i=0; $i -lt $expected.Length; $i++) {
        $difference = $difference -bor ($expected[$i] -bxor $received[$i])
    }
    if ($difference -ne 0) { throw 'Firma de autorización inválida.' }

    $intent = $envelope.payload | ConvertFrom-Json
    $expiration = [DateTime]::Parse(
        [string]$intent.expires_utc,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [System.Globalization.DateTimeStyles]::RoundtripKind
    ).ToUniversalTime()
    if ($intent.version -ne 1 -or
        $intent.sandbox -cne [System.IO.Path]::GetFileName($root) -or
        $intent.stage -cne $StageName -or
        $intent.final -cne $FinalName -or
        [string]$intent.nonce -cnotmatch '^[0-9a-f]{32}$' -or
        ($expiration -lt [DateTime]::UtcNow -and
            -not ($AllowExpiredReadOnly -and $Location -eq 'Published')) -or
        $expiration -gt [DateTime]::UtcNow.AddMinutes(15)) {
        throw 'El plan firmado no coincide o ha caducado.'
    }
    $folder = Join-Path $root (
        $(if ($Location -eq 'Stage') { $StageName } else { $FinalName })
    )
    $folderInfo = [System.IO.DirectoryInfo]::new($folder)
    if (-not $folderInfo.Exists -or
        ($folderInfo.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Carpeta del plan no disponible.'
    }
    $actual = @([System.IO.Directory]::GetFileSystemEntries($folder))
    $declared = @($intent.files)
    if ($declared.Count -lt 1 -or $declared.Count -gt 20 -or
        $actual.Count -ne $declared.Count) {
        throw 'Los archivos no coinciden con el plan firmado.'
    }
    $seen = @{}
    foreach ($entry in $declared) {
        if ($entry.name -isnot [string] -or
            [string]::IsNullOrWhiteSpace($entry.name) -or
            $entry.name -in @('.','..') -or
            $entry.name -match '[<>:"/\\|?*\x00-\x1f]' -or
            $entry.name.StartsWith('.') -or
            $seen.ContainsKey($entry.name.ToLowerInvariant())) {
            throw 'El plan firmado contiene nombres peligrosos o repetidos.'
        }
        $seen[$entry.name.ToLowerInvariant()] = $true
        $file = Join-Path $folder $entry.name
        $fileInfo = [System.IO.FileInfo]::new($file)
        if (-not $fileInfo.Exists -or
            ($fileInfo.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -or
            $fileInfo.Length -ne [long]$entry.size -or
            $fileInfo.Length -le 0 -or
            $fileInfo.Length -gt 33554432 -or
            [string]$entry.sha256 -cnotmatch '^[a-f0-9]{64}$' -or
            (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne [string]$entry.sha256) {
            throw 'El contenido no coincide con los hashes autorizados.'
        }
    }
    $actualIdentity = Get-ViewtvTestFolderFingerprint $root $(
        if ($Location -eq 'Stage') { $StageName } else { $FinalName }
    )
    if ($intent.PSObject.Properties.Name -notcontains 'stage_identity' -or
        [string]$intent.stage_identity -cne $actualIdentity) {
        throw 'La identidad NTFS del staging no coincide con el plan firmado.'
    }
    return $true
}
