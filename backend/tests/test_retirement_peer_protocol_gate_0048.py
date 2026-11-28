"""0048: rechazar peer falso, replay, payload y falsas autorizaciones."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from worker.retirement_peer_protocol_gate_0048 import (
    EXPECTED_0048,
    ProtocoloPipeNoConfiable,
    evaluar_protocolo_pipe_0048,
    validar_protocolo_pipe_0048,
)

GOOD = "\n".join(EXPECTED_0048) + "\n"


def test_informe_windows_limpio_canonicamente():
    assert len(EXPECTED_0048) == 11
    assert validar_protocolo_pipe_0048(GOOD) == EXPECTED_0048
    assert validar_protocolo_pipe_0048(
        GOOD.replace("\n", "\r\n")
    ) == EXPECTED_0048


def test_dos_peers_windows_validos_no_son_broker_productivo():
    result = evaluar_protocolo_pipe_0048(
        GOOD, GOOD.replace("\n", "\r\n"),
    )
    assert result["estado"] == "bloqueada"
    assert result["auditorias_validas"] == 2
    assert result["comprobacion_peer_windows_sandbox"]
    assert result["sid_broker_productivo_verificado"] is False
    assert result["qbit_real_aislado"] is False
    assert result["puede_borrar_archivos"] is False
    assert result["permiso_de_borrado_otorgado"] is False
    assert "nonces_sin_ledger_persistente_de_pipe" in result["motivos"]


@pytest.mark.parametrize("wrong", (
    None, True, 12, b"pipe", {}, [], "", "PASS",
    GOOD + "SID=S-1-5-21-10\n",
    GOOD + "PASSWORD=123456\n",
    GOOD + "HASH=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
    GOOD + "POST_QBIT_REAL=1\n",
    GOOD.replace("SID_DEL_CLIENTE_OBTENIDO_POR_WIN32=PASS",
                 "SID_DEL_CLIENTE_OBTENIDO_POR_WIN32=NO"),
    GOOD.replace("SID_EN_PAYLOAD_NO_ES_AUTORIDAD=PASS",
                 "SID_EN_PAYLOAD_NO_ES_AUTORIDAD=FAIL"),
    GOOD.replace("NONCE_REUTILIZADO_DENEGADO=PASS",
                 "NONCE_REUTILIZADO_DENEGADO=NO"),
    GOOD.replace("QBIT_REAL_CONTACTADO=NO", "QBIT_REAL_CONTACTADO=SI"),
    GOOD.replace("BROKER_SID_DISTINTO_PRODUCTIVO=NO",
                 "BROKER_SID_DISTINTO_PRODUCTIVO=SI"),
    GOOD.replace("REPLAY_DURABLE_TRAS_REINICIO_INSTALADO=NO",
                 "REPLAY_DURABLE_TRAS_REINICIO_INSTALADO=SI"),
    GOOD.replace("ARCHIVOS_REALES_ELIMINADOS=0",
                 "ARCHIVOS_REALES_ELIMINADOS=1"),
    GOOD.replace("TORRENTS_REALES_MODIFICADOS=0",
                 "TORRENTS_REALES_MODIFICADOS=1"),
    GOOD.replace("SOLO_MOCK_START_SIN_EFECTOS=PASS\n", ""),
    GOOD.replace("START_ALL_Y_HASH_AJENO_DENEGADOS=PASS\n", ""),
    GOOD.replace("PASS\n", "PASS\nPASS\n", 1),
    GOOD.replace("\n", "\r"),
    GOOD + "\x00",
    GOOD + ("X" * 1500),
    "\n" + GOOD,
    GOOD.replace("\n", "\r\r\n"),
    GOOD.replace("SID_NO_VERIFICADO_DENEGADO=PASS",
                 "SID_NO_VERIFICADO_DENEGADO=PASS\n"
                 "SID_NO_VERIFICADO_DENEGADO=PASS"),
))
def test_toda_falsificacion_de_peer_rechazada(wrong):
    with pytest.raises(ProtocoloPipeNoConfiable):
        validar_protocolo_pipe_0048(wrong)


@pytest.mark.parametrize("first,second,expected", (
    (GOOD, None, 1),
    (None, GOOD, 1),
    ("BAD", GOOD, 1),
    (GOOD, "BAD", 1),
    (None, None, 0),
    ("BAD", "BAD", 0),
))
def test_falta_alguno_de_dos_informes_falla_cerrado(
    first, second, expected,
):
    result = evaluar_protocolo_pipe_0048(first, second)
    assert result["auditorias_validas"] == expected
    assert not result["permiso_de_borrado_otorgado"]
    assert any(
        key.startswith("auditoria_") for key in result["motivos"]
    )


def _runner():
    source = (
        Path(__file__).resolve().parents[2]
        / "scripts" / "viewtv_retirada_peer_protocol_0048.py"
    )
    spec = importlib.util.spec_from_file_location("runner_0048", source)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runner_incluso_dos_exitos_devuelve_no_cero(monkeypatch, capsys):
    runner = _runner()
    monkeypatch.setattr(runner, "_observar_0048", lambda: GOOD)
    assert runner.main() == 3
    output = capsys.readouterr().out
    assert "AUDITORIAS_VALIDAS=2" in output
    assert "ESTADO_RETIRADA_0048=BLOQUEADA" in output
    assert "PERMISO_DE_BORRADO_OTORGADO=NO" in output
    assert "ARCHIVOS_REALES_ELIMINADOS=0" in output
    assert "NONCE=" not in output
    assert "S-1-5-" not in output


def test_runner_informe_cortado_devuelve_codigo_dos(monkeypatch, capsys):
    runner = _runner()
    readings = iter((GOOD, None))
    monkeypatch.setattr(runner, "_observar_0048", lambda: next(readings))
    assert runner.main() == 2
    assert "AUDITORIAS_VALIDAS=1" in capsys.readouterr().out


@pytest.mark.parametrize("distro", (
    None, "", "Ubuntu-24.04 /", "../../etc",
    "Ubuntu;bad", "Ubuntu\nX", "a" * 90,
))
def test_no_inyectar_distribucion_windows(monkeypatch, distro):
    runner = _runner()
    if distro is None:
        monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    else:
        monkeypatch.setenv("WSL_DISTRO_NAME", distro)
    assert runner._observar_0048() is None


def test_runner_solo_script_fijo_sin_shell(monkeypatch):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=GOOD)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner._observar_0048() == GOOD
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] == "powershell.exe"
    assert "-File" in args and "-Command" not in args
    assert args[-1].endswith(
        "test_viewtv_windows_pipe_peer_protocol_sandbox_0048.ps1"
    )
    assert kwargs["stdin"] is runner.subprocess.DEVNULL
    assert kwargs["capture_output"] is True
    assert kwargs["timeout"] <= 25


@pytest.mark.parametrize("rc,out", (
    (4, GOOD),
    (0, GOOD + ("X" * 1500)),
    (0, GOOD + "SID=secreto\n"),
))
def test_runner_fallo_proceso_y_salida_sospechosa(monkeypatch, rc, out):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=rc, stdout=out,
        ),
    )
    value = runner._observar_0048()
    if rc or len(out) > 1200:
        assert value is None
    else:
        assert evaluar_protocolo_pipe_0048(
            value, value
        )["auditorias_validas"] == 0
