# VIEWTV 0013 — Signed response for the Windows pipe sandbox, NOT a service.
# Imports Assert-TestKeyPath from viewtv_windows_approval_sandbox.ps1.
Set-StrictMode -Version Latest

function Get-ViewtvBrokerTestRequestDigest([string]$Request) {
    $sha=[Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString(
            $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Request))
        ).Replace('-','').ToLowerInvariant()
    } finally { $sha.Dispose() }
}

function New-ViewtvBrokerTestChallenge {
    $buffer=New-Object byte[] 32
    $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
    return ,$buffer
}

function New-ViewtvBrokerTestSignedResponse(
    [string]$Status, [byte[]]$Challenge, [string]$Request, [string]$TestKeyPath
) {
    if ($Challenge.Length -ne 32 -or
        $Status -cnotin @(
            'intencion_registrada_sin_publicar',
            'replay_bloqueado','requiere_revision','no_autorizada'
        )) {
        throw 'Respuesta de sandbox no reconocida.'
    }
    $reply=[ordered]@{
        version=1
        challenge=([BitConverter]::ToString($Challenge)).Replace('-','').ToLowerInvariant()
        request_sha256=Get-ViewtvBrokerTestRequestDigest $Request
        estado=$Status
        publicacion_iniciada=$false
    } | ConvertTo-Json -Compress
    $key=Assert-TestKeyPath $TestKeyPath
    $h=[Security.Cryptography.HMACSHA256]::new($key)
    try {
        $domain='VIEWTV_PIPE_SIGNED_RESPONSE_V1' + [char]10
        $signature=[Convert]::ToBase64String(
            $h.ComputeHash([Text.Encoding]::UTF8.GetBytes($domain+$reply))
        )
    } finally { $h.Dispose() }
    return ([ordered]@{payload=$reply;signature=$signature} |
        ConvertTo-Json -Compress)
}

function Assert-ViewtvBrokerTestSignedResponse(
    [string]$RawResponse, [byte[]]$Challenge,
    [string]$Request, [string]$TestKeyPath
) {
    if ($Challenge.Length -ne 32 -or
        [Text.Encoding]::UTF8.GetByteCount($RawResponse) -gt 2048) {
        throw 'Respuesta del broker demasiado grande o desafío no válido.'
    }
    try {
        $envelope=$RawResponse | ConvertFrom-Json
        if (@($envelope.PSObject.Properties.Name).Count -ne 2 -or
            @($envelope.PSObject.Properties.Name) -cnotcontains 'payload' -or
            @($envelope.PSObject.Properties.Name) -cnotcontains 'signature' -or
            $envelope.payload -isnot [string] -or
            $envelope.signature -isnot [string]) {
            throw 'Sobre de respuesta no válido.'
        }
        $key=Assert-TestKeyPath $TestKeyPath
        $h=[Security.Cryptography.HMACSHA256]::new($key)
        try {
            $domain='VIEWTV_PIPE_SIGNED_RESPONSE_V1' + [char]10
            $expected=$h.ComputeHash(
                [Text.Encoding]::UTF8.GetBytes($domain+$envelope.payload))
        } finally { $h.Dispose() }
        $received=[Convert]::FromBase64String($envelope.signature)
        if ($received.Length -ne $expected.Length) {
            throw 'Firma de servidor no válida.'
        }
        $diff=0
        for ($i=0;$i -lt $expected.Length;$i++) {
            $diff=$diff -bor ($expected[$i] -bxor $received[$i])
        }
        if ($diff -ne 0) {throw 'Firma de servidor no válida.'}
        $reply=$envelope.payload | ConvertFrom-Json
        $keys=@('version','challenge','request_sha256','estado','publicacion_iniciada')
        if (@($reply.PSObject.Properties.Name).Count -ne $keys.Count) {
            throw 'Respuesta con campos inesperados.'
        }
        foreach($keyName in $keys) {
            if (@($reply.PSObject.Properties.Name) -cnotcontains $keyName) {
                throw 'Respuesta incompleta.'
            }
        }
        $challengeHex=([BitConverter]::ToString($Challenge)).Replace('-','').ToLowerInvariant()
        if ($reply.version -ne 1 -or
            [string]$reply.challenge -cne $challengeHex -or
            [string]$reply.request_sha256 -cne (Get-ViewtvBrokerTestRequestDigest $Request) -or
            $reply.estado -cnotin @(
                'intencion_registrada_sin_publicar','replay_bloqueado',
                'requiere_revision','no_autorizada'
            ) -or $reply.publicacion_iniciada -isnot [bool] -or
            $reply.publicacion_iniciada) {
            throw 'Respuesta no vinculada a esta conexión.'
        }
        return [pscustomobject]@{
            estado=[string]$reply.estado
            publicacion_iniciada=$false
        }
    } catch {
        throw 'Autenticación de la respuesta del broker fallida.'
    }
}
