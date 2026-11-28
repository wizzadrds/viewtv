# VIEWTV 0037: prueba automatizada de SIDs reales en laboratorio GUID.
# Requiere consentimiento explícito para cuentas LOCALES EFÍMERAS del ensayo.
# Jamás toca ACL de medios reales, tareas, servicios o torrents.
[CmdletBinding()]
param([switch]$AutorizarCuentasEfimeras)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not $AutorizarCuentasEfimeras) {
    throw 'Sin autorización para crear dos cuentas temporales de ensayo.'
}
$inner=Join-Path $PSScriptRoot 'test_viewtv_windows_distinct_sids_sandbox.ps1'
if(-not [IO.File]::Exists($inner) -or
   ([IO.FileInfo]::new($inner).Attributes -band
    [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'Falta el ensayo de identidades reales.'
}
$oldAccounts=@(Get-LocalUser -ErrorAction Stop | Where-Object {
    $_.Description -ceq 'VIEWTV-0013-EPHEMERAL'
})
if($oldAccounts.Count -ne 0) {
    throw 'Existen identidades temporales antiguas; no se continúa.'
}
$expected=[ordered]@{
    dos_sids_no_administrativos='verificado'
    vault_y_destino_privados='copia_denegada'
    copia_no_lee_ni_altera_registro='denegada'
    broker_real_lee_sid_privado='verificado'
    gate_antes_de_sellado='rechazado'
    gate_ace_lectura_sid_real='rechazada'
    gate_acls_selladas='correcto'
    copia_sellada='escritura_denegada'
    gate_escrow_privado='correcto'
    handoff_con_broker_real='correcto'
    gate_destino_publicado='correcto'
    publicacion_sin_modificacion='correcto'
    escritor_preabierto='bloquea_move'
    cierre_voluntario='move_correcto'
    lector_lee_sin_escribir_en_directorio_sellado='PASS'
    lector_crea_link_desde_directorio_propio='DENEGADO'
    broker_distinto_sid_crea_link_de_ensayo='PASS'
    lector_no_relink_durante_handles_delete='PASS'
    doble_unlink_broker_sid_aislado='PASS'
    ninguna_acl_ni_cuenta_productiva_modificada='SI'
}
$testFailed=$false
try {
    # Evitar el segundo PowerShell con una tubería de salida; ejecutar
    # el script comprobado en el mismo proceso, una sola vez.
    $output=@(& $inner -AuthorizeEphemeralAccounts)
    if($output.Count -ne 1) {
        throw 'El laboratorio SID finalizó con error o salida inesperada.'
    }
    $result=[string]$output[0] | ConvertFrom-Json -ErrorAction Stop
    $names=@($result.PSObject.Properties.Name)
    if($names.Count -ne $expected.Count) {
        throw 'El contrato SID de laboratorio cambió.'
    }
    foreach($key in $expected.Keys) {
        if($names -cnotcontains $key -or
           [string]$result.$key -cne [string]$expected[$key]) {
            throw 'La verificación de una barrera SID falló.'
        }
    }
} catch {
    $testFailed=$true
}
$remaining=@(Get-LocalUser -ErrorAction Stop | Where-Object {
    $_.Description -ceq 'VIEWTV-0013-EPHEMERAL'
})
if($remaining.Count -ne 0) {
    throw 'Quedaron cuentas de laboratorio; revisión manual necesaria.'
}
if($testFailed) {
    throw 'No se satisfizo una de las barreras SID/NTFS de laboratorio.'
}
Write-Output 'SIDS_DISTINTOS_NO_ADMINISTRADORES=PASS'
Write-Output 'LECTOR_PUEDE_LEER_ARCHIVO=PASS'
Write-Output 'LECTOR_NO_CREAR_HARDLINK_EN_DIRECTORIO_PROPIO=PASS'
Write-Output 'LECTOR_NO_CREAR_HARDLINK_DURANTE_COMMIT=PASS'
Write-Output 'BROKER_DISTINTO_SID_DOS_UNLINKS_FICTICIOS=PASS'
Write-Output 'CUENTAS_TEMPORALES_REVERTIDAS=PASS'
Write-Output 'PERMISOS_PRODUCTIVOS_MODIFICADOS=NO'
Write-Output 'EJECUTOR_PRODUCTIVO_INSTALADO=NO'
Write-Output 'PERMISO_DE_BORRADO_OTORGADO=NO'
Write-Output 'ARCHIVOS_REALES_ELIMINADOS=0'
Write-Output 'TORRENTS_REALES_MODIFICADOS=0'
