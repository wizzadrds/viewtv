# Sandbox 0018: retirada física de dos enlaces NTFS y reconciliación reversible.
# NO TIENE parámetros de ruta, IDs reales, ni modos de producción.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Importa las funciones de NTFS; la inicialización ejecuta solo auditoría
# de producción de 0016 (SIN borrar ni modificar nada en producción).
. (Join-Path $PSScriptRoot 'viewtv_windows_retirada_auditoria_0016.ps1') -Mode Audit |
    Out-Null

$parent=[IO.Path]::GetTempPath()
$root=[IO.Path]::Combine(
    $parent, 'viewtv-retirada-0018-ficticio-'+[Guid]::NewGuid().ToString('N'))
if([IO.Directory]::Exists($root)) { throw 'El sandbox ya existe.' }
$null=[IO.Directory]::CreateDirectory($root)
$source=[IO.Path]::Combine($root,'origen-ficticio.bin')
$dest=[IO.Path]::Combine($root,'publicado-ficticio.bin')
$extra=[IO.Path]::Combine($root,'tercer-enlace-ficticio.bin')
$journal=[IO.Path]::Combine($root,'diario-sandbox.json')

function Finger($Path) { return File-Fingerprint $Path }
function Assert-TwoLinks {
    $a=Finger $source
    $b=Finger $dest
    if($a.links -ne 2 -or $b.links -ne 2 -or
       $a.volume -ne $b.volume -or
       $a.high -ne $b.high -or $a.low -ne $b.low -or
       $a.bytes -ne $b.bytes) {
        throw 'No se verificaron dos enlaces exclusivos de ensayo.'
    }
}
function Assert-ThirdLink-Rejected {
    $a=Finger $source
    if($a.links -eq 2) {
        throw 'La prueba negativa no se ha configurado.'
    }
    if($a.links -ne 3) { throw 'Conteo ambiguo de enlaces.' }
    $thirdGuardDenied=$false
    try { Assert-TwoLinks } catch { $thirdGuardDenied=$true }
    if(-not $thirdGuardDenied) { throw 'Guardia de terceros ausente.' }
    Write-Output 'TERCER_HARDLINK_EXCLUIDO=PASS'
}
function Write-Sandbox-Journal([string]$State) {
    if($State -cnotin @('preparado','copia_retirada','restaurado','completado')) {
        throw 'Estado no admitido.'
    }
    [IO.File]::WriteAllText($journal,(
        [ordered]@{
            version=1
            caso='sandbox_0018'
            estado=$State
            origen='origen-ficticio.bin'
            publicado='publicado-ficticio.bin'
        } | ConvertTo-Json -Compress
    ),[Text.Encoding]::UTF8)
}
function Read-Sandbox-Journal {
    $entry=[IO.File]::ReadAllText($journal,[Text.Encoding]::UTF8)|ConvertFrom-Json
    if($entry.version -ne 1 -or $entry.caso -cne 'sandbox_0018' -or
       $entry.origen -cne 'origen-ficticio.bin' -or
       $entry.publicado -cne 'publicado-ficticio.bin') {
        throw 'Diario de sandbox no verificable.'
    }
    return $entry
}

try {
    $payload = New-Object byte[] (1024*1024)
    [IO.File]::WriteAllBytes($source,$payload)
    if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
        $dest,$source,[IntPtr]::Zero)) {
        throw 'No se pudo crear la copia ficticia por hardlink.'
    }
    Assert-TwoLinks

    # Abrir en exclusiva: no sería seguro borrar durante esta ventana.
    $handle=[IO.FileStream]::new($source,[IO.FileMode]::Open,
        [IO.FileAccess]::Read,[IO.FileShare]::None)
    try {
        $blocked=$false
        try { $null=Finger $dest } catch { $blocked=$true }
        if(-not $blocked) { throw 'Un archivo abierto no bloqueó el examen.' }
    } finally { $handle.Dispose() }
    Write-Output 'LECTOR_EXCLUSIVO_BLOQUEA=PASS'

    if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
        $extra,$source,[IntPtr]::Zero)) {
        throw 'No se pudo crear el tercer enlace ficticio.'
    }
    Assert-ThirdLink-Rejected
    # Nunca deshacer un enlace ajeno real: solo la tercera referencia
    # creada en este directorio GUID aislado.
    [IO.File]::Delete($extra)
    Assert-TwoLinks

    Write-Sandbox-Journal 'preparado'
    Assert-TwoLinks
    # Simula interrupción entre dos unlink, exclusivamente sandbox:
    [IO.File]::Delete($dest)
    if([IO.File]::Exists($dest) -or (Finger $source).links -ne 1) {
        throw 'El paso 1 no conservó el origen ficticio.'
    }
    Write-Sandbox-Journal 'copia_retirada'
    $checkpoint = Read-Sandbox-Journal
    if($checkpoint.estado -cne 'copia_retirada') {
        throw 'El diario no recuerda la operación interrumpida.'
    }
    # En este punto no se borró el último enlace: se puede cancelar
    # la retirada recreando la copia a partir del origen ficticio.
    if(-not [ViewtvLinkAudit0016]::CreateHardLinkW(
        $dest,$source,[IntPtr]::Zero)) {
        throw 'La conciliación ficticia no pudo recuperar la publicación.'
    }
    Assert-TwoLinks
    Write-Sandbox-Journal 'restaurado'
    Write-Output 'RECUPERACION_TRAS_INTERRUPCION=PASS'

    # Ejemplo de cierre: volvemos a verificar y eliminamos ambos
    # hardlinks SOLO de este sandbox único, nunca el original qBit.
    Assert-TwoLinks
    [IO.File]::Delete($dest)
    if((Finger $source).links -ne 1) {
        throw 'Antes del último unlink persistían enlaces no previstos.'
    }
    [IO.File]::Delete($source)
    if([IO.File]::Exists($source) -or [IO.File]::Exists($dest)) {
        throw 'Los dos nombres de ensayo no han desaparecido.'
    }
    Write-Sandbox-Journal 'completado'
    Write-Output 'RETIRADA_AMBAS_REFERENCIAS_SANDBOX=PASS'
    Write-Output 'FICHEROS_REALES_ELIMINADOS=0'
    Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
} finally {
    # Rutas constantes dentro del GUID recién creado por este proceso.
    # En ningún caso se llama a Remove-Item -Recurse ni se usa
    # C:\VIEWTV\media para escribir o borrar.
    foreach($item in @($extra,$dest,$source,$journal)) {
        if([IO.File]::Exists($item)) { [IO.File]::Delete($item) }
    }
    if([IO.Directory]::Exists($root)) {
        [IO.Directory]::Delete($root,$false)
    }
}
