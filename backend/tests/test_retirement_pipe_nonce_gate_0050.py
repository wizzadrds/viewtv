"""0050: validador fail-closed de SID real + nonce durable Windows sandbox."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from worker.retirement_pipe_nonce_gate_0050 import (
    EXPECTED_0050,
    PeerNonceNoConfiable,
    evaluar_peer_nonce_0050,
    validar_peer_nonce_0050,
)

GOOD = "\n".join(EXPECTED_0050) + "\n"


def test_contrato_exactamente_trece_resultados_win32():
    assert len(EXPECTED_0050) == 13
    assert validar_peer_nonce_0050(GOOD) == EXPECTED_0050
    assert validar_peer_nonce_0050(
        GOOD.replace("\n", "\r\n"),
    ) == EXPECTED_0050


def test_dos_ensayos_win32_validos_siempre_deniegan_borrado():
    decision = evaluar_peer_nonce_0050(
        GOOD, GOOD.replace("\n", "\r\n"),
    )
    assert decision["estado"] == "bloqueada"
    assert decision["auditorias_validas"] == 2
    assert decision["auditorias_exigidas"] == 2
    assert decision["win32_peer_y_nonce_en_mismo_ensayo"] is True
    assert decision["sid_broker_productivo_instalado"] is False
    assert decision["autoriza_borrado_fisico"] is False
    assert decision["puede_iniciar_unlink"] is False
    assert "journal_solo_temp_y_sin_prueba_de_apagon" in decision["motivos"]


@pytest.mark.parametrize("bad", (
    None, True, False, 0, b"PASS", {}, [], "", "PASS",
    GOOD + "SID=S-1-5-21-123\n",
    GOOD + "TOKEN=SECRET\n",
    GOOD + "HASH=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
    GOOD.replace("SID_PEER_Y_COMMIT_ANTES_DE_CRASH=PASS",
                 "SID_PEER_Y_COMMIT_ANTES_DE_CRASH=FAIL"),
    GOOD.replace("REPLAY_EN_NUEVA_PIPE_DENEGADO=PASS",
                 "REPLAY_EN_NUEVA_PIPE_DENEGADO=NO"),
    GOOD.replace("SID_FALSO_EN_MENSAJE_DENEGADO=PASS",
                 "SID_FALSO_EN_MENSAJE_DENEGADO=NO"),
    GOOD.replace("HASH_AJENO_DENEGADO=PASS",
                 "HASH_AJENO_DENEGADO=FAIL"),
    GOOD.replace("IDENTIDAD_NO_VERIFICADA_DENEGADA=PASS",
                 "IDENTIDAD_NO_VERIFICADA_DENEGADA=NO"),
    GOOD.replace("NONCE_NUEVO_ACEPTADO_SOLO_MOCK=PASS",
                 "NONCE_NUEVO_ACEPTADO_SOLO_MOCK=FAIL"),
    GOOD.replace("CUATRO_PIPE_CLIENTS_UNICA_RESERVA=PASS",
                 "CUATRO_PIPE_CLIENTS_UNICA_RESERVA=FAIL"),
    GOOD.replace("JOURNAL_MANIPULADO_FALLA_CERRADA=PASS",
                 "JOURNAL_MANIPULADO_FALLA_CERRADA=NO"),
    GOOD.replace("SANDBOX_GUID_LIMPIADO=SI",
                 "SANDBOX_GUID_LIMPIADO=NO"),
    GOOD.replace("BROKER_PRODUCTIVO_INSTALADO=NO",
                 "BROKER_PRODUCTIVO_INSTALADO=SI"),
    GOOD.replace("QBIT_REAL_CONTACTADO=NO",
                 "QBIT_REAL_CONTACTADO=SI"),
    GOOD.replace("ARCHIVOS_REALES_ELIMINADOS=0",
                 "ARCHIVOS_REALES_ELIMINADOS=1"),
    GOOD.replace("TORRENTS_REALES_MODIFICADOS=0",
                 "TORRENTS_REALES_MODIFICADOS=1"),
    GOOD.replace("NONCE_NUEVO_ACEPTADO_SOLO_MOCK=PASS\n", ""),
    GOOD.replace("PASS\n", "PASS\nPASS\n", 1),
    GOOD.replace("\n", "\r"),
    GOOD.replace("\n", "\r\r\n"),
    GOOD + "\x00",
    GOOD + ("X" * 1500),
    "\n" + GOOD,
    GOOD.replace("REPLAY_EN_NUEVA_PIPE_DENEGADO=PASS\n", ""),
))
def test_resultado_modificado_es_rechazado(bad):
    with pytest.raises(PeerNonceNoConfiable):
        validar_peer_nonce_0050(bad)


@pytest.mark.parametrize("left,right,valid", (
    (GOOD, None, 1),
    (None, GOOD, 1),
    (GOOD, "BAD", 1),
    ("BAD", GOOD, 1),
    ("BAD", "BAD", 0),
    (None, None, 0),
))
def test_evidencia_incompleta_bloquea(left, right, valid):
    result = evaluar_peer_nonce_0050(left, right)
    assert result["auditorias_validas"] == valid
    assert result["estado"] == "bloqueada"
    assert result["autoriza_borrado_fisico"] is False
    assert any(key.startswith("auditoria_") for key in result["motivos"])


def _runner():
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts" / "viewtv_retirada_pipe_nonce_0050.py"
    )
    spec = importlib.util.spec_from_file_location("pipe_nonce_0050", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_devuelve_tres_incluso_con_dos_ensayos_correctos(
    monkeypatch, capsys,
):
    runner = _runner()
    monkeypatch.setattr(runner, "_observar_0050", lambda: GOOD)
    assert runner.main() == 3
    lines = capsys.readouterr().out
    assert "ESTADO_RETIRADA_0050=BLOQUEADA" in lines
    assert "AUDITORIAS_VALIDAS=2" in lines
    assert "PERMISO_DE_BORRADO_OTORGADO=NO" in lines
    assert "ARCHIVOS_REALES_ELIMINADOS=0" in lines
    assert "S-1-5-" not in lines
    assert "a" * 40 not in lines


def test_runner_devuelve_dos_si_falla_segunda_fuente(monkeypatch, capsys):
    runner = _runner()
    results = iter((GOOD, None))
    monkeypatch.setattr(runner, "_observar_0050", lambda: next(results))
    assert runner.main() == 2
    assert "AUDITORIAS_VALIDAS=1" in capsys.readouterr().out


@pytest.mark.parametrize("distro", (
    None, "", "Ubuntu;evil", "Ubuntu\nmore", "../../Ubuntu",
    "/etc/passwd", "Ubuntu with spaces", "x" * 100,
))
def test_runner_denegacion_nombre_distro_inyectado(monkeypatch, distro):
    runner = _runner()
    if distro is None:
        monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    else:
        monkeypatch.setenv("WSL_DISTRO_NAME", distro)
    assert runner._observar_0050() is None


def test_runner_no_acepta_shell_ni_path_dinamico(monkeypatch):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=GOOD)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner._observar_0050() == GOOD
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] == "powershell.exe"
    assert "-File" in args and "-Command" not in args
    assert args[-1].endswith(
        "test_viewtv_windows_pipe_peer_nonce_sandbox_0050.ps1"
    )
    assert len(args) == 7
    assert kwargs["stdin"] is runner.subprocess.DEVNULL
    assert kwargs["capture_output"] is True
    assert kwargs["timeout"] <= 45


@pytest.mark.parametrize("rc,output", (
    (2, GOOD), (3, GOOD), (0, GOOD + "SECRET=NO\n"),
    (0, GOOD + ("X" * 1500)),
))
def test_runner_proceso_inseguro_no_da_permiso(monkeypatch, rc, output):
    runner = _runner()
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=rc, stdout=output,
        ),
    )
    source = runner._observar_0050()
    if rc or len(output) > 1400:
        assert source is None
    else:
        assert evaluar_peer_nonce_0050(
            source, source,
        )["auditorias_validas"] == 0
