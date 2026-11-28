"""0052: servicio LocalService aislado, sin derechos sobre ningún medio."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from worker.retirement_installed_broker_gate_0052 import (
    PASS_0052,
    EvidenciaServicioNoConfiable,
    evaluar_servicio_0052,
    validar_servicio_0052,
)

GOOD = "\n".join(PASS_0052) + "\n"


def test_host_devuelve_diez_lineas_sin_secretos():
    assert len(PASS_0052) == 10
    assert validar_servicio_0052(GOOD) == PASS_0052
    assert validar_servicio_0052(GOOD.replace("\n", "\r\n")) == PASS_0052


def test_broker_real_inerte_no_es_ejecutor_de_borrado():
    decision = evaluar_servicio_0052(GOOD, GOOD.replace("\n", "\r\n"))
    assert decision["auditorias_validas"] == 2
    assert decision["sid_servicio_independiente_instalado"] is True
    assert decision["acl_broker_privada_verificada"] is True
    assert decision["cuenta_mantenimiento_autorizada"] is True
    assert decision["broker_fisico_retirada_instalado"] is False
    assert decision["permiso_de_borrado_otorgado"] is False
    assert decision["puede_iniciar_unlink"] is False
    assert decision["estado"] == "bloqueada"


@pytest.mark.parametrize("wrong", (
    None, False, 5, b"PASS", {}, [], "", "PASS",
    GOOD + "TOKEN=secret\n",
    GOOD + "SID=S-1-5-19\n",
    GOOD + "QBIT_PASSWORD=secret\n",
    GOOD + "BROKER_CON_DELETE=SI\n",
    GOOD.replace("BROKER_SID_DISTINTO_OPERADOR=PASS",
                 "BROKER_SID_DISTINTO_OPERADOR=FAIL"),
    GOOD.replace("SERVICIO_MANUAL_Y_DETENIDO=PASS",
                 "SERVICIO_MANUAL_Y_DETENIDO=NO"),
    GOOD.replace("CARPETA_PRIVADA_MARCADA=PASS",
                 "CARPETA_PRIVADA_MARCADA=FAIL"),
    GOOD.replace("ACL_EXCLUSIVAS_ADMIN_SYSTEM_SERVICE=PASS",
                 "ACL_EXCLUSIVAS_ADMIN_SYSTEM_SERVICE=NO"),
    GOOD.replace("BINARIO_SIN_WRITE_SERVICIO=PASS",
                 "BINARIO_SIN_WRITE_SERVICIO=FAIL"),
    GOOD.replace("DIRECTORIO_DATOS_PRIVADO=PASS",
                 "DIRECTORIO_DATOS_PRIVADO=NO"),
    GOOD.replace("AUTO_PRUEBA_BROKER_SID_Y_PIPE=PASS",
                 "AUTO_PRUEBA_BROKER_SID_Y_PIPE=FAIL"),
    GOOD.replace("BROKER_FUNCIONES_DE_BORRADO=NO",
                 "BROKER_FUNCIONES_DE_BORRADO=SI"),
    GOOD.replace("TORRENTS_REALES_MODIFICADOS=0",
                 "TORRENTS_REALES_MODIFICADOS=1"),
    GOOD.replace("ARCHIVOS_REALES_ELIMINADOS=0",
                 "ARCHIVOS_REALES_ELIMINADOS=1"),
    GOOD.replace("PASS\n", "PASS\nPASS\n", 1),
    GOOD.replace("SERVICIO_MANUAL_Y_DETENIDO=PASS\n", ""),
    GOOD.replace("\n", "\r"),
    GOOD.replace("\n", "\r\r\n"),
    GOOD + "\x00",
    GOOD + ("X" * 900),
    "\n" + GOOD,
    GOOD.replace("AUTO_PRUEBA_BROKER_SID_Y_PIPE=PASS\n", ""),
))
def test_rechaza_cualquier_permiso_ilegítimo(wrong):
    with pytest.raises(EvidenciaServicioNoConfiable):
        validar_servicio_0052(wrong)


@pytest.mark.parametrize("a,b,count", (
    (GOOD, None, 1),
    (None, GOOD, 1),
    ("no", GOOD, 1),
    (GOOD, "no", 1),
    (None, None, 0),
    ("no", "no", 0),
))
def test_doble_verificacion_fail_closed(a, b, count):
    result = evaluar_servicio_0052(a, b)
    assert result["auditorias_validas"] == count
    assert result["permiso_de_borrado_otorgado"] is False
    assert result["puede_iniciar_unlink"] is False
    if count != 2:
        assert not result["sid_servicio_independiente_instalado"]


def _runner():
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts" / "viewtv_broker_instalado_gate_0052.py"
    )
    spec = importlib.util.spec_from_file_location("installed_broker_0052", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_dos_ensayos_aceptados_sin_permiso(monkeypatch, capsys):
    runner = _runner()
    monkeypatch.setattr(runner, "_leer_host_0052", lambda: GOOD)
    assert runner.main() == 3
    report = capsys.readouterr().out
    assert "AUDITORIAS_VALIDAS=2" in report
    assert "ESTADO_RETIRADA_0052=BLOQUEADA" in report
    assert "BROKER_FISICO_CON_ELIMINACION_INSTALADO=NO" in report
    assert "PERMISO_DE_BORRADO_OTORGADO=NO" in report
    assert "ARCHIVOS_REALES_ELIMINADOS=0" in report
    assert "S-1-5-" not in report


def test_runner_lectura_incompleta_devuelve_dos(monkeypatch, capsys):
    runner = _runner()
    readings = iter((GOOD, None))
    monkeypatch.setattr(runner, "_leer_host_0052", lambda: next(readings))
    assert runner.main() == 2
    assert "AUDITORIAS_VALIDAS=1" in capsys.readouterr().out


@pytest.mark.parametrize("distro", (
    None, "", "Ubuntu;bad", "Ubuntu\nX", "../../Ubuntu",
    "/etc/passwd", "Ubuntu with spaces", "x" * 100,
))
def test_runner_bloquea_distro_inyectada(monkeypatch, distro):
    runner = _runner()
    if distro is None:
        monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    else:
        monkeypatch.setenv("WSL_DISTRO_NAME", distro)
    assert runner._leer_host_0052() is None


def test_runner_invoca_powershell_script_fijo_sin_shell(monkeypatch):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    invoked = []

    def fake_call(args, **kwargs):
        invoked.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=GOOD)

    monkeypatch.setattr(runner.subprocess, "run", fake_call)
    assert runner._leer_host_0052() == GOOD
    assert len(invoked) == 1
    args, kw = invoked[0]
    assert args[0] == "powershell.exe"
    assert "-Command" not in args and "-File" in args
    assert args[-1].endswith("viewtv_windows_broker_verify_readonly_0052.ps1")
    assert len(args) == 7
    assert kw["stdin"] is runner.subprocess.DEVNULL
    assert kw["capture_output"]
    assert kw["timeout"] <= 25


@pytest.mark.parametrize("rc,text", (
    (1, GOOD), (2, GOOD), (0, GOOD + "PASSWORD=secret\n"),
    (0, GOOD + ("X" * 901)),
))
def test_runner_proceso_windows_fallido_no_autoriza(monkeypatch, rc, text):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda *a, **kw: SimpleNamespace(returncode=rc, stdout=text),
    )
    result = runner._leer_host_0052()
    if rc or len(text) > 850:
        assert result is None
    else:
        assert evaluar_servicio_0052(
            result, result,
        )["auditorias_validas"] == 0
