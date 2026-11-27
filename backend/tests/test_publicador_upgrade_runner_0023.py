"""El coordinador WSL de 0023 solo invoca la auditoría Windows read-only."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_publicador_upgrade_gate_0023 import report

PATH = Path(__file__).resolve().parents[2] / (
    "scripts/viewtv_publicador_upgrade_preflight_0023.py"
)
SPEC = importlib.util.spec_from_file_location("publisher_upgrade_readonly_0023", PATH)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_comando_exclusivamente_powershell_en_lectura(capsys, monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=report(), stderr="")

    monkeypatch.setattr(RUNNER.subprocess, "run", fake_run)
    assert RUNNER.main() == 0
    out = capsys.readouterr().out
    assert "BLOQUEOS_ACTUALES=4" in out
    assert "REEMPLAZO_AUTOMATICO=NO" in out
    assert "BLOQUEO_TAREA_NO_DESHABILITADA=SI" in out
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv[:5] == [
        "powershell.exe", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
    ]
    assert argv[5] == "-File"
    assert argv[6].endswith("viewtv_windows_publicador_upgrade_readonly_0023.ps1")
    assert kwargs["timeout"] == 40
    assert kwargs["capture_output"] is True
    assert kwargs["check"] is False


@pytest.mark.parametrize(("exit_code", "stdout"), [
    (1, report()),
    (2, "PASSWORD=secreto"),
    (0, report().replace("TAREAS_MODIFICADAS=0", "TAREAS_MODIFICADAS=1")),
    (0, report() + "SESSION=secreto\n"),
    (0, "USER=privado"),
])
def test_error_o_salida_no_confiable_falla_sin_secretos(
    capsys, monkeypatch, exit_code, stdout,
):
    monkeypatch.setattr(
        RUNNER.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=exit_code, stdout=stdout, stderr="TOKEN PRIVADO",
        ),
    )
    assert RUNNER.main() == 2
    out = capsys.readouterr().out
    assert out == (
        "UPGRADE_PUBLICADOR_0023=BLOQUEADO_FUENTE_NO_CONFIABLE\n"
        "REEMPLAZO_AUTOMATICO=NO\n"
        "MEDIOS_MODIFICADOS=0\n"
        "TORRENTS_MODIFICADOS=0\n"
    )
    assert "PRIVADO" not in out


def test_timeout_no_hace_una_segunda_llamada(capsys, monkeypatch):
    calls = []

    def timeout(*args, **kwargs):
        calls.append(1)
        raise subprocess.TimeoutExpired(cmd="powershell", timeout=40)

    monkeypatch.setattr(RUNNER.subprocess, "run", timeout)
    assert RUNNER.main() == 2
    assert len(calls) == 1
    assert "REEMPLAZO_AUTOMATICO=NO" in capsys.readouterr().out


def test_evaluador_no_es_un_instalador():
    source = PATH.read_text(encoding="utf-8")
    for verb in (
        "Stop-Process", "Disable-ScheduledTask", "Enable-ScheduledTask",
        "Stop-Service", "Register-ScheduledTask", "Remove-Item",
    ):
        assert verb not in source
    assert "shell=True" not in source


def test_auditoria_windows_no_modifica_tareas_o_contenido_productivo():
    windows = (PATH.parents[1] / (
        "scripts/viewtv_windows_publicador_upgrade_readonly_0023.ps1"
    )).read_text(encoding="utf-8")
    assert "Get-ScheduledTask -TaskName" in windows
    assert "Get-CimInstance" in windows
    assert "Get-FileHash" in windows
    assert "REEMPLAZO_AUTOMATICO_DESDE_AUDITORIA=NO" in windows
    assert "PUEDE_AFIRMARSE_EXCLUSION_PRODUCTIVA=NO" in windows
    for verb in (
        "Stop-Process", "Disable-ScheduledTask", "Enable-ScheduledTask",
        "Stop-Service", "Set-Service", "Remove-Item", "[IO.File]::Delete",
        "[IO.File]::Replace", "[IO.File]::Copy",
    ):
        assert verb not in windows
