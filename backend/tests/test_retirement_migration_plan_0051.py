"""0051: plan de migración realista sin permiso, sin IPs, cuentas o secretos."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from worker.retirement_external_gate_0033 import _BLOCKERS, _FLAGS
from worker.retirement_migration_plan_0051 import (
    PERMANENT,
    PHASES,
    SOURCES,
    planificar_aislamiento_0051,
)
from worker.retirement_qbit_webui_gate_0040 import FIXED as WEBUI_FIXED
from worker.retirement_qbit_webui_gate_0040 import YES_NO as WEBUI_FLAGS
from worker.retirement_sid_gate_0037 import SIDS
from worker.retirement_sid_gate_0037 import STATIC as SID_FIXED


def encoded(data):
    return "\n".join(f"{k}={v}" for k, v in sorted(data.items())) + "\n"


def sid(**changes):
    info = {
        "SIDS_WINDOWS_0037": "OBSERVADOS_SOLO_LECTURA",
        "DIRECTORIOS_RAIZ_ACL_PROTEGIDAS": "4_DE_4",
        "CUENTAS_EFIMERAS_SIN_LIMPIAR": "0",
        **SID_FIXED,
        **{name: "NO" for name in SIDS},
        **changes,
    }
    return encoded(info)


def net(**changes):
    info = {
        "ACCESOS_EXTERNOS_0033": "AUDITORIA_SOLO_LECTURA",
        "PERMISO_DE_BORRADO_OTORGADO": "NO",
        "ARCHIVOS_ELIMINADOS": "0",
        "TORRENTS_MODIFICADOS": "0",
        **{name: "NO_VERIFICADO" if name != "DRENAJE_EXTERNO"
           else "NO_VERIFICADO" for name in _BLOCKERS},
        **{name: "NO" for name in _FLAGS},
        "DOCKER_JELLYFIN_SOLO_LOCAL": "SI",
        **changes,
    }
    # El contrato diferencia estado NO_VERIFICADA de NTFS.
    info["NTFS_EXCLUSION_KERNEL"] = "NO_VERIFICADA"
    return encoded(info)


def web(**changes):
    info = {
        "QBIT_WEBUI_0040": "OBSERVACION_SOLO_LECTURA",
        **WEBUI_FIXED,
        **{name: "NO" for name in WEBUI_FLAGS},
        "QBIT_INSTANCIA_NATIVA_UNICA": "SI",
        **changes,
    }
    return encoded(info)


def all_reports(*, s=None, q=None, n=None):
    values = {"0033": n or net(), "0037": s or sid(), "0040": q or web()}
    return {name: (value, value) for name, value in values.items()}


def test_tres_auditorias_con_configuracion_ideal_tampoco_autorizan():
    out = planificar_aislamiento_0051(all_reports())
    assert out["estado"] == "bloqueada"
    assert out["inventario_completo"] is True, out["motivos"]
    assert out["fuentes_validas"] == 3
    assert out["fuentes_exigidas"] == 3
    assert out["fases"] == PHASES
    assert len(out["fases"]) == 6
    assert PERMANENT.issubset(out["motivos"])
    for flag in (
        "modificaciones_efectuadas", "mantenimiento_autorizado",
        "puede_instalar_broker", "puede_desplegar_borrado",
        "autoriza_borrado_fisico",
    ):
        assert out[flag] is False


@pytest.mark.parametrize("value,expected", (
    (sid(QBIT_COMPARTE_SID_OPERADOR="SI"), "qbit_comparte_sid_operador"),
    (sid(JELLYFIN_COMPARTE_SID_OPERADOR="SI"), "jellyfin_comparte_sid_operador"),
    (sid(PUBLICADOR_COMPARTE_SID_OPERADOR="SI"), "publicador_comparte_sid_operador"),
    (sid(QBIT_COMPARTE_SID_OPERADOR="DESCONOCIDO"), "identidad_proceso_no_verificada"),
    (sid(DIRECTORIOS_RAIZ_ACL_PROTEGIDAS="1_DE_4"), "herencia_acl_raices_pendiente"),
    (sid(CUENTAS_EFIMERAS_SIN_LIMPIAR="3"), "cuentas_temporales_sin_limpiar"),
    (sid(OPERADOR_ADMIN_ELEVADO="SI"), "operador_elevado_no_es_servicio_aislado"),
))
def test_aislamiento_sid_detecta_los_bloqueos(value, expected):
    reports = all_reports(s=value)
    # Para una fuente 0037 alterada se conserva la relación con 0040
    # en todos los casos excepto cuando el SID qBit pasa a SI.
    if "QBIT_COMPARTE_SID_OPERADOR=SI" in value:
        reports = all_reports(s=value, q=web(QBIT_PROCESO_SID_OPERADOR="SI"))
    out = planificar_aislamiento_0051(reports)
    assert expected in out["motivos"]
    assert out["autoriza_borrado_fisico"] is False


@pytest.mark.parametrize("value,expected", (
    (web(QBIT_PROCESO_SID_OPERADOR="SI"), "qbit_comparte_sid_operador"),
    (web(WEBUI_HABILITADA_CONFIG_OPERADOR="SI"), "webui_config_operador_habilitada"),
    (web(QBIT_LISTENER_EXTERNO="SI"), "qbit_listener_externo"),
    (web(QBIT_FIREWALL_ALLOW_AMPLIA="SI"), "qbit_firewall_amplio"),
    (web(WEBUI_APIKEY_EN_CONFIG="SI"), "api_key_en_config_no_es_exclusividad"),
    (web(WEBUI_PASSWORD_HASH_EN_CONFIG="SI"), "password_configurada_no_es_exclusividad"),
    (web(WEBUI_CONEXION_REMOTA_OBSERVADA="SI"), "sesion_webui_remota_observada"),
))
def test_webui_detecta_atajos_externos_y_no_presume_secretos(value, expected):
    reports = all_reports(q=value)
    if "QBIT_PROCESO_SID_OPERADOR=SI" in value:
        reports = all_reports(q=value, s=sid(QBIT_COMPARTE_SID_OPERADOR="SI"))
    out = planificar_aislamiento_0051(reports)
    assert expected in out["motivos"]
    assert not out["puede_instalar_broker"]
    assert "SECRET" not in repr(out)


@pytest.mark.parametrize("value,expected", (
    (net(QBIT_ESCUCHA_EXTERNA="SI"), "qbit_listener_externo"),
    (net(QBIT_FIREWALL_ALLOW="SI"), "qbit_firewall_amplio"),
    (net(JELLYFIN_NATIVO_ESCUCHA_EXTERNA="SI"), "jellyfin_listener_externo"),
    (net(JELLYFIN_FIREWALL_ALLOW="SI"), "jellyfin_firewall_amplio"),
    (net(DOCKER_JELLYFIN_SOLO_LOCAL="NO"), "docker_jellyfin_no_aislado_o_no_verificado"),
))
def test_superficies_externas_se_planifican_sin_aplicar_firewall(value, expected):
    out = planificar_aislamiento_0051(all_reports(n=value))
    assert expected in out["motivos"]
    assert out["modificaciones_efectuadas"] is False


def test_si_0033_informa_wildcard_y_0040_no_no_se_infiere_certidumbre():
    out = planificar_aislamiento_0051(
        all_reports(n=net(QBIT_ESCUCHA_EXTERNA="SI"))
    )
    assert "qbit_listener_externo" in out["motivos"]
    assert out["inventario_completo"] is True
    assert out["autoriza_borrado_fisico"] is False


def test_sid_qbit_cruzado_con_0040_distinto_se_detecta():
    out = planificar_aislamiento_0051(
        all_reports(s=sid(QBIT_COMPARTE_SID_OPERADOR="SI"))
    )
    assert "identidad_qbit_contradictoria_entre_fuentes" in out["motivos"]
    assert out["inventario_completo"] is False
    assert out["estado"] == "bloqueada"


@pytest.mark.parametrize("source", SOURCES)
def test_lecturas_diferentes_dentro_de_una_fuente_fallan(source):
    reports = all_reports()
    reports[source] = (reports[source][0], reports[source][0] + "\n")
    # Un salto final adicional es semánticamente equivalente para parser:
    # usar un cambio genuino del dato, siempre conservando sintaxis válida.
    changes = {
        "0033": net(QBIT_FIREWALL_ALLOW="SI"),
        "0037": sid(DIRECTORIOS_RAIZ_ACL_PROTEGIDAS="1_DE_4"),
        "0040": web(QBIT_LISTENER_EXTERNO="SI"),
    }
    reports[source] = (reports[source][0], changes[source])
    out = planificar_aislamiento_0051(reports)
    assert out["fuentes_validas"] == 2
    assert f"auditoria_{source}_no_verificable" in out["motivos"]
    assert not out["inventario_completo"]


@pytest.mark.parametrize("source", SOURCES)
def test_informe_crlf_windows_normalizado_y_verificado(source):
    reports = all_reports()
    reports[source] = (
        reports[source][0],
        reports[source][0].replace("\n", "\r\n"),
    )
    out = planificar_aislamiento_0051(reports)
    assert out["inventario_completo"] is True
    assert not out["autoriza_borrado_fisico"]


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("corruption", (
    lambda raw: raw + "SECRET=redactado\n",
    lambda raw: raw.replace("\n", "\r", 1),
    lambda raw: raw + "BROKER_PRODUCTIVO_INSTALADO=SI\n",
    lambda raw: raw + "SID=S-1-5-21-1\n",
    lambda raw: raw + "PASSWORD=oculta\n",
))
def test_manipulacion_de_una_fuente_falla_cerrado(source, corruption):
    reports = all_reports()
    reports[source] = (reports[source][0], corruption(reports[source][1]))
    out = planificar_aislamiento_0051(reports)
    assert not out["inventario_completo"]
    assert out["fuentes_validas"] == 2
    assert not out["autoriza_borrado_fisico"]
    assert "oculta" not in repr(out)


@pytest.mark.parametrize("bad", (
    None, "", [], (), {}, {"0033": (net(), net())},
    {"0033": (net(), net()), "0037": (sid(), sid()),
     "0040": (web(), web()), "extras": ()},
    1, True,
))
def test_origenes_ausentes_nunca_producen_plan_aplicable(bad):
    out = planificar_aislamiento_0051(bad)
    assert out["fuentes_validas"] == 0
    assert not out["inventario_completo"]
    assert out["estado"] == "bloqueada"
    assert not out["mantenimiento_autorizado"]


@pytest.mark.parametrize("bad", (None, [], ("x",), "text", (net(),), (net(), None)))
def test_par_de_fuente_incorrecto_falla(bad):
    data = all_reports()
    data["0033"] = bad
    out = planificar_aislamiento_0051(data)
    assert out["fuentes_validas"] == 2
    assert "auditoria_0033_no_verificable" in out["motivos"]


def _runner():
    file = (
        Path(__file__).resolve().parents[2]
        / "scripts" / "viewtv_aislamiento_dryrun_0051.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0051", file)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runner_6_consultas_sin_permitir_borrado(monkeypatch, capsys):
    runner = _runner()
    calls = []
    outputs = {"0033": net(), "0037": sid(), "0040": web()}

    def fake_audit(name):
        calls.append(name)
        return outputs[name]

    monkeypatch.setattr(runner, "_audit", fake_audit)
    assert runner.main() == 3
    assert calls == ["0033", "0033", "0037", "0037", "0040", "0040"]
    output = capsys.readouterr().out
    assert "ESTADO_RETIRADA_0051=BLOQUEADA" in output
    assert "FUENTES_VALIDAS=3" in output
    assert "VENTANA_MANTENIMIENTO_AUTORIZADA=NO" in output
    assert "PERMISO_DE_BORRADO_OTORGADO=NO" in output
    assert output.count("FASE_") == 6
    assert "SID=S-1-5-" not in output


def test_runner_faltan_evidencias_devuelve_dos(monkeypatch, capsys):
    runner = _runner()
    monkeypatch.setattr(
        runner, "_audit",
        lambda name: None if name == "0040" else (
            net() if name == "0033" else sid()
        ),
    )
    assert runner.main() == 2
    lines = capsys.readouterr().out
    assert "FUENTES_VALIDAS=2" in lines
    assert "ESTADO_RETIRADA_0051=BLOQUEADA" in lines


@pytest.mark.parametrize("bad", (None, "", "Ubuntu;rm", "Ubuntu\nX",
                                  "../Ubuntu", "Ubuntu/24.04", "u" * 90))
def test_distro_no_inyectable(monkeypatch, bad):
    runner = _runner()
    if bad is None:
        monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    else:
        monkeypatch.setenv("WSL_DISTRO_NAME", bad)
    assert runner._audit("0033") is None


def test_runner_solo_scripts_fijos_sin_shell(monkeypatch):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    called = []

    def fake_run(args, **kwargs):
        called.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=net())

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner._audit("0033") == net().strip()
    assert runner._audit("9999") is None
    assert len(called) == 1
    args, opts = called[0]
    assert args[0] == "powershell.exe"
    assert "-File" in args and "-Command" not in args
    assert args[-1].endswith("viewtv_windows_accesos_externos_readonly_0033.ps1")
    assert len(args) == 7
    assert opts["stdin"] is runner.subprocess.DEVNULL
    assert opts["capture_output"]
    assert opts["timeout"] <= 90


@pytest.mark.parametrize("code,output", (
    (2, net()), (0, net() + "PASSWORD=secret\n"), (0, net() + "X" * 5000)
))
def test_runner_no_retorna_salidas_inseguras(monkeypatch, code, output):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=code, stdout=output),
    )
    result = runner._audit("0033")
    if code != 0 or len(output) > 4096:
        assert result is None
    else:
        data = all_reports(n=result)
        assert not planificar_aislamiento_0051(data)["inventario_completo"]
