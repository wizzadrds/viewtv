"""0047: informe SID de pipe Win32 fail-closed, sin red ni cuentas."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from worker.retirement_pipe_sid_gate_0047 import (
    EXPECTED_0047,
    EvidenciaPipeNoConfiable,
    evaluar_pipe_0047,
    validar_pipe_0047,
)

GOOD = "\n".join(EXPECTED_0047) + "\n"


def test_contrato_pipe_exactamente_diez_lineas():
    assert len(EXPECTED_0047) == 10
    assert validar_pipe_0047(GOOD) == EXPECTED_0047
    assert validar_pipe_0047(GOOD.replace("\n", "\r\n")) == EXPECTED_0047


def test_doble_windows_valido_jamas_autoriza_retirada():
    decision = evaluar_pipe_0047(GOOD, GOOD.replace("\n", "\r\n"))
    assert decision["estado"] == "bloqueada"
    assert decision["auditorias_validas"] == 2
    assert decision["pipe_sandbox_solo_sid_verificada"] is True
    assert decision["broker_productivo_aislado"] is False
    assert decision["autoriza_borrado_fisico"] is False
    assert decision["puede_borrar_archivos"] is False
    assert "qbit_webui_gui_real_no_aisladas" in decision["motivos"]


@pytest.mark.parametrize("wrong", (
    None, True, b"PASS", 15, "", {}, [], "PASS",
    GOOD + "GUI_WEBUI_QBIT_PRODUCCION_AISLADA=SI\n",
    GOOD + "HASH=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
    GOOD + "SID=S-1-5-21-123\n",
    GOOD.replace("TOKEN_RESTRINGIDO_NO_CONECTA=PASS",
                 "TOKEN_RESTRINGIDO_NO_CONECTA=FAIL"),
    GOOD.replace("GUI_WEBUI_QBIT_PRODUCCION_AISLADA=NO",
                 "GUI_WEBUI_QBIT_PRODUCCION_AISLADA=SI"),
    GOOD.replace("BROKER_PRODUCTIVO_INSTALADO=NO",
                 "BROKER_PRODUCTIVO_INSTALADO=SI"),
    GOOD.replace("ACL_PRODUCTIVAS_MODIFICADAS=0",
                 "ACL_PRODUCTIVAS_MODIFICADAS=1"),
    GOOD.replace("POST_QBIT_REAL=0", "POST_QBIT_REAL=1"),
    GOOD.replace("ARCHIVOS_REALES_ELIMINADOS=0",
                 "ARCHIVOS_REALES_ELIMINADOS=1"),
    GOOD.replace("TOKEN_RESTRINGIDO_NO_CONECTA=PASS\n", ""),
    GOOD.replace("PIPE_ACL_UNICAMENTE_SID_DESIGNADO=PASS\n", ""),
    GOOD.replace("START_ALL", "START_ANY"),
    GOOD.replace("\n", "\r"),
    GOOD + "\x00",
    "\n" + GOOD,
    GOOD.replace("PASS\n", "PASS\nPASS\n", 1),
    GOOD.replace("PIPE_ACL_UNICAMENTE_SID_DESIGNADO=PASS\n", "", 1)
    + "PIPE_ACL_UNICAMENTE_SID_DESIGNADO=PASS\n",
    GOOD + ("X" * 2000),
))
def test_toda_evidencia_alterada_o_filtracion_rechazada(wrong):
    with pytest.raises(EvidenciaPipeNoConfiable):
        validar_pipe_0047(wrong)


@pytest.mark.parametrize("left,right,expected", (
    (None, GOOD, 1),
    (GOOD, None, 1),
    ("not valid", GOOD, 1),
    (GOOD, "not valid", 1),
    ("not valid", "not valid", 0),
    (None, None, 0),
))
def test_informe_parcial_siempre_bloquea(left, right, expected):
    report = evaluar_pipe_0047(left, right)
    assert report["auditorias_validas"] == expected
    assert report["autoriza_borrado_fisico"] is False
    assert report["broker_productivo_aislado"] is False
    assert any(
        reason.startswith("auditoria_pipe_") for reason in report["motivos"]
    )


def _runner():
    source = (
        Path(__file__).resolve().parents[2]
        / "scripts" / "viewtv_retirada_pipe_sid_0047.py"
    )
    spec = importlib.util.spec_from_file_location("viewtv_pipe_0047", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_doble_exito_devuelve_salida_no_cero(monkeypatch, capsys):
    runner = _runner()
    monkeypatch.setattr(runner, "_leer_windows_0047", lambda: GOOD)
    assert runner.main() == 3
    output = capsys.readouterr().out
    assert "AUDITORIAS_VALIDAS=2" in output
    assert "ESTADO_RETIRADA_0047=BLOQUEADA" in output
    assert "PERMISO_DE_BORRADO_OTORGADO=NO" in output
    assert "ARCHIVOS_REALES_ELIMINADOS=0" in output
    assert "S-1-5-" not in output


def test_runner_fallo_de_fuente_devuelve_dos(monkeypatch, capsys):
    runner = _runner()
    observations = iter((GOOD, None))
    monkeypatch.setattr(runner, "_leer_windows_0047", lambda: next(observations))
    assert runner.main() == 2
    output = capsys.readouterr().out
    assert "AUDITORIAS_VALIDAS=1" in output
    assert "PERMISO_DE_BORRADO_OTORGADO=NO" in output


def test_runner_falla_si_no_se_conoce_distribucion_wsl(monkeypatch):
    runner = _runner()
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    assert runner._leer_windows_0047() is None


@pytest.mark.parametrize("distro", (
    "Ubuntu-24.04;rm -rf", "Ubuntu-24.04\nSTART", "/etc/passwd",
    "Ubuntu / secrets", "", "a" * 81,
))
def test_runner_rechaza_distribuciones_inyectadas(monkeypatch, distro):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", distro)
    assert runner._leer_windows_0047() is None


def test_runner_solo_invoca_script_fijo_sin_shell(monkeypatch):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    called = []

    def fake_run(args, **kwargs):
        called.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=GOOD)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner._leer_windows_0047() == GOOD
    assert len(called) == 1
    args, kwargs = called[0]
    assert args[0] == "powershell.exe"
    assert "-Command" not in args
    assert "-File" in args
    assert args[-1].endswith("test_viewtv_windows_pipe_sid_sandbox_0047.ps1")
    assert kwargs["stdin"] is runner.subprocess.DEVNULL
    assert kwargs["capture_output"] is True
    assert kwargs["timeout"] <= 25


@pytest.mark.parametrize("returncode,body", (
    (1, GOOD),
    (0, GOOD + "LEAK=SECRET\n"),
    (0, GOOD + ("X" * 1001)),
))
def test_runner_fallo_proceso_o_salida_insegura(monkeypatch, returncode, body):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=returncode, stdout=body,
        ),
    )
    output = runner._leer_windows_0047()
    if returncode != 0 or len(body) > 1000:
        assert output is None
    else:
        assert evaluar_pipe_0047(output, output)["auditorias_validas"] == 0
