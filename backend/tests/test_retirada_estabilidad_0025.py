"""0025: detectar drift de qBit/Jellyfin/SQL/NTFS con dos snapshots.

Pruebas 100% sintéticas: sin contenedores, reproducción, torrentes ni medios.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from test_retirada_preflight_0018 import base
from test_retirada_revision_runner_0024 import MOD, fixture, patch_sources
from worker.retirement_evidence_stability_0025 import (
    EvidenciaInestable,
    certificar_doble_lectura,
)


def valid():
    snapshot, journals, ntfs = base()
    return snapshot, journals, ntfs


def check(s1, j1, n1, s2=None, j2=None, n2=None):
    return certificar_doble_lectura(
        s1, s2 if s2 is not None else deepcopy(s1),
        j1, j2 if j2 is not None else deepcopy(j1),
        n1, n2 if n2 is not None else deepcopy(n1),
    )


def test_dos_fuentes_iguales_son_una_observacion_no_un_bloqueo():
    s, j, n = valid()
    result = check(s, j, n)
    assert result == {
        "estado": "dos_lecturas_coincidentes",
        "snapshots_completos": 2,
        "lecturas_diarios": 2,
        "auditorias_ntfs": 2,
        "inmovilizacion_qbit_y_jellyfin": False,
        "habilita_borrado_fisico": False,
    }
    assert "jellyfin_id" not in str(result)
    assert "torrent" not in str(result)


@pytest.mark.parametrize(("kind", "value"), [
    ("torrent_state", "uploading"),
    ("torrent_progress", 0.98),
    ("torrent_tag", "otro-tag"),
    ("torrent_hash", "b" * 40),
    ("torrent_path", r"C:\Otra"),
    ("torrent_query", "error_consulta"),
    ("file_progress", 0.94),
    ("file_priority", 0),
    ("file_size", 1025),
    ("file_name", "Torrent/Otra.mkv"),
    ("jellyfin_path", "/media/Peliculas/Otra/Otra.mkv"),
    ("jellyfin_id", "jf-otro"),
    ("jf_status", "consulta_fallida"),
    ("download_status", "pausada"),
    ("download_hash", "b" * 40),
    ("download_lock", True),
    ("movie_request", []),
    ("watched", [1]),
    ("active_profiles", [1, 2, 3]),
])
def test_cualquier_cambio_entre_snapshots_bloquea(kind, value):
    original, j, n = valid()
    changed = deepcopy(original)
    movie = changed["peliculas"][0]
    download = changed["descargas"][0]
    qbit = changed["qbittorrent"]["8"]
    torrent = qbit["torrent"]
    qfile = qbit["files"][0]
    if kind == "torrent_state":
        torrent["state"] = value
    elif kind == "torrent_progress":
        torrent["progress"] = value
    elif kind == "torrent_tag":
        torrent["tags"] = value
    elif kind == "torrent_hash":
        torrent["hash"] = value
    elif kind == "torrent_path":
        torrent["save_path"] = value
    elif kind == "torrent_query":
        qbit["estado_consulta"] = value
    elif kind == "file_progress":
        qfile["progress"] = value
    elif kind == "file_priority":
        qfile["priority"] = value
    elif kind == "file_size":
        qfile["size"] = value
    elif kind == "file_name":
        qfile["name"] = value
    elif kind == "jellyfin_path":
        changed["jellyfin"]["elementos"][0]["path"] = value
    elif kind == "jellyfin_id":
        changed["jellyfin"]["elementos"][0]["id"] = value
    elif kind == "jf_status":
        changed["jellyfin"]["estado"] = value
    elif kind == "download_status":
        download["estado"] = value
    elif kind == "download_hash":
        download["hash"] = value
    elif kind == "download_lock":
        download["organizacion_bloqueada"] = value
    elif kind == "movie_request":
        movie["pendiente_perfiles"] = value
    elif kind == "watched":
        movie["visto_perfiles"] = value
    elif kind == "active_profiles":
        changed["perfiles_activos"] = value
    with pytest.raises(EvidenciaInestable):
        check(original, j, n, s2=changed)


@pytest.mark.parametrize(("kind", "value"), [
    ("journal_sha", "f" * 64),
    ("source_path", "Torrent/Otro.mkv"),
    ("journal_hash", "f" * 40),
    ("journal_size", 999),
    ("journal_id", 999),
    ("ntfs_hash", "a" * 64),
    ("ntfs_verified", False),
    ("ntfs_files", 2),
])
def test_cambios_diarios_y_ntfs_bloquean(kind, value):
    s, j, n = valid()
    changed_j = deepcopy(j)
    changed_n = deepcopy(n)
    if kind == "journal_sha":
        changed_j[8] = (changed_j[8][0], value)
    elif kind == "source_path":
        changed_j[8][0]["intent"]["files"][0]["source_relative"] = value
    elif kind == "journal_hash":
        changed_j[8][0]["intent"]["torrent_hash"] = value
    elif kind == "journal_size":
        changed_j[8][0]["intent"]["files"][0]["size_bytes"] = value
    elif kind == "journal_id":
        changed_j[8][0]["download_id"] = value
    elif kind == "ntfs_hash":
        changed_n[0]["journal_sha256"] = value
    elif kind == "ntfs_verified":
        changed_n[0]["ntfs_verified"] = value
    elif kind == "ntfs_files":
        changed_n[0]["archivos"] = value
    with pytest.raises(EvidenciaInestable):
        check(s, j, n, j2=changed_j, n2=changed_n)


@pytest.mark.parametrize(("kind", "value"), [
    ("missing_movies", None),
    ("invalid_jellyfin", []),
    ("not_json", object()),
    ("nan_progress", float("nan")),
    ("huge_json", "a" * 2_000_100),
    ("bad_journal_hash", "m" * 64),
    ("bad_ntfs_id", 0),
    ("duplicate_ntfs", True),
    ("journal_unsafe_id", True),
    ("journal_unsafe_tuple", "invalid"),
    ("non_list_ntfs", {}),
])
def test_fuenteno_verificable_siempre_bloquea(kind, value):
    s, j, n = valid()
    s, j, n = deepcopy(s), deepcopy(j), deepcopy(n)
    if kind == "missing_movies":
        del s["peliculas"]
    elif kind == "invalid_jellyfin":
        s["jellyfin"] = value
    elif kind == "not_json":
        s["token"] = value
    elif kind == "nan_progress":
        s["qbittorrent"]["8"]["torrent"]["progress"] = value
    elif kind == "huge_json":
        s["qbittorrent"]["8"]["torrent"]["state"] = value
    elif kind == "bad_journal_hash":
        j[8] = (j[8][0], value)
    elif kind == "bad_ntfs_id":
        n[0]["download_id"] = value
    elif kind == "duplicate_ntfs":
        n.append(deepcopy(n[0]))
    elif kind == "journal_unsafe_id":
        j[True] = j.pop(8)
    elif kind == "journal_unsafe_tuple":
        j[8] = value
    elif kind == "non_list_ntfs":
        n = value
    with pytest.raises(EvidenciaInestable):
        check(s, j, n)


def test_orden_de_diarios_y_ntfs_no_cambia_la_identidad():
    s, j, n = valid()
    second = deepcopy(j)
    second[10] = (
        {"download_id": 10, "version": 1, "intent": {"files": []}},
        "2" * 64,
    )
    first = deepcopy(second)
    first = dict(reversed(list(first.items())))
    extra = {
        "download_id": 10, "journal_sha256": "2" * 64,
        "ntfs_verified": False, "archivos": 1,
    }
    n2 = n + [extra]
    assert check(s, first, n2, j2=second, n2=list(reversed(n2)))[
        "habilita_borrado_fisico"
    ] is False


def test_runner_doble_snapshot_coincidente_en_datos_sinteticos(monkeypatch, capsys):
    snapshot, journals, ntfs, detail = fixture()
    patch_sources(monkeypatch, snapshot, journals, ntfs, detail)
    assert MOD.main(["--titulo", "Pelicula ficticia", "--anio", "2026"]) == 0
    output = capsys.readouterr().out
    assert "DOBLE_SNAPSHOT_SQL_JELLYFIN_QBIT=COINCIDENTE" in output
    assert "DOBLE_INVENTARIO_DIARIOS_NTFS=COINCIDENTE" in output
    assert "EXCLUSION_TRANSACCIONAL_QBIT_JELLYFIN=NO" in output
    assert "PERMISO_BORRADO_FISICO=NO" in output


@pytest.mark.parametrize(("kind", "value"), [
    ("state", "stoppedUP"),
    ("progress", 0.4),
    ("tag", "otro"),
    ("file", "Torrent/otro.mkv"),
    ("jf", "/media/Otro.mkv"),
    ("profile", []),
])
def test_runner_0024_detecta_drift_entre_dos_snapshots(monkeypatch, capsys, kind, value):
    snapshot, journals, ntfs, detail = fixture()
    patch_sources(monkeypatch, snapshot, journals, ntfs, detail)
    second = deepcopy(snapshot)
    qbit = second["qbittorrent"]["8"]
    if kind == "state":
        qbit["torrent"]["state"] = value
    elif kind == "progress":
        qbit["torrent"]["progress"] = value
    elif kind == "tag":
        qbit["torrent"]["tags"] = value
    elif kind == "file":
        qbit["files"][0]["name"] = value
    elif kind == "jf":
        second["jellyfin"]["elementos"][0]["path"] = value
    elif kind == "profile":
        second["peliculas"][0]["pendiente_perfiles"] = value
    calls = iter([deepcopy(snapshot), second])
    monkeypatch.setattr(MOD, "_api_snapshot", lambda: next(calls))
    assert MOD.main(["--titulo", "Pelicula ficticia", "--anio", "2026"]) == 2
    output = capsys.readouterr().out
    assert "BLOQUEADA_DATOS_NO_CONFIABLES" in output
    assert "PERMISO_BORRADO_FISICO=NO" in output
    assert "TORRENTS_MODIFICADOS=0" in output


def test_runner_0024_detecta_cambio_diario(monkeypatch, capsys):
    snapshot, journals, ntfs, detail = fixture()
    patch_sources(monkeypatch, snapshot, journals, ntfs, detail)
    changed = deepcopy(journals)
    changed[8][0]["intent"]["files"][0]["size_bytes"] = 2048
    calls = iter([deepcopy(journals), changed])
    monkeypatch.setattr(MOD, "_journals_readonly", lambda: next(calls))
    assert MOD.main(["--titulo", "Pelicula ficticia", "--anio", "2026"]) == 2
    assert "PERMISO_BORRADO_FISICO=NO" in capsys.readouterr().out
