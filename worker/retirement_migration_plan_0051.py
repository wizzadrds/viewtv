"""0051: inventario host en 3 superficies para planificar SID broker, SOLO LECTURA.

No despliega, modifica, borra ni autoriza. Nunca registra SIDs, IPs,
puertos exactos, claves, rutas de medios ni nombres de perfiles.
"""
from __future__ import annotations

from collections.abc import Mapping

from worker.retirement_external_gate_0033 import parsear_accesos_0033
from worker.retirement_qbit_webui_gate_0040 import parsear_webui_qbit_0040
from worker.retirement_sid_gate_0037 import parsear_auditoria_sids_0037

SOURCES = ("0033", "0037", "0040")
PARSERS = {
    "0033": parsear_accesos_0033,
    "0037": parsear_auditoria_sids_0037,
    "0040": parsear_webui_qbit_0040,
}
EXPECTED_STATUS = {
    "0033": ("ACCESOS_EXTERNOS_0033", "AUDITORIA_SOLO_LECTURA"),
    "0037": ("SIDS_WINDOWS_0037", "OBSERVADOS_SOLO_LECTURA"),
    "0040": ("QBIT_WEBUI_0040", "OBSERVACION_SOLO_LECTURA"),
}
PHASES = (
    "01_inventario_y_reversion",
    "02_broker_sid_no_interactivo_y_clave_segregada",
    "03_cierre_gui_webui_qbit_con_excepciones",
    "04_acl_ntfs_y_prueba_tercer_hardlink",
    "05_jellyfin_hls_v2_y_drenaje",
    "06_ensayo_recuperacion_y_autorizacion_por_pelicula",
)
PERMANENT = frozenset({
    "sin_aprobacion_explicita_de_mantenimiento",
    "broker_sid_independiente_no_instalado",
    "qbit_exclusividad_no_demostrada",
    "jellyfin_hls_y_drenaje_no_demostrados",
    "acl_file_id_ntfs_no_demostrada",
    "aprobacion_admin_pelicula_no_consumida",
    "recuperacion_y_espacio_fisico_no_verificados",
})


def _validar_pareja(name: str, pair: object) -> dict[str, str]:
    if (
        not isinstance(pair, (tuple, list))
        or len(pair) != 2
        or not all(isinstance(item, str) for item in pair)
    ):
        raise ValueError("Informe ausente o tipo no autorizado.")
    parser = PARSERS[name]
    before = parser(pair[0].replace("\r\n", "\n"))
    after = parser(pair[1].replace("\r\n", "\n"))
    if before != after:
        raise ValueError("Las dos observaciones no son iguales.")
    key, expected = EXPECTED_STATUS[name]
    if after[key] != expected:
        raise ValueError("Informe host incompleto.")
    return after


def planificar_aislamiento_0051(
    reports: Mapping[str, object] | object,
) -> dict[str, object]:
    """Evidencia cerrada de 0033,0037,0040; jamás implica luz verde."""
    reasons = set(PERMANENT)
    observed: dict[str, dict[str, str]] = {}
    if not isinstance(reports, Mapping) or set(reports) != set(SOURCES):
        reasons.add("inventario_fuentes_incompleto")
    else:
        for name in SOURCES:
            try:
                observed[name] = _validar_pareja(name, reports[name])
            except (ValueError, KeyError, TypeError):
                reasons.add(f"auditoria_{name}_no_verificable")

    sid = observed.get("0037")
    qbit = observed.get("0040")
    network = observed.get("0033")

    if sid:
        for field, reason in (
            ("QBIT_COMPARTE_SID_OPERADOR", "qbit_comparte_sid_operador"),
            ("JELLYFIN_COMPARTE_SID_OPERADOR", "jellyfin_comparte_sid_operador"),
            ("PUBLICADOR_COMPARTE_SID_OPERADOR", "publicador_comparte_sid_operador"),
        ):
            if sid[field] == "SI":
                reasons.add(reason)
            elif sid[field] == "DESCONOCIDO":
                reasons.add("identidad_proceso_no_verificada")
        if sid["DIRECTORIOS_RAIZ_ACL_PROTEGIDAS"] != "4_DE_4":
            reasons.add("herencia_acl_raices_pendiente")
        if sid["CUENTAS_EFIMERAS_SIN_LIMPIAR"] != "0":
            reasons.add("cuentas_temporales_sin_limpiar")
        if sid["OPERADOR_ADMIN_ELEVADO"] == "SI":
            reasons.add("operador_elevado_no_es_servicio_aislado")

    if qbit:
        for field, reason in (
            ("QBIT_PROCESO_SID_OPERADOR", "qbit_comparte_sid_operador"),
            ("WEBUI_HABILITADA_CONFIG_OPERADOR", "webui_config_operador_habilitada"),
            ("QBIT_LISTENER_EXTERNO", "qbit_listener_externo"),
            ("QBIT_FIREWALL_ALLOW_AMPLIA", "qbit_firewall_amplio"),
        ):
            if qbit[field] == "SI":
                reasons.add(reason)
        # La presencia de clave NO prueba exclusividad del broker:
        # no mostrar siquiera sus valores ni hashes.
        if qbit["WEBUI_APIKEY_EN_CONFIG"] == "SI":
            reasons.add("api_key_en_config_no_es_exclusividad")
        if qbit["WEBUI_PASSWORD_HASH_EN_CONFIG"] == "SI":
            reasons.add("password_configurada_no_es_exclusividad")
        if qbit["WEBUI_CONEXION_REMOTA_OBSERVADA"] == "SI":
            reasons.add("sesion_webui_remota_observada")

    if network:
        for field, reason in (
            ("QBIT_ESCUCHA_EXTERNA", "qbit_listener_externo"),
            ("QBIT_FIREWALL_ALLOW", "qbit_firewall_amplio"),
            ("JELLYFIN_NATIVO_ESCUCHA_EXTERNA", "jellyfin_listener_externo"),
            ("JELLYFIN_FIREWALL_ALLOW", "jellyfin_firewall_amplio"),
        ):
            if network[field] == "SI":
                reasons.add(reason)
        if network["DOCKER_JELLYFIN_SOLO_LOCAL"] != "SI":
            reasons.add("docker_jellyfin_no_aislado_o_no_verificado")

    cross_conflict = bool(
        sid and qbit
        and sid["QBIT_COMPARTE_SID_OPERADOR"] != "DESCONOCIDO"
        and sid["QBIT_COMPARTE_SID_OPERADOR"]
        != qbit["QBIT_PROCESO_SID_OPERADOR"]
    )
    if cross_conflict:
        reasons.add("identidad_qbit_contradictoria_entre_fuentes")
    # No igualar la prueba de listener de 0033 (wildcard) y 0040
    # (cualquier dirección no loopback), pues NO usan la misma definición.

    return {
        "estado": "bloqueada",
        "inventario_completo": len(observed) == 3 and not cross_conflict,
        "fuentes_validas": len(observed),
        "fuentes_exigidas": 3,
        "fases": PHASES,
        "modificaciones_efectuadas": False,
        "mantenimiento_autorizado": False,
        "puede_instalar_broker": False,
        "puede_desplegar_borrado": False,
        "autoriza_borrado_fisico": False,
        "motivos": sorted(reasons),
    }
