"""No Docker real: el ejecutor local solo transmite un sondeo sin secretos."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

module_path = Path(__file__).resolve().parents[2] / (
    "scripts/viewtv_retirada_jellyfin_probe_run_0021.py"
)
spec = importlib.util.spec_from_file_location("viewtv_runner_0021", module_path)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


VALID = """JELLYFIN_SESIONES_0021=SOLO_GET
ESTADO=sin_reproduccion_reportada
PELICULAS_COMPROBADAS=4
PELICULAS_BLOQUEADAS=0
SESIONES_JELLYFIN=0
SESIONES_PELICULA_OBJETIVO=0
SESIONES_OTRAS_PELICULAS=0
SESIONES_AMBIGUAS=0
SIN_BLOQUEO_TRANSACCIONAL=SI
AUTORIZA_BORRADO_FISICO=NO
REPRODUCCIONES_MODIFICADAS=0
ARCHIVOS_ELIMINADOS=0
"""


def test_payload_carga_guarda_en_memoria_sin_archivos_de_produccion():
    code = runner.payload()
    assert "sys.modules['worker.retirement_playback_guard_0021']" in code
    assert "docker exec" not in code
    assert "jwt_secret" not in code
    assert ".env" not in code


def test_salida_segura_del_probedor(capsys, monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=VALID, stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.main() == 0
    out = capsys.readouterr().out
    assert "ESTADO=sin_reproduccion_reportada" in out
    assert "AUTORIZA_BORRADO_FISICO=NO" in out
    assert len(calls) == 1
    assert calls[0][0] == ["docker", "exec", "-i", "viewtv-api-1", "python", "-"]
    assert calls[0][1]["timeout"] == 35


@pytest.mark.parametrize("stdout", [
    VALID.replace("AUTORIZA_BORRADO_FISICO=NO", "AUTORIZA_BORRADO_FISICO=SI"),
    VALID.replace("ARCHIVOS_ELIMINADOS=0", "ARCHIVOS_ELIMINADOS=1"),
    VALID + "NOMBRE_USUARIO=privado\n",
    VALID.replace("ESTADO=sin_reproduccion_reportada", "ESTADO=nombre privado"),
    VALID + "ESTADO=duplicado\n",
])
def test_salida_alterada_es_bloqueo_sin_divulgar(capsys, monkeypatch, stdout):
    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=stdout, stderr="clave PRIVADA",
        ),
    )
    assert runner.main() == 2
    out = capsys.readouterr().out
    assert out == (
        "JELLYFIN_SESIONES_0021=BLOQUEADO\n"
        "AUTORIZA_BORRADO_FISICO=NO\n"
        "ARCHIVOS_ELIMINADOS=0\n"
    )
    assert "PRIVADA" not in out


def test_error_del_contenedor_no_filtra_mensaje_privado(capsys, monkeypatch):
    monkeypatch.setattr(
        runner.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="SECRET=PRIVADO", stderr="TOKEN secreto"
        ),
    )
    assert runner.main() == 2
    assert "SECRET" not in capsys.readouterr().out


def test_timeout_bloquea_sin_iniciar_nuevo_proceso(capsys, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="docker", timeout=35)

    monkeypatch.setattr(runner.subprocess, "run", timeout)
    assert runner.main() == 2
    assert "ARCHIVOS_ELIMINADOS=0" in capsys.readouterr().out
