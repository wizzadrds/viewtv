"""0026: orquestador no filtra datos y aborta ante drift entre GETs.

Mocks sintéticos, sin Docker ni cambios reales.
"""
from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path

from test_retirada_preflight_0018 import base

PATH = Path(__file__).resolve().parents[2] / (
    "scripts/viewtv_retirada_custodia_qbit_0026.py"
)
SPEC = importlib.util.spec_from_file_location("qbit_custody_0026", PATH)
assert SPEC and SPEC.loader
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)


def patch_sources(monkeypatch, snap, journals, ntfs):
    monkeypatch.setattr(RUN, "_api_snapshot", lambda: deepcopy(snap))
    monkeypatch.setattr(RUN, "_journals_readonly", lambda: deepcopy(journals))
    monkeypatch.setattr(RUN, "_evidence_windows", lambda: deepcopy(ntfs))


def test_orquestador_get_doble_no_autoriza_retirada(monkeypatch, capsys):
    s, j, n = base()
    patch_sources(monkeypatch, s, j, n)
    assert RUN.main() == 0
    output = capsys.readouterr().out
    assert "DOBLE_SNAPSHOT_SQL_JELLYFIN_QBIT=COINCIDENTE" in output
    assert "TORRENT_COMPLETO_Y_EN_REPOSO_REPORTADO=1" in output
    assert "PERMISO_BORRADO_FISICO=NO" in output
    assert "TORRENTS_MODIFICADOS=0" in output
    assert "aaaaaaaaaaaa" not in output
    assert "jf-unique" not in output


def test_qbit_activo_con_extra_se_mantiene_custodiado(monkeypatch, capsys):
    s, j, n = base()
    s["qbittorrent"]["8"]["torrent"]["state"] = "uploading"
    s["qbittorrent"]["8"]["files"].append({
        "name": "Torrent/extra.nfo", "size": 10,
        "progress": 1, "priority": 1,
    })
    patch_sources(monkeypatch, s, j, n)
    assert RUN.main() == 0
    output = capsys.readouterr().out
    assert "TORRENT_NO_EN_REPOSO_O_INCOMPLETO=1" in output
    assert "EXTRAS_CONSERVADOS=SI" in output
    assert "ARCHIVOS_EXTRA_PROTEGIDOS=1" in output


def test_drift_de_torrent_se_bloquea_con_salida_privada(monkeypatch, capsys):
    s, j, n = base()
    patch_sources(monkeypatch, s, j, n)
    after = deepcopy(s)
    after["qbittorrent"]["8"]["torrent"]["state"] = "uploading"
    calls = iter([deepcopy(s), after])
    monkeypatch.setattr(RUN, "_api_snapshot", lambda: next(calls))
    assert RUN.main() == 2
    output = capsys.readouterr().out
    assert output.startswith("CUSTODIA_QBIT_0026=BLOQUEADA_")
    assert "PERMISO_BORRADO_FISICO=NO" in output
    assert "jf-unique" not in output
    assert "TORRENTS_MODIFICADOS=0" in output


def test_diario_que_cambia_entre_consultas_bloquea(monkeypatch, capsys):
    s, j, n = base()
    patch_sources(monkeypatch, s, j, n)
    changed = deepcopy(j)
    changed[8][0]["intent"]["files"][0]["size_bytes"] = 2
    calls = iter([deepcopy(j), changed])
    monkeypatch.setattr(RUN, "_journals_readonly", lambda: next(calls))
    assert RUN.main() == 2
    assert "PERMISO_BORRADO_FISICO=NO" in capsys.readouterr().out


def test_ntfs_que_cambia_entre_consultas_bloquea(monkeypatch, capsys):
    s, j, n = base()
    patch_sources(monkeypatch, s, j, n)
    changed = deepcopy(n)
    changed[0]["ntfs_verified"] = False
    calls = iter([deepcopy(n), changed])
    monkeypatch.setattr(RUN, "_evidence_windows", lambda: next(calls))
    assert RUN.main() == 2
    assert "ARCHIVOS_ELIMINADOS=0" in capsys.readouterr().out


def test_fallo_de_fuente_no_se_convierte_en_estado_seguro(monkeypatch, capsys):
    s, j, n = base()
    patch_sources(monkeypatch, s, j, n)
    monkeypatch.setattr(
        RUN, "_api_snapshot",
        lambda: (_ for _ in ()).throw(RuntimeError("token_secreto")),
    )
    assert RUN.main() == 2
    output = capsys.readouterr().out
    assert "token_secreto" not in output
    assert "PERMISO_BORRADO_FISICO=NO" in output
