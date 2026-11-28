"""0033: evaluación conservadora de exposición externa (SOLO LECTURA).

Acepta dos informes públicos mínimos del auditor Windows 0033; nunca
concede permisos de retirada. Es una comprobación de consistencia, NO una
prueba de quietud: los puertos, reglas de firewall y estados de procesos no
sustituyen el control kernel de handles/NTFS ni la custodia de qBittorrent.
No consulta ni escribe servicios, discos, perfiles, medios o torrents.
"""
from __future__ import annotations

_STATUS = "ACCESOS_EXTERNOS_0033"
_FLAGS = frozenset({
    "JELLYFIN_NATIVO_ESCUCHA_EXTERNA",
    "JELLYFIN_FIREWALL_ALLOW",
    "QBIT_ESCUCHA_EXTERNA",
    "QBIT_FIREWALL_ALLOW",
    "DOCKER_JELLYFIN_SOLO_LOCAL",
})
_BLOCKERS = frozenset({
    "NTFS_EXCLUSION_KERNEL", "CUSTODIA_QBIT", "DRENAJE_EXTERNO",
})
_REQUIRED = _FLAGS | _BLOCKERS | {
    _STATUS, "PERMISO_DE_BORRADO_OTORGADO", "ARCHIVOS_ELIMINADOS",
    "TORRENTS_MODIFICADOS",
}
_STATES = frozenset({"SI", "NO", "DESCONOCIDO"})
_MAX_BYTES = 4096


def parsear_accesos_0033(texto: object) -> dict[str, str]:
    """Rechaza duplicados, campos extra, datos no públicos y salida parcial."""
    if not isinstance(texto, str) or not 80 <= len(texto) <= _MAX_BYTES:
        raise ValueError("Informe externo ausente o demasiado grande.")
    if not texto.isascii() or "\r" in texto or "\x00" in texto:
        raise ValueError("Informe externo con caracteres no válidos.")
    fields: dict[str, str] = {}
    for line in texto.splitlines():
        if not line or line.count("=") != 1:
            raise ValueError("Estructura de auditoría inesperada.")
        key, value = line.split("=", 1)
        if key not in _REQUIRED | {"CAUSA"} or key in fields:
            raise ValueError("Campo externo duplicado o desconocido.")
        if not value or len(value) > 80 or value.strip() != value:
            raise ValueError("Valor de auditoría inválido.")
        fields[key] = value

    if not _REQUIRED.issubset(fields):
        raise ValueError("Faltan condiciones de auditoría.")
    state = fields[_STATUS]
    if state not in {"AUDITORIA_SOLO_LECTURA", "INCOMPLETO"}:
        raise ValueError("Origen de auditoría no confiable.")
    if (state == "INCOMPLETO") != (
        fields.get("CAUSA") == "EVIDENCIA_NO_DISPONIBLE"
    ):
        raise ValueError("La auditoría incompleta no tiene causa verificable.")
    if any(fields[k] not in _STATES for k in _FLAGS):
        raise ValueError("Estado de acceso externo inválido.")
    if any(
        fields[k] not in {"NO_VERIFICADA", "NO_VERIFICADO"} for k in _BLOCKERS
    ):
        raise ValueError("Autocertificación no admitida como prueba kernel.")
    if (
        fields["PERMISO_DE_BORRADO_OTORGADO"] != "NO"
        or fields["ARCHIVOS_ELIMINADOS"] != "0"
        or fields["TORRENTS_MODIFICADOS"] != "0"
    ):
        raise ValueError("La fuente afirma cambios o permisos indebidos.")
    if state == "INCOMPLETO" and any(
        fields[k] != "DESCONOCIDO" for k in _FLAGS
    ):
        raise ValueError("La auditoría incompleta declara datos no verificados.")
    return fields


def evaluar_accesos_externos_0033(
    anterior: object, posterior: object,
) -> dict[str, object]:
    """Dos observaciones; ninguna combinación equivale a permiso de borrar.

    Solo devuelve categorías de bloqueo sin filtrar IPs, rutas o hashes.
    La autorización final exige un guardián real y revalidación atómica.
    """
    motivos: set[str] = set()
    try:
        left = parsear_accesos_0033(anterior)
        right = parsear_accesos_0033(posterior)
        if left != right:
            motivos.add("evidencias_cambiantes")
        if right[_STATUS] != "AUDITORIA_SOLO_LECTURA":
            motivos.add("fuente_externa_incompleta")
        for key, reason in (
            ("JELLYFIN_NATIVO_ESCUCHA_EXTERNA", "jellyfin_nativo_expuesto"),
            ("JELLYFIN_FIREWALL_ALLOW", "firewall_jellyfin_permisivo"),
            ("QBIT_ESCUCHA_EXTERNA", "qbittorrent_expuesto"),
            ("QBIT_FIREWALL_ALLOW", "firewall_qbittorrent_permisivo"),
        ):
            if right[key] == "SI":
                motivos.add(reason)
            elif right[key] == "DESCONOCIDO":
                motivos.add("observacion_externa_incompleta")
        if right["DOCKER_JELLYFIN_SOLO_LOCAL"] != "SI":
            motivos.add("docker_jellyfin_no_aislado_o_no_verificado")
    except (ValueError, TypeError, KeyError):
        motivos.add("evidencia_externa_no_verificable")

    # Ni puertos ni firewall prueban bloqueo de handles por File ID o
    # ausencia de reanudación de torrents; ninguna vía autoriza borrado.
    motivos.update((
        "ntfs_exclusion_kernel_pendiente",
        "custodia_qbittorrent_pendiente",
        "drenaje_externo_pendiente",
        "autorizacion_administrativa_no_evaluada",
    ))
    return {
        "estado": "bloqueada",
        "permiso_de_borrado_otorgado": False,
        "puede_retirar_archivos": False,
        "motivos": sorted(motivos),
    }
