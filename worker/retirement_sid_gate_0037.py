"""0037: evaluar evidencia de aislamiento Windows sin conceder borrado.

El inventario Windows indica si las identidades comparten SID, pero no
permite certificar que el mismo File ID NTFS esté inmovilizado frente a
escritores, privilegios, grupos y handles antiguos. Por tanto se bloquea
incluso cuando no se detecta coincidencia de SIDs.
No hay efectos de red, disco o procesos.
"""
from __future__ import annotations

import re

OBSERVED = "OBSERVADOS_SOLO_LECTURA"
INCOMPLETE = "EVIDENCIA_INCOMPLETA"
STATUS = "SIDS_WINDOWS_0037"
SIDS = frozenset({
    "OPERADOR_ADMIN_ELEVADO",
    "JELLYFIN_COMPARTE_SID_OPERADOR",
    "QBIT_COMPARTE_SID_OPERADOR",
    "PUBLICADOR_COMPARTE_SID_OPERADOR",
})
STATIC = {
    "BROKER_SID_DISTINTO_EN_PRODUCCION": "NO_VERIFICADO",
    "LECTORES_SIN_FILE_WRITE_ATTRIBUTES_EN_PRODUCCION": "NO_VERIFICADO",
    "AISLAMIENTO_KERNEL_ARCHIVOS_PRODUCCION": "NO_VERIFICADO",
    "RETIRADA_POR_SIDS_PREPARADA": "NO",
    "PERMISO_DE_BORRADO_OTORGADO": "NO",
    "ARCHIVOS_REALES_ELIMINADOS": "0",
    "TORRENTS_REALES_MODIFICADOS": "0",
}
INCOMPLETE_STATIC = {
    STATUS: INCOMPLETE,
    "RETIRADA_POR_SIDS_PREPARADA": "NO",
    "AISLAMIENTO_KERNEL_ARCHIVOS_PRODUCCION": "NO_VERIFICADO",
    "PERMISO_DE_BORRADO_OTORGADO": "NO",
    "ARCHIVOS_REALES_ELIMINADOS": "0",
    "TORRENTS_REALES_MODIFICADOS": "0",
}
EXPECTED = SIDS | frozenset(STATIC) | {
    STATUS, "DIRECTORIOS_RAIZ_ACL_PROTEGIDAS",
    "CUENTAS_EFIMERAS_SIN_LIMPIAR",
}


class SidsNoVerificables(ValueError):
    """El origen no demuestra ninguna condición de aislamiento."""


def parsear_auditoria_sids_0037(raw: object) -> dict[str, str]:
    """Solo admite indicadores del contrato, nunca rutas, hashes ni SIDs."""
    if not isinstance(raw, str) or not 75 <= len(raw) <= 2048:
        raise SidsNoVerificables("Longitud de informe inválida.")
    if not raw.isascii() or "\x00" in raw or "\r" in raw:
        raise SidsNoVerificables("Informe de SIDs no público o no normalizado.")
    result: dict[str, str] = {}
    for line in raw.splitlines():
        if not line or line.count("=") != 1:
            raise SidsNoVerificables("Línea de auditoría inválida.")
        key, value = line.split("=", 1)
        if (
            not key.isascii() or not value.isascii()
            or not key or not value or value != value.strip()
            or len(value) > 40 or key in result
        ):
            raise SidsNoVerificables("Clave o valor no aceptado.")
        result[key] = value

    if result.get(STATUS) == INCOMPLETE:
        if result != INCOMPLETE_STATIC:
            raise SidsNoVerificables("Fallo cerrado no canónico.")
        return result

    if result.get(STATUS) != OBSERVED or set(result) != EXPECTED:
        raise SidsNoVerificables("Informe de identidades incompleto.")
    if any(result[k] not in {"SI", "NO", "DESCONOCIDO"} for k in SIDS):
        raise SidsNoVerificables("Estado de SID desconocido.")
    if any(result[k] != value for k, value in STATIC.items()):
        raise SidsNoVerificables("El host se autocertifica sin prueba kernel.")
    if re.fullmatch(r"[0-4]_DE_4", result[
        "DIRECTORIOS_RAIZ_ACL_PROTEGIDAS"
    ]) is None:
        raise SidsNoVerificables("Estado de ACL de raíz inválido.")
    number = result["CUENTAS_EFIMERAS_SIN_LIMPIAR"]
    if (
        re.fullmatch(r"(?:0|[1-9][0-9]?)", number) is None
        or int(number) > 99
    ):
        raise SidsNoVerificables("Número de cuentas no verificable.")
    return result


def evaluar_aislamiento_sids_0037(
    primera: object, segunda: object,
) -> dict[str, object]:
    """Falla cerrado para cualquier estado, incluida ausencia aparente de SIDs."""
    issues: set[str] = {
        "broker_sid_productivo_no_enrolado",
        "permisos_kernel_por_file_id_no_demostrados",
        "custodia_qbit_y_drenaje_jellyfin_fuera_de_alcance",
        "autorizacion_administrativa_no_consumida",
    }
    try:
        left = parsear_auditoria_sids_0037(primera)
        right = parsear_auditoria_sids_0037(segunda)
        if left != right:
            issues.add("auditorias_windows_distintas")
        if right[STATUS] != OBSERVED:
            issues.add("estado_host_incompleto")
        else:
            for key, reason in (
                ("JELLYFIN_COMPARTE_SID_OPERADOR", "jellyfin_sin_segregar"),
                ("QBIT_COMPARTE_SID_OPERADOR", "qbittorrent_sin_segregar"),
                ("PUBLICADOR_COMPARTE_SID_OPERADOR", "publicador_sin_segregar"),
            ):
                if right[key] == "SI":
                    issues.add(reason)
                if right[key] == "DESCONOCIDO":
                    issues.add("dueño_de_proceso_no_verificado")
            if right["DIRECTORIOS_RAIZ_ACL_PROTEGIDAS"] != "4_DE_4":
                issues.add("herencia_acl_de_raices_no_sellada")
            if int(right["CUENTAS_EFIMERAS_SIN_LIMPIAR"]) != 0:
                issues.add("cuentas_de_laboratorio_pendientes")
    except (SidsNoVerificables, TypeError, ValueError, KeyError):
        issues.add("evidencia_sids_no_verificable")
    return {
        "estado": "bloqueada",
        "aislamiento_de_lectores_verificado": False,
        "permiso_de_borrado_otorgado": False,
        "motivos": sorted(issues),
    }
