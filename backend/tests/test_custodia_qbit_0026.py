"""0026 — qBit activo y metadatos extras nunca habilitan borrado.

Fuentes 100% ficticias. Sin requests externas ni cambios de torrent.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from test_retirada_preflight_0018 import base
from worker.retirement_qbit_custody_0026 import (
    CustodiaNoConfiable,
    evaluar_custodia_qbit,
)


def sample() -> tuple[dict, dict]:
    snap, journals, _ = base()
    return snap, journals


def summary(s, j):
    result = evaluar_custodia_qbit(s, j)
    assert result["autoriza_borrado_fisico"] is False
    assert result["bloqueo_jellyfin_y_qbit_transaccional"] is False
    assert result["archivos_eliminados"] == 0
    assert result["torrents_modificados"] == 0
    assert "Torrent/" not in str(result)
    return result


def test_torrent_aparentemente_ideal_no_es_autorizacion():
    s, j = sample()
    result = summary(s, j)
    assert result["descargas"] == 1
    assert result["torrent_completo_y_en_reposo_reportado"] == 1
    assert result["torrent_no_en_reposo_o_incompleto"] == 0
    assert result["archivos_publicados_correlacionados"] == 1
    assert result["archivos_extra_protegidos"] == 0
    assert result["ficheros_extra_conservados"] is True


@pytest.mark.parametrize("state", [
    "uploading", "stalledUP", "checkingUP", "moving", "forcedUP",
    "queuedUP", "stoppedDL", "pausedDL", "downloading", "unknown",
])
def test_estado_no_reposo_deja_todo_protegido(state):
    s, j = sample()
    s["qbittorrent"]["8"]["torrent"]["state"] = state
    result = summary(s, j)
    assert result["torrent_completo_y_en_reposo_reportado"] == 0
    assert result["torrent_no_en_reposo_o_incompleto"] == 1


@pytest.mark.parametrize("state", ["pausedUP", "stoppedUP"])
def test_estados_reposo_no_son_licencia_para_borrar(state):
    s, j = sample()
    s["qbittorrent"]["8"]["torrent"]["state"] = state
    s["qbittorrent"]["8"]["files"].append({
        "name": "Torrent/extra.nfo", "size": 35,
        "progress": 1, "priority": 1,
    })
    result = summary(s, j)
    assert result["torrent_completo_y_en_reposo_reportado"] == 1
    assert result["archivos_extra_protegidos"] == 1
    assert result["extras_tipo_metadato"] == 1


@pytest.mark.parametrize(("name", "bucket"), [
    ("Torrent/extra.nfo", "metadato"),
    ("Torrent/info.txt", "metadato"),
    ("Torrent/poster.jpeg", "metadato"),
    ("Torrent/pelicula.mkv", "video"),
    ("Torrent/subtitulo.srt", "subtitulo"),
    ("Torrent/raro.xyz", "otro"),
])
def test_tipo_de_extra_nunca_concede_permiso(name, bucket):
    s, j = sample()
    s["qbittorrent"]["8"]["files"].append({
        "name": name, "size": 1, "progress": 1, "priority": 1,
    })
    result = summary(s, j)
    assert result["archivos_extra_protegidos"] == 1
    assert result["extras_tipo_" + bucket] == 1
    assert result["bytes_logicos_extras_protegidos"] == 1


@pytest.mark.parametrize("name", [
    "Torrent/CON.txt", "Torrent/..", "../extra.nfo",
    "Torrent/extra.", "Torrent/secret?wrong.nfo",
    "Torrent/file .txt",
])
def test_extras_nombre_no_normalizable_tambien_protegidos(name):
    s, j = sample()
    s["qbittorrent"]["8"]["files"].append({
        "name": name, "size": 15, "progress": 1, "priority": 1,
    })
    result = summary(s, j)
    assert result["extras_con_nombre_no_normalizable"] == 1
    assert result["archivos_extra_protegidos"] == 1


@pytest.mark.parametrize(("field", "value"), [
    ("hash", "f" * 40),
    ("tags", "viewtv-descarga-9"),
    ("tags", "viewtv-descarga-8,viewtv-descarga-9"),
    ("tags", "viewtv-descarga-8,viewtv-descarga-8"),
    ("save_path", r"C:\Otra"),
])
def test_procedencia_inconsistente_bloquea_la_propiedad(field, value):
    s, j = sample()
    s["qbittorrent"]["8"]["torrent"][field] = value
    result = summary(s, j)
    assert result["torrent_propiedad_o_ruta_inconsistente"] == 1
    assert result["autoriza_borrado_fisico"] is False


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("size", 2, "archivos_con_tamano_incompatible"),
    ("progress", 0.5, "archivos_con_progreso_incompleto"),
    ("priority", 0, "archivos_con_prioridad_excluida"),
])
def test_archivo_publicado_no_ideal_se_registra_pero_no_autoriza(
    field, value, reason,
):
    s, j = sample()
    s["qbittorrent"]["8"]["files"][0][field] = value
    result = summary(s, j)
    assert result[reason] == 1
    assert result["autoriza_borrado_fisico"] is False


def test_archivo_de_publicacion_con_tamano_distinto_se_protege():
    s, j = sample()
    s["qbittorrent"]["8"]["files"][0]["size"] = 2000
    result = summary(s, j)
    assert result["archivos_extra_protegidos"] == 1
    assert result["archivos_publicados_correlacionados"] == 0
    assert result["archivos_con_tamano_incompatible"] == 1


@pytest.mark.parametrize(("kind", "value"), [
    ("missing_journal", None),
    ("duplicated_download", None),
    ("missing_torrent", None),
    ("extra_torrent", None),
    ("torrent_files_none", None),
    ("duplicated_file", None),
    ("invalid_file_name", None),
    ("invalid_file_size", 0),
    ("file_priority_bool", True),
    ("file_progress_nan", float("nan")),
    ("torrent_progress_nan", float("nan")),
    ("invalid_journal_id", 9),
    ("invalid_journal_size", 0),
    ("invalid_journal_name", "../mal"),
    ("journal_duplicate_file", None),
    ("invalid_download_id", "8"),
    ("invalid_hash_state", None),
])
def test_fuentes_incompletas_fallan_cerrado(kind, value):
    s, j = sample()
    q = s["qbittorrent"]["8"]
    if kind == "missing_journal":
        j.clear()
    elif kind == "duplicated_download":
        s["descargas"].append(deepcopy(s["descargas"][0]))
        s["qbittorrent"]["9"] = deepcopy(q)
    elif kind == "missing_torrent":
        del s["qbittorrent"]["8"]
    elif kind == "extra_torrent":
        s["qbittorrent"]["9"] = deepcopy(q)
    elif kind == "torrent_files_none":
        q["files"] = None
    elif kind == "duplicated_file":
        q["files"].append(deepcopy(q["files"][0]))
    elif kind == "invalid_file_name":
        q["files"][0]["name"] = None
    elif kind == "invalid_file_size":
        q["files"][0]["size"] = value
    elif kind == "file_priority_bool":
        q["files"][0]["priority"] = value
    elif kind == "file_progress_nan":
        q["files"][0]["progress"] = value
    elif kind == "torrent_progress_nan":
        q["torrent"]["progress"] = value
    elif kind == "invalid_journal_id":
        j[8][0]["download_id"] = value
    elif kind == "invalid_journal_size":
        j[8][0]["intent"]["files"][0]["size_bytes"] = value
    elif kind == "invalid_journal_name":
        j[8][0]["intent"]["files"][0]["source_relative"] = value
    elif kind == "journal_duplicate_file":
        j[8][0]["intent"]["files"].append(
            deepcopy(j[8][0]["intent"]["files"][0]),
        )
    elif kind == "invalid_download_id":
        s["descargas"][0]["id"] = value
    elif kind == "invalid_hash_state":
        q["torrent"]["progress"] = None
    with pytest.raises(CustodiaNoConfiable):
        evaluar_custodia_qbit(s, j)


@pytest.mark.parametrize("value", [0.99, -0.1, True, 1.1, None])
def test_progreso_torrent_invalido_o_incompleto_denegado(value):
    s, j = sample()
    s["qbittorrent"]["8"]["torrent"]["progress"] = value
    if value == 0.99:
        assert summary(s, j)["torrent_no_en_reposo_o_incompleto"] == 1
    else:
        with pytest.raises(CustodiaNoConfiable):
            evaluar_custodia_qbit(s, j)


def test_cuentas_agrupadas_no_revelan_identidades():
    s, j = sample()
    s["qbittorrent"]["8"]["files"].append({
        "name": "Torrent/secreto-privado.nfo",
        "size": 99, "progress": 1, "priority": 1,
    })
    summary_value = summary(s, j)
    assert "secreto-privado" not in str(summary_value)
    assert "aaaaaaaaaaaa" not in str(summary_value)
    assert "jf-unique" not in str(summary_value)


def test_cambios_simultaneos_de_metadatos_nunca_autorizan():
    s, j = sample()
    s["qbittorrent"]["8"]["torrent"]["state"] = "uploading"
    s["qbittorrent"]["8"]["files"].append({
        "name": "Torrent/readme.txt", "size": 488,
        "progress": 1, "priority": 1,
    })
    out = summary(s, j)
    assert out["torrent_no_en_reposo_o_incompleto"] == 1
    assert out["archivos_extra_protegidos"] == 1
    assert out["extras_tipo_metadato"] == 1
    assert out["bytes_logicos_extras_protegidos"] == 488
