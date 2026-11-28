"""0049: nonce durable solo en TEMP, auditoría fail-closed de crash Win32."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from worker.retirement_nonce_durable_gate_0049 import (
    EXPECTED_0049,
    EvidenciaNonceNoConfiable,
    evaluar_nonce_0049,
    validar_nonce_0049,
)

GOOD = "\n".join(EXPECTED_0049) + "\n"


def test_contrato_0049_estricto_y_crlf_windows():
    assert len(EXPECTED_0049) == 12
    assert validar_nonce_0049(GOOD) == EXPECTED_0049
    assert validar_nonce_0049(
        GOOD.replace("\n", "\r\n"),
    ) == EXPECTED_0049


def test_dos_ejecuciones_correctas_son_solo_ensayo():
    result = evaluar_nonce_0049(GOOD, GOOD.replace("\n", "\r\n"))
    assert result["estado"] == "bloqueada"
    assert result["auditorias_validas"] == 2
    assert result["auditorias_exigidas"] == 2
    assert result["nonce_durable_en_windows_sandbox"] is True
    assert result["nonce_durable_en_broker_real"] is False
    assert result["puede_borrar_archivos"] is False
    assert result["permiso_de_borrado_otorgado"] is False
    assert "ledger_nonce_solo_sandbox_desconectado_de_pipe" in result["motivos"]


@pytest.mark.parametrize("bad", (
    None, True, 0, 1.0, b"PASS", {}, [], "", "PASS",
    GOOD + "ARCHIVOS_REALES_ELIMINADOS=1\n",
    GOOD + "QBIT_REAL_CONTACTADO=SI\n",
    GOOD + "SID=S-1-5-21-SECRET\n",
    GOOD + "PASSWORD_PBKDF2=SECRET\n",
    GOOD.replace("MUERTE_REAL_TRAS_INTENCION_DURABLE=PASS",
                 "MUERTE_REAL_TRAS_INTENCION_DURABLE=NO"),
    GOOD.replace("REPLAY_TRAS_REINICIO_DENEGADO=PASS",
                 "REPLAY_TRAS_REINICIO_DENEGADO=FAIL"),
    GOOD.replace("NONCE_OTRO_HASH_RECHAZADO=PASS",
                 "NONCE_OTRO_HASH_RECHAZADO=NO"),
    GOOD.replace("CUATRO_PROCESOS_UNICA_RESERVA=PASS",
                 "CUATRO_PROCESOS_UNICA_RESERVA=FAIL"),
    GOOD.replace("BITACORA_CORRUPTA_FALLA_CERRADA=PASS",
                 "BITACORA_CORRUPTA_FALLA_CERRADA=NO"),
    GOOD.replace("SANDBOX_GUID_LIMPIADO=SI",
                 "SANDBOX_GUID_LIMPIADO=NO"),
    GOOD.replace("BROKER_PRODUCTIVO_INSTALADO=NO",
                 "BROKER_PRODUCTIVO_INSTALADO=SI"),
    GOOD.replace("NONCE_PRODUCTIVO_DURABLE=NO",
                 "NONCE_PRODUCTIVO_DURABLE=SI"),
    GOOD.replace("QBIT_REAL_CONTACTADO=NO",
                 "QBIT_REAL_CONTACTADO=SI"),
    GOOD.replace("ARCHIVOS_REALES_ELIMINADOS=0",
                 "ARCHIVOS_REALES_ELIMINADOS=1"),
    GOOD.replace("TORRENTS_REALES_MODIFICADOS=0",
                 "TORRENTS_REALES_MODIFICADOS=1"),
    GOOD.replace("BITACORA_CORRUPTA_FALLA_CERRADA=PASS\n", ""),
    GOOD.replace("PASS\n", "PASS\nPASS\n", 1),
    GOOD.replace("\n", "\r"),
    GOOD.replace("\n", "\r\r\n"),
    GOOD + "\x00",
    "\n" + GOOD,
    GOOD + ("X" * 1500),
    GOOD.replace("OTRO_NONCE_INDEPENDIENTE_Y_UNICO=PASS\n", ""),
))
def test_evidencia_adulterada_no_pasa(bad):
    with pytest.raises(EvidenciaNonceNoConfiable):
        validar_nonce_0049(bad)


@pytest.mark.parametrize("first,second,count", (
    (GOOD, None, 1),
    (None, GOOD, 1),
    (GOOD, "no", 1),
    ("no", GOOD, 1),
    (None, None, 0),
    ("no", "no", 0),
))
def test_doble_lectura_incompleta_deniega(first, second, count):
    result = evaluar_nonce_0049(first, second)
    assert result["auditorias_validas"] == count
    assert result["estado"] == "bloqueada"
    assert result["permiso_de_borrado_otorgado"] is False
    assert any(
        reason.startswith("ensayo_") for reason in result["motivos"]
    )


def _runner():
    file = (
        Path(__file__).resolve().parents[2]
        / "scripts" / "viewtv_retirada_nonce_0049.py"
    )
    spec = importlib.util.spec_from_file_location("nonce_runner_0049", file)
    assert spec is not None and spec.loader is not None
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def test_runner_exit_3_incluso_con_dos_crashes_correctos(
    monkeypatch, capsys,
):
    runner = _runner()
    monkeypatch.setattr(runner, "_observar_0049", lambda: GOOD)
    assert runner.main() == 3
    stdout = capsys.readouterr().out
    assert "AUDITORIAS_VALIDAS=2" in stdout
    assert "ESTADO_RETIRADA_0049=BLOQUEADA" in stdout
    assert "PERMISO_DE_BORRADO_OTORGADO=NO" in stdout
    assert "ARCHIVOS_REALES_ELIMINADOS=0" in stdout
    assert "S-1-5-" not in stdout
    assert "a" * 40 not in stdout


def test_runner_exit_2_si_un_proceso_windows_falla(monkeypatch, capsys):
    runner = _runner()
    reports = iter((GOOD, None))
    monkeypatch.setattr(runner, "_observar_0049", lambda: next(reports))
    assert runner.main() == 2
    assert "AUDITORIAS_VALIDAS=1" in capsys.readouterr().out


@pytest.mark.parametrize("distro", (
    None, "", "Ubuntu;bad", "Ubuntu\nX", "../Ubuntu",
    "Ubuntu /etc", "a" * 100,
))
def test_runner_sin_inyeccion_en_nombre_de_distro(monkeypatch, distro):
    runner = _runner()
    if distro is None:
        monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    else:
        monkeypatch.setenv("WSL_DISTRO_NAME", distro)
    assert runner._observar_0049() is None


def test_runner_no_shell_ni_parametros_dinamicos(monkeypatch):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=GOOD)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner._observar_0049() == GOOD
    assert len(calls) == 1
    args, opts = calls[0]
    assert args[0] == "powershell.exe"
    assert "-File" in args and "-Command" not in args
    assert args[-1].endswith(
        "test_viewtv_windows_pipe_nonce_durable_sandbox_0049.ps1"
    )
    assert len(args) == 7
    assert opts["stdin"] == runner.subprocess.DEVNULL
    assert opts["timeout"] <= 45
    assert opts["capture_output"]


@pytest.mark.parametrize("rc,content", (
    (1, GOOD), (5, GOOD),
    (0, GOOD + "SECRET=NO\n"),
    (0, GOOD + ("X" * 1401)),
))
def test_runner_subproceso_erroneo_denegado(
    monkeypatch, rc, content,
):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda *a, **k: SimpleNamespace(
            returncode=rc, stdout=content,
        ),
    )
    result = runner._observar_0049()
    if rc or len(content) > 1400:
        assert result is None
    else:
        assert evaluar_nonce_0049(result, result)["auditorias_validas"] == 0
