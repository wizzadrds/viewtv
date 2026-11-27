"""0024: no mezclar película de otro perfil ni evidencias que cambien."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_retirada_preflight_0018 import base
from worker.retirement_request_review_0024 import RevisionNoConfiable

SOURCE = Path(__file__).resolve().parents[2] / (
    "scripts/viewtv_retirada_revision_solicitud_0024.py"
)
SPEC = importlib.util.spec_from_file_location("revision_solicitud_0024", SOURCE)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def fixture():
    snap, journals, ntfs = base()
    snap["peliculas"][0]["visto_perfiles"] = [1]
    snap["qbittorrent"]["8"]["torrent"]["state"] = "uploading"
    snap["qbittorrent"]["8"]["files"].append({
        "name": "Torrent/EXTRA.nfo", "size": 30, "progress": 1, "priority": 1,
    })
    detail = {
        "estado": "unica", "medio_id": 2, "jellyfin_id": "jf-unique",
        "perfiles_activos": [1, 2], "visto_perfiles": [1],
        "pendiente_perfiles": [1], "solicitudes_canceladas": 0,
    }
    return snap, journals, ntfs, detail


def patch_sources(monkeypatch, snap, journals, ntfs, detail):
    monkeypatch.setattr(MOD, "_evidence_windows", lambda: deepcopy(ntfs))
    monkeypatch.setattr(MOD, "_api_snapshot", lambda: deepcopy(snap))
    monkeypatch.setattr(MOD, "_journals_readonly", lambda: deepcopy(journals))
    monkeypatch.setattr(MOD, "_detalle_api", lambda *_: deepcopy(detail))


def test_una_pelicula_especifica_y_pendiente_no_se_borra(monkeypatch, capsys):
    snap, journals, ntfs, detail = fixture()
    patch_sources(monkeypatch, snap, journals, ntfs, detail)
    assert MOD.main(["--titulo", "Pelicula ficticia", "--anio", "2026"]) == 0
    lines = capsys.readouterr().out
    assert "ESTADO=PENDIENTE_REVISION_BLOQUEADA" in lines
    assert "PERFILES_CON_VISTO=1" in lines
    assert "PERFILES_ACTIVOS=2" in lines
    assert "SOLICITUDES_PENDIENTES=1" in lines
    assert "BLOQUEO_HAY_PERFILES_SIN_MARCAR_VISTA=SI" in lines
    assert "BLOQUEO_TORRENT_ACTIVO_O_INCOMPLETO=SI" in lines
    assert "BLOQUEO_TORRENT_CON_ARCHIVOS_AJENOS_O_INCOMPLETOS=SI" in lines
    assert "BLOQUEO_FALTA_AUTORIZACION_ADMINISTRADOR=SI" in lines
    assert "PERMISO_BORRADO_FISICO=NO" in lines
    assert "ARCHIVOS_ELIMINADOS=0" in lines
    assert "TORRENTS_MODIFICADOS=0" in lines
    assert "Pelicula ficticia" not in lines
    assert "jf-unique" not in lines
    assert "Torrent" not in lines


def test_snapshot_sin_pelicula_solicitada_falla_cerrado(monkeypatch, capsys):
    snap, journals, ntfs, detail = fixture()
    detail["estado"] = "pelicula_no_unica"
    patch_sources(monkeypatch, snap, journals, ntfs, detail)
    assert MOD.main(["--titulo", "Otra", "--anio", "2026"]) == 2
    assert "BLOQUEADA_DATOS_NO_CONFIABLES" in capsys.readouterr().out


def test_si_cambian_solicitudes_entre_lecturas_se_aborta(monkeypatch):
    snap, journals, ntfs, detail = fixture()
    patch_sources(monkeypatch, snap, journals, ntfs, detail)
    calls = iter([
        deepcopy(detail),
        dict(detail, pendiente_perfiles=[]),
    ])
    monkeypatch.setattr(MOD, "_detalle_api", lambda *_: next(calls))
    with pytest.raises(RevisionNoConfiable):
        MOD.revisar("Película ficticia", 2026)


def test_si_cambian_hardlinks_entre_lecturas_se_aborta(monkeypatch):
    snap, journals, ntfs, detail = fixture()
    patch_sources(monkeypatch, snap, journals, ntfs, detail)
    changed = deepcopy(ntfs)
    changed[0]["journal_sha256"] = "c" * 64
    calls = iter([ntfs, changed])
    monkeypatch.setattr(MOD, "_evidence_windows", lambda: next(calls))
    with pytest.raises(RevisionNoConfiable):
        MOD.revisar("Película ficticia", 2026)


def test_no_fuga_datos_tras_fallo_en_qbit(monkeypatch, capsys):
    snap, journals, ntfs, detail = fixture()
    patch_sources(monkeypatch, snap, journals, ntfs, detail)
    monkeypatch.setattr(
        MOD, "_api_snapshot",
        lambda: (_ for _ in ()).throw(RuntimeError("token_secreto")),
    )
    assert MOD.main(["--titulo", "Pelicula", "--anio", "2026"]) == 2
    text = capsys.readouterr().out
    assert "token_secreto" not in text
    assert "PERMISO_BORRADO_FISICO=NO" in text


def test_consulta_sql_pasa_solo_el_titulo_al_python_de_la_api(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return SimpleNamespace(
            returncode=0, stdout=json.dumps({"estado": "pelicula_no_unica"}),
        )

    monkeypatch.setattr(MOD.subprocess, "run", fake_run)
    result = MOD._detalle_api("Pelicula ficticia", 2026)
    assert result["estado"] == "pelicula_no_unica"
    assert len(calls) == 1
    cmd, opts = calls[0]
    assert cmd[:6] == ["docker", "exec", "-i", "viewtv-api-1", "python", "-"]
    assert cmd[6:] == ["Pelicula ficticia", "2026"]
    assert opts["capture_output"] is True
    assert opts["check"] is False
    assert opts["timeout"] == 35
    assert "import" in opts["input"]
    assert "Pelicula ficticia" not in opts["input"]


@pytest.mark.parametrize("failure", [
    SimpleNamespace(returncode=2, stdout="Jellyfin secret"),
    SimpleNamespace(returncode=0, stdout="no json"),
    SimpleNamespace(returncode=0, stdout="a" * 8193),
])
def test_no_fuga_respuesta_sql_ajena(monkeypatch, failure):
    monkeypatch.setattr(MOD.subprocess, "run", lambda *args, **kwargs: failure)
    with pytest.raises(RevisionNoConfiable):
        MOD._detalle_api("Pelicula", 2026)


def test_timeout_tambien_se_denega(monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired("docker", timeout=35)

    monkeypatch.setattr(MOD.subprocess, "run", fail)
    with pytest.raises(RevisionNoConfiable):
        MOD._detalle_api("Pelicula", 2026)


@pytest.mark.parametrize(("title", "year"), [
    ("", 2026), ("Pelicula", True), ("Pelicula", 190), ("Pelicula", 2300),
])
def test_argumentos_sin_identidad_valida_no_consultan_sistemas(title, year):
    with pytest.raises(RevisionNoConfiable):
        MOD.revisar(title, year)


def test_fuente_api_no_ejecuta_escrituras():
    code = (SOURCE.parent / "viewtv_retirada_solicitud_api_0024.py").read_text(
        encoding="utf-8",
    )
    assert "session.commit(" not in code
    assert "session.delete(" not in code
    assert "session.add(" not in code
    assert "POST " not in code
