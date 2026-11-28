"""0040: informes de WebUI qBit sin secretos y bloqueados por defecto."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from worker.retirement_qbit_webui_gate_0040 import (
    WebUiQbit0040NoVerificable,
    evaluar_webui_qbit_0040,
    parsear_webui_qbit_0040,
)

BASE = "\n".join((
    "QBIT_WEBUI_0040=OBSERVACION_SOLO_LECTURA",
    "QBIT_INSTANCIA_NATIVA_UNICA=SI",
    "QBIT_PROCESO_SID_OPERADOR=SI",
    "WEBUI_HABILITADA_CONFIG_OPERADOR=SI",
    "WEBUI_APIKEY_EN_CONFIG=SI",
    "WEBUI_PASSWORD_HASH_EN_CONFIG=SI",
    "QBIT_LISTENER_EXTERNO=SI",
    "QBIT_FIREWALL_ALLOW_AMPLIA=SI",
    "WEBUI_CONEXION_REMOTA_OBSERVADA=NO",
    "WEBUI_CONFIG_VINCULADA_A_PROCESO=NO_VERIFICADA",
    "BROKER_SECRETO_EXCLUSIVO=NO_VERIFICADO",
    "GUI_BLOQUEADA_PARA_REANUDAR=NO_VERIFICADA",
    "FILE_ID_SIN_ESCRITORES=NO_VERIFICADO",
    "PERMISO_DE_BORRADO_OTORGADO=NO",
    "ARCHIVOS_ELIMINADOS=0",
    "TORRENTS_MODIFICADOS=0",
))
FAIL = "\n".join((
    "QBIT_WEBUI_0040=INCOMPLETA",
    "BROKER_SECRETO_EXCLUSIVO=NO_VERIFICADO",
    "GUI_BLOQUEADA_PARA_REANUDAR=NO_VERIFICADA",
    "FILE_ID_SIN_ESCRITORES=NO_VERIFICADO",
    "PERMISO_DE_BORRADO_OTORGADO=NO",
    "ARCHIVOS_ELIMINADOS=0",
    "TORRENTS_MODIFICADOS=0",
    "CAUSA=EVIDENCIA_NO_DISPONIBLE",
))


def test_host_realista_bloqueado_pese_a_api_key_y_password():
    data = parsear_webui_qbit_0040(BASE)
    assert data["WEBUI_APIKEY_EN_CONFIG"] == "SI"
    assert data["WEBUI_PASSWORD_HASH_EN_CONFIG"] == "SI"
    decision = evaluar_webui_qbit_0040(BASE, BASE)
    assert decision["estado"] == "bloqueada"
    assert decision["custodia_exclusiva_qbit_verificada"] is False
    assert decision["permiso_de_borrado_otorgado"] is False
    assert "qbit_puerto_no_local" in decision["motivos"]
    assert "firewall_qbit_allow_amplio" in decision["motivos"]
    assert "gui_qbit_en_sid_operador" in decision["motivos"]
    assert "api_key_configurada_no_equivale_a_exclusividad" in decision["motivos"]


def test_incluso_webui_apagada_y_puertos_cerrados_no_prueba_exclusion():
    closed = BASE
    for key in (
        "WEBUI_HABILITADA_CONFIG_OPERADOR", "WEBUI_APIKEY_EN_CONFIG",
        "WEBUI_PASSWORD_HASH_EN_CONFIG", "QBIT_LISTENER_EXTERNO",
        "QBIT_FIREWALL_ALLOW_AMPLIA", "QBIT_PROCESO_SID_OPERADOR",
    ):
        closed = closed.replace(f"{key}=SI", f"{key}=NO")
    assert parsear_webui_qbit_0040(closed)
    result = evaluar_webui_qbit_0040(closed, closed)
    assert not result["puede_desplegar_borrado"]
    assert "gui_o_clientes_externos_sin_barrera_compartida" in result["motivos"]
    assert "permisos_ntfs_file_id_sin_exclusion" in result["motivos"]


def test_observacion_remota_es_evidencia_de_bypass_potencial():
    with_remote = BASE.replace(
        "WEBUI_CONEXION_REMOTA_OBSERVADA=NO",
        "WEBUI_CONEXION_REMOTA_OBSERVADA=SI",
    )
    result = evaluar_webui_qbit_0040(with_remote, with_remote)
    assert "sesion_webui_remota_detectada" in result["motivos"]
    assert result["permiso_de_borrado_otorgado"] is False


def test_dos_lecturas_diferentes_bloquean():
    changes = BASE.replace("QBIT_FIREWALL_ALLOW_AMPLIA=SI",
                           "QBIT_FIREWALL_ALLOW_AMPLIA=NO")
    assert "evidencia_webui_inestable" in evaluar_webui_qbit_0040(
        BASE, changes,
    )["motivos"]


def test_fallo_incompleto_esquema_canonico_y_bloquea():
    assert parsear_webui_qbit_0040(FAIL)["QBIT_WEBUI_0040"] == "INCOMPLETA"
    decision = evaluar_webui_qbit_0040(FAIL, FAIL)
    assert "auditoria_host_incompleta" in decision["motivos"]
    assert not decision["permiso_de_borrado_otorgado"]


@pytest.mark.parametrize("change", (
    lambda t: t + "\nWEBUI_APIKEY_EN_CONFIG=SI",
    lambda t: t + "\nCONFIG_APPCONFIG=C:\\usuario\\qbit.ini",
    lambda t: t + "\nAPIKEY=secreto",
    lambda t: t + "\nPASSWORD_PBKDF2=hashsensitivo",
    lambda t: t + "\nQBIT_SID=S-1-5-21-999",
    lambda t: t.replace("QBIT_INSTANCIA_NATIVA_UNICA=SI",
                        "QBIT_INSTANCIA_NATIVA_UNICA=NO"),
    lambda t: t.replace("QBIT_PROCESO_SID_OPERADOR=SI",
                        "QBIT_PROCESO_SID_OPERADOR=DESCONOCIDO"),
    lambda t: t.replace("GUI_BLOQUEADA_PARA_REANUDAR=NO_VERIFICADA",
                        "GUI_BLOQUEADA_PARA_REANUDAR=SI"),
    lambda t: t.replace("WEBUI_CONFIG_VINCULADA_A_PROCESO=NO_VERIFICADA",
                        "WEBUI_CONFIG_VINCULADA_A_PROCESO=SI"),
    lambda t: t.replace("BROKER_SECRETO_EXCLUSIVO=NO_VERIFICADO",
                        "BROKER_SECRETO_EXCLUSIVO=SI"),
    lambda t: t.replace("FILE_ID_SIN_ESCRITORES=NO_VERIFICADO",
                        "FILE_ID_SIN_ESCRITORES=SI"),
    lambda t: t.replace("PERMISO_DE_BORRADO_OTORGADO=NO",
                        "PERMISO_DE_BORRADO_OTORGADO=SI"),
    lambda t: t.replace("TORRENTS_MODIFICADOS=0", "TORRENTS_MODIFICADOS=1"),
    lambda t: t.replace("ARCHIVOS_ELIMINADOS=0", "ARCHIVOS_ELIMINADOS=1"),
    lambda t: t.replace("QBIT_LISTENER_EXTERNO=SI\n", ""),
    lambda t: t.replace("QBIT_WEBUI_0040=OBSERVACION_SOLO_LECTURA",
                        "QBIT_WEBUI_0040=AUTORIZADO"),
    lambda t: t.replace("WEBUI_APIKEY_EN_CONFIG=SI",
                        "WEBUI_APIKEY_EN_CONFIG=SI "),
    lambda t: t + "\r\n",
    lambda t: t + "\nAMIGO=ñ",
    lambda t: t + "x" * 5000,
))
def test_alteraciones_de_informe_rechazadas(change):
    result = change(BASE)
    with pytest.raises(WebUiQbit0040NoVerificable):
        parsear_webui_qbit_0040(result)
    decision = evaluar_webui_qbit_0040(result, BASE)
    assert "evidencia_webui_no_verificable" in decision["motivos"]
    assert decision["permiso_de_borrado_otorgado"] is False


@pytest.mark.parametrize("bad", (None, [], {}, 42, b"texto", "", object()))
def test_sin_informe_no_hay_permiso(bad):
    with pytest.raises(WebUiQbit0040NoVerificable):
        parsear_webui_qbit_0040(bad)
    assert not evaluar_webui_qbit_0040(bad, BASE)[
        "permiso_de_borrado_otorgado"
    ]


def test_fallo_incompleto_adulterado_no_se_acepta():
    with pytest.raises(WebUiQbit0040NoVerificable):
        parsear_webui_qbit_0040(
            FAIL.replace("CAUSA=EVIDENCIA_NO_DISPONIBLE",
                         "CAUSA=APROBADO")
        )


def _runner_module():
    source = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "viewtv_retirada_webui_qbit_0040.py"
    )
    spec = importlib.util.spec_from_file_location("viewtv_runner_0040", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_orquestador_no_emite_credenciales_y_bloquea(monkeypatch, capsys):
    runner = _runner_module()

    monkeypatch.setattr(runner, "_audit_windows", lambda: BASE)
    assert runner.main() == 0
    output = capsys.readouterr().out
    assert "ESTADO_RETIRADA_0040=BLOQUEADA" in output
    assert "PERMISO_DE_BORRADO_OTORGADO=NO" in output
    assert "ARCHIVOS_ELIMINADOS=0" in output
    assert "TORRENTS_MODIFICADOS=0" in output
    assert "secreto" not in output
    assert "APIKEY=" not in output


def test_orquestador_con_fallo_de_segunda_lectura_bloquea(monkeypatch, capsys):
    runner = _runner_module()

    calls = 0

    def read():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Sin acceso a host.")
        return BASE

    monkeypatch.setattr(runner, "_audit_windows", read)
    assert runner.main() == 2
    out = capsys.readouterr().out
    assert "RETIRADA_WEBUI_QBIT_0040=EVIDENCIA_INCOMPLETA" in out
    assert "PERMISO_DE_BORRADO_OTORGADO=NO" in out
    assert "Sin acceso a host" not in out
