# VIEWTV 0022: MUTEX Windows compartido, sin operaciones sobre medios.
# Publicador y futuro retirador deben adquirir ESTE MISMO nombre en Global\.
# Exclusion es obligatoria para el codigo fuente 0022 del publicador;
# el proceso de produccion NO queda actualizado solo por agregar este archivo.
Set-StrictMode -Version Latest

function Enter-ViewtvMediaExclusion0022 {
    [CmdletBinding()]
    param(
        [ValidateSet('publicador','retirada','sandbox')]
        [string]$Proposito,
        [string]$SandboxId=''
    )
    if ($Proposito -ceq 'sandbox') {
        if ($SandboxId -cnotmatch '^[a-f0-9]{32}$') {
            throw 'El mutex ficticio requiere GUID de sandbox.'
        }
        $name='Global\VIEWTV-MEDIA-SANDBOX-0022-'+$SandboxId
    } else {
        if ($SandboxId -ne '') {
            throw 'No se admiten variantes del mutex de produccion.'
        }
        $name='Global\VIEWTV-MEDIA-EXCLUSIVA-PUBLICACION-RETIRADA-0022'
    }
    $mutex=$null
    $owned=$false
    try {
        $mutex=[Threading.Mutex]::new($false,$name)
        try {
            $owned=$mutex.WaitOne(0)
        } catch [Threading.AbandonedMutexException] {
            # El proceso anterior murio manteniendo la exclusion:
            # liberarla y ABORTAR para revision. No seguir operando.
            $mutex.ReleaseMutex()
            throw 'Mutex abandonado: revisar ultima transaccion.'
        }
        if (-not $owned) {
            throw 'Otro proceso ocupa la exclusion de medios.'
        }
        return $mutex
    } catch {
        if($mutex -ne $null) { $mutex.Dispose() }
        throw
    }
}

function Exit-ViewtvMediaExclusion0022 {
    [CmdletBinding()]
    param([Parameter(Mandatory)][Threading.Mutex]$Mutex)
    try {
        $Mutex.ReleaseMutex()
    } finally {
        $Mutex.Dispose()
    }
}
