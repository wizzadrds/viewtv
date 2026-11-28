"""0052: servicio Windows REAL aislado e inerte; nunca permiso de borrar.

Solo valida resultados categóricos de la auditoría Windows independiente.
El servicio no posee qBit, Jellyfin, ACL productivas ni unlink.
"""
from __future__ import annotations

PASS_0052 = (
    "BROKER_SID_DISTINTO_OPERADOR=PASS",
    "SERVICIO_MANUAL_Y_DETENIDO=PASS",
    "CARPETA_PRIVADA_MARCADA=PASS",
    "ACL_EXCLUSIVAS_ADMIN_SYSTEM_SERVICE=PASS",
    "BINARIO_SIN_WRITE_SERVICIO=PASS",
    "DIRECTORIO_DATOS_PRIVADO=PASS",
    "AUTO_PRUEBA_BROKER_SID_Y_PIPE=PASS",
    "BROKER_FUNCIONES_DE_BORRADO=NO",
    "TORRENTS_REALES_MODIFICADOS=0",
    "ARCHIVOS_REALES_ELIMINADOS=0",
)


class EvidenciaServicioNoConfiable(ValueError):
    """Una prueba de servicio inerte no puede autorizar películas."""


def validar_servicio_0052(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, str) or not 200 <= len(raw) <= 850:
        raise EvidenciaServicioNoConfiable("Informe inválido o demasiado grande.")
    if not raw.isascii() or "\x00" in raw or "\ufeff" in raw:
        raise EvidenciaServicioNoConfiable("Informe contiene datos privados.")
    normalized = raw.replace("\r\n", "\n")
    if "\r" in normalized or tuple(normalized.splitlines()) != PASS_0052:
        raise EvidenciaServicioNoConfiable("Instalación Windows no acreditada.")
    return PASS_0052


def evaluar_servicio_0052(first: object, second: object) -> dict[str, object]:
    reasons = {
        "broker_instalado_solo_con_salud_sin_acciones_de_medios",
        "qbit_gui_webui_y_torrents_sin_custodia_kernel",
        "jellyfin_hls_v2_y_drenaje_no_desplegados",
        "file_id_ntfs_exclusion_productiva_no_demostrada",
        "administrador_no_autorizo_pelicula_elegible",
        "servicio_manual_detenido_no_acepta_operaciones",
        "apagones_y_espacio_fisico_sin_prueba_productiva",
    }
    valid = 0
    for i, value in enumerate((first, second), 1):
        try:
            validar_servicio_0052(value)
            valid += 1
        except EvidenciaServicioNoConfiable:
            reasons.add(f"auditoria_{i}_no_verificable")
    return {
        "estado": "bloqueada",
        "auditorias_validas": valid,
        "auditorias_exigidas": 2,
        "sid_servicio_independiente_instalado": valid == 2,
        "acl_broker_privada_verificada": valid == 2,
        "broker_fisico_retirada_instalado": False,
        "cuenta_mantenimiento_autorizada": True,
        "permiso_de_borrado_otorgado": False,
        "puede_iniciar_unlink": False,
        "motivos": sorted(reasons),
    }
