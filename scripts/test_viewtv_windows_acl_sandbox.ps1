# Ensayo exclusivamente local de ACL Windows sobre sandbox recién creado.
# No modifica cuentas, servicio, producción, SQLite, torrents ni archivos preexistentes.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$public = [System.IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
if ($public -ine 'C:\Users\Public' -or
    [System.IO.Path]::GetPathRoot($public).ToUpperInvariant() -cne 'C:\') {
    throw 'Solo se admite C:\Users\Public para este ensayo.'
}
$root = Join-Path $public ('viewtv-win-sandbox-' + [Guid]::NewGuid().ToString('N'))
$markerValue = 'VIEWTV_WINDOWS_SANDBOX_ONLY_V1' + [char]10
$marker = Join-Path $root '.viewtv-win-sandbox-only'
$keyPath = $null
$created = $false

try {
    if ([System.IO.Directory]::Exists($root) -or
        [System.IO.File]::Exists($root)) {
        throw 'El sandbox único ya existe.'
    }
    [System.IO.Directory]::CreateDirectory($root) | Out-Null
    $created = $true
    $currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new(
        [System.Security.Principal.WellKnownSidType]::LocalSystemSid, $null
    )
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new(
        [System.Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid, $null
    )
    $allowed = @($currentSid.Value, $systemSid.Value, $adminsSid.Value)
    $acl = Get-Acl -LiteralPath $root
    $acl.SetAccessRuleProtection($true, $false)
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
        [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    foreach ($sid in @($currentSid, $systemSid, $adminsSid)) {
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
            $sid,
            [System.Security.AccessControl.FileSystemRights]::FullControl,
            $inherit,
            [System.Security.AccessControl.PropagationFlags]::None,
            [System.Security.AccessControl.AccessControlType]::Allow
        )
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $root -AclObject $acl

    $actualAcl = Get-Acl -LiteralPath $root
    if (-not $actualAcl.AreAccessRulesProtected) {
        throw 'La herencia de permisos sigue habilitada.'
    }
    $rules = @($actualAcl.GetAccessRules(
        $true, $true, [System.Security.Principal.SecurityIdentifier]
    ))
    if ($rules.Count -lt 3) {
        throw 'Faltan entradas ACL explícitas.'
    }
    foreach ($entry in $rules) {
        if ($entry.IsInherited -or
            $entry.AccessControlType -ne
                [System.Security.AccessControl.AccessControlType]::Allow -or
            $allowed -cnotcontains $entry.IdentityReference.Value) {
            throw 'Permiso heredado, denegación o identidad inesperada.'
        }
    }

    [System.IO.File]::WriteAllText($marker, $markerValue)
    $stageName = '.viewtv-stage-1'
    $stage = Join-Path $root $stageName
    [System.IO.Directory]::CreateDirectory($stage) | Out-Null
    $videoName = 'Video ACL (2026).mkv'
    $subtitleName = 'Video ACL (2026).es.srt'
    $video = Join-Path $stage $videoName
    $subtitle = Join-Path $stage $subtitleName
    [System.IO.File]::WriteAllText($video, 'video de ensayo de ACL')
    [System.IO.File]::WriteAllText($subtitle, 'subtitulo de ensayo de ACL')
    $videoHash = (Get-FileHash -LiteralPath $video -Algorithm SHA256).Hash
    $subtitleHash = (Get-FileHash -LiteralPath $subtitle -Algorithm SHA256).Hash

    . (Join-Path $PSScriptRoot 'viewtv_windows_approval_sandbox.ps1')
    $keyPath = New-ViewtvTestKey
    $finalName = 'Video ACL (2026)'
    $approval = New-ViewtvTestApproval -SandboxRoot $root -StageName $stageName -FinalName $finalName -KeyPath $keyPath
    $published = & (Join-Path $PSScriptRoot 'viewtv_windows_publish_sandbox.ps1') -SandboxRoot $root -StageName $stageName -FinalName $finalName -ApprovalName $approval -KeyPath $keyPath | ConvertFrom-Json
    $final = Join-Path $root $finalName
    if ($published.estado -ne 'publicada_en_sandbox' -or
        [System.IO.Directory]::Exists($stage) -or
        (Get-FileHash -LiteralPath (Join-Path $final $videoName) -Algorithm SHA256).Hash -ne $videoHash -or
        (Get-FileHash -LiteralPath (Join-Path $final $subtitleName) -Algorithm SHA256).Hash -ne $subtitleHash) {
        throw 'La publicación con ACL confinada falló.'
    }
    # Denegación efectiva de creación de destinos nuevos en ESTA raíz ficticia.
    # Se restaura siempre el ACL exacto del ensayo, incluso si la prueba falla.
    $stage2Name = '.viewtv-stage-2'
    $stage2 = Join-Path $root $stage2Name
    [System.IO.Directory]::CreateDirectory($stage2) | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $stage2 'Denegada.mkv'), 'contenido de prueba')
    $approval2 = New-ViewtvTestApproval -SandboxRoot $root -StageName $stage2Name -FinalName 'Denegada' -KeyPath $keyPath
    $denyRule = [System.Security.AccessControl.FileSystemAccessRule]::new(
        $currentSid,
        [System.Security.AccessControl.FileSystemRights]::CreateDirectories,
        [System.Security.AccessControl.AccessControlType]::Deny
    )
    # DACL-only: no solicitar escrituras SACL que requieran SeSecurityPrivilege.
    $restrict = [System.Security.AccessControl.DirectorySecurity]::new()
    $restrict.SetAccessRuleProtection($true, $false)
    foreach ($sid in @($currentSid, $systemSid, $adminsSid)) {
        $restrict.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new(
            $sid, [System.Security.AccessControl.FileSystemRights]::FullControl,
            $inherit, [System.Security.AccessControl.PropagationFlags]::None,
            [System.Security.AccessControl.AccessControlType]::Allow
        ))
    }
    $restrict.AddAccessRule($denyRule)
    [System.IO.Directory]::SetAccessControl($root, $restrict)
    $refused = $false
    try {
        try {
            & (Join-Path $PSScriptRoot 'viewtv_windows_publish_sandbox.ps1') -SandboxRoot $root -StageName $stage2Name -FinalName 'Denegada' -ApprovalName $approval2 -KeyPath $keyPath | Out-Null
        } catch {
            $refused = $true
        }
        if (-not $refused -or -not [System.IO.Directory]::Exists($stage2) -or
            [System.IO.Directory]::Exists((Join-Path $root 'Denegada'))) {
            throw 'La denegación de permisos no impidió la publicación.'
        }
    } finally {
        [System.IO.Directory]::SetAccessControl($root, $acl)
    }
    if (@((Get-Acl -LiteralPath $root).Access | Where-Object {
        $_.AccessControlType -eq 'Deny'
    }).Count -gt 0) {
        throw 'La ACL temporal de denegación no se restauró.'
    }
    [pscustomobject]@{
        acl_sin_herencia = $true
        identidades_explicitas = $rules.Count
        publicacion_multifichero = 'verificada'
        escritura_denegada = 'rechazada_sin_mover'
        identidades_windows_separadas = $false
        produccion = 'sin_acceso'
    } | ConvertTo-Json -Compress
}
finally {
    # Limpia exclusivamente el directorio nuevo de esta ejecución, si su marca
    # sigue siendo auténtica y el directorio no fue redirigido.
    if ($created -and
        [System.IO.Path]::GetDirectoryName($root) -ieq $public -and
        [System.IO.Path]::GetFileName($root) -cmatch '^viewtv-win-sandbox-[0-9a-f]{32}$' -and
        [System.IO.Directory]::Exists($root) -and
        ([System.IO.DirectoryInfo]::new($root).Attributes -band
          [System.IO.FileAttributes]::ReparsePoint) -eq 0 -and
        [System.IO.File]::Exists($marker) -and
        [System.IO.File]::ReadAllText($marker) -ceq $markerValue) {
        [System.IO.Directory]::Delete($root, $true)
    }
    if ($keyPath -and [System.IO.File]::Exists($keyPath)) {
        $keyDirectory = [System.IO.Path]::GetDirectoryName($keyPath)
        if ([System.IO.Path]::GetFileName($keyDirectory) -match
              '^viewtv-test-key-[0-9a-f]{32}$' -and
            [System.IO.Path]::GetDirectoryName($keyDirectory) -ieq
              [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')) {
            [System.IO.Directory]::Delete($keyDirectory, $true)
        }
    }
}
