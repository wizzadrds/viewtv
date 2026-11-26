"""Inventario qBit 0020: los extras siempre quedan protegidos.

Todas las fuentes son diccionarios de sandbox; no se consulta la API real.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from test_retirada_preflight_0018 import base
from worker.retirement_inventory_0020 import analizar_inventario


def fixture():
    snapshot, journals, _ = base()
    return snapshot, journals


def test_solo_archivo_publicado_no_genera_candidatos_de_borrado():
    snapshot, journals = fixture()
    summary = analizar_inventario(snapshot, journals)
    assert summary["descargas_analizadas"] == 1
    assert summary["archivos_publicados_correlacionados"] == 1
    assert summary["archivos_no_publicados_protegidos"] == 0
    assert "autoriza_borrado" not in summary
    assert "rutas" not in summary


def test_archivos_extra_metadatos_permanecen_protegidos():
    snapshot, journals = fixture()
    snapshot["qbittorrent"]["8"]["files"] += [
        {"name": "Torrent/Info.nfo", "size": 40, "progress": 1, "priority": 1},
        {"name": "Torrent/AUX.txt", "size": 99, "progress": 1, "priority": 1},
        {"name": "Torrent/Posters/cover.jpg", "size": 7, "progress": 1, "priority": 1},
    ]
    summary = analizar_inventario(snapshot, journals)
    assert summary["archivos_qbit"] == 4
    assert summary["archivos_publicados_correlacionados"] == 1
    assert summary["archivos_no_publicados_protegidos"] == 3
    assert summary["extra_tipo_metadato"] == 3
    assert summary["no_normalizables"] == 1
    assert summary["suma_bytes_logicos_no_publicados"] == 146
    assert "borrar" not in str(summary).lower()


def test_extra_video_tambien_es_protegido_y_no_se_autoriza_borrarlo():
    snapshot, journals = fixture()
    snapshot["qbittorrent"]["8"]["files"].append(
        {"name": "Torrent/Otro.mkv", "size": 10000, "progress": 1, "priority": 1}
    )
    summary = analizar_inventario(snapshot, journals)
    assert summary["extra_tipo_video"] == 1
    assert summary["archivos_no_publicados_protegidos"] == 1


def test_nombre_de_subtitulo_y_desconocido_no_se_autorizan():
    snapshot, journals = fixture()
    snapshot["qbittorrent"]["8"]["files"] += [
        {"name": "Torrent/other.ass", "size": 15, "progress": 1},
        {"name": "Torrent/mystery.dat", "size": 60, "progress": 1},
    ]
    summary = analizar_inventario(snapshot, journals)
    assert summary["extra_tipo_subtitulo"] == 1
    assert summary["extra_tipo_otro"] == 1


def test_tamano_diferente_no_es_como_manifest_y_se_bloquea():
    snapshot, journals = fixture()
    snapshot["qbittorrent"]["8"]["files"][0]["size"] = 999
    summary = analizar_inventario(snapshot, journals)
    assert summary["tamanos_incompatibles"] == 1
    assert summary["archivos_publicados_correlacionados"] == 0
    assert summary["archivos_no_publicados_protegidos"] == 1


def test_torrent_no_disponible_se_marca_sin_extras_optimistas():
    snapshot, journals = fixture()
    snapshot["qbittorrent"]["8"]["estado_consulta"] = "error_consulta"
    summary = analizar_inventario(snapshot, journals)
    assert summary["qbit_no_disponible"] == 1
    assert summary["descargas_analizadas"] == 0


@pytest.mark.parametrize("edit", ["duplicate", "invalid_journal", "invalid_id", "invalid_input"])
def test_datos_ambiguos_fallan_cerrado(edit):
    snapshot, journals = fixture()
    if edit == "duplicate":
        snapshot["qbittorrent"]["8"]["files"].append(
            deepcopy(snapshot["qbittorrent"]["8"]["files"][0])
        )
    elif edit == "invalid_journal":
        journals[8][0]["intent"]["files"][0]["size_bytes"] = 0
    elif edit == "invalid_id":
        snapshot["descargas"][0]["id"] = "8"
    else:
        snapshot["qbittorrent"] = []
    with pytest.raises(ValueError):
        analizar_inventario(snapshot, journals)


def test_nombres_privados_y_hashes_no_se_imprimen_ni_se_exponen():
    snapshot, journals = fixture()
    snapshot["qbittorrent"]["8"]["files"].append(
        {"name": "Torrent/privado-identificable.txt", "size": 3}
    )
    summary = analizar_inventario(snapshot, journals)
    assert "privado-identificable" not in str(summary)
    assert "Torrent/" not in str(summary)
    assert "a" * 40 not in str(summary)
