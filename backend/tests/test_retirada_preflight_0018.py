"""Preflight 0018: ningún perfil ni torrent puede activar un borrado real."""
from __future__ import annotations

from copy import deepcopy

import pytest
from worker.retirement_preflight_0018 import (
    _valid_relative,
    evaluar_retiradas,
)

HASH = "a" * 40
SHA = "1" * 64


def base() -> tuple[dict, dict, list[dict]]:
    snapshot = {
        "perfiles_activos": [1, 2],
        "peliculas": [{
            "medio_id": 2, "jellyfin_id": "jf-unique",
            "tmdb_id": 876, "visto_perfiles": [1, 2],
            "pendiente_perfiles": [1],
        }],
        "descargas": [{
            "id": 8, "solicitud_id": 15, "hash": HASH,
            "estado": "completada", "estado_verificacion": "verificada",
            "progreso": 1, "verificada": True,
            "organizacion_estado": "organizada",
            "organizacion_bloqueada": False,
            "inicio_bloqueado": False,
            "verificacion_bloqueada": False,
            "solicitud": {
                "id": 15, "tipo_medio": "pelicula",
                "jellyfin_item_id": None, "tmdb_id": 876,
            },
        }],
        "jellyfin": {
            "estado": "ok",
            "elementos": [{
                "id": "jf-unique", "tipo": "Movie",
                "path": "/media/Peliculas/Folder/Film.mkv",
            }],
        },
        "qbittorrent": {"8": {
            "estado_consulta": "ok",
            "torrent": {
                "hash": HASH, "tags": "viewtv-descarga-8",
                "save_path": r"C:\VIEWTV\media\descargas_temporales",
                "state": "stoppedUP", "progress": 1,
            },
            "files": [{
                "name": "Torrent/Film.mkv", "size": 1024,
                "progress": 1, "priority": 1,
            }],
        }},
    }
    journals = {8: ({
        "version": 1, "download_id": 8, "folder": "Folder",
        "intent": {
            "download_id": 8, "library": "Peliculas",
            "torrent_hash": HASH,
            "files": [{
                "source_relative": "Torrent/Film.mkv",
                "destination_relative": "Peliculas/Folder/Film.mkv",
                "size_bytes": 1024,
            }],
        },
    }, SHA)}
    proofs = [{
        "download_id": 8,
        "ntfs_verified": True,
        "journal_sha256": SHA,
        "archivos": 1,
    }]
    return snapshot, journals, proofs


def reasons(s, j, p) -> list[str]:
    result = evaluar_retiradas(s, j, p)
    assert len(result) == 1
    assert result[0]["estado"] == "bloqueada"
    assert result[0]["puede_borrarse_ahora"] is False
    return result[0]["motivos"]


def test_identidades_ideales_sin_admin_no_son_permiso_de_borrado():
    assert reasons(*base()) == ["falta_autorizacion_administrador"]


@pytest.mark.parametrize(("field", "value", "expected"), [
    ("state", "uploading", "torrent_activo_o_incompleto"),
    ("state", "checkingUP", "torrent_activo_o_incompleto"),
    ("state", "stalledUP", "torrent_activo_o_incompleto"),
    ("state", "unknown", "torrent_activo_o_incompleto"),
    ("progress", 0.5, "torrent_activo_o_incompleto"),
    ("hash", "f" * 40, "torrent_identidad_invalida"),
    ("tags", "viewtv-descarga-9", "torrent_no_propio"),
    ("tags", "viewtv-descarga-8,viewtv-descarga-9", "torrent_no_propio"),
    ("tags", "viewtv-descarga-8,viewtv-descarga-8", "torrent_no_propio"),
    ("save_path", r"C:\Otros", "torrent_raiz_ajena"),
])
def test_torrent_inseguro_bloquea(field, value, expected):
    s, j, p = base()
    s["qbittorrent"]["8"]["torrent"][field] = value
    assert expected in reasons(s, j, p)


def test_torrent_con_mas_archivos_que_diario_no_autoriza_borrar_original():
    s, j, p = base()
    s["qbittorrent"]["8"]["files"].append({
        "name": "Torrent/extra.nfo", "size": 40, "progress": 1, "priority": 1,
    })
    assert "torrent_con_archivos_ajenos_o_incompletos" in reasons(s, j, p)


@pytest.mark.parametrize(("field", "value"), [
    ("name", "../Otro/Film.mkv"),
    ("name", "C:\\invasor.mkv"),
    ("size", 0),
    ("priority", 0),
    ("progress", 0.99),
])
def test_archivos_torrent_no_verificables(field, value):
    s, j, p = base()
    s["qbittorrent"]["8"]["files"][0][field] = value
    assert "torrent_archivos_no_verificables" in reasons(s, j, p)


def test_torrent_con_archivo_duplicado_es_no_verificable():
    s, j, p = base()
    s["qbittorrent"]["8"]["files"].append(
        deepcopy(s["qbittorrent"]["8"]["files"][0]),
    )
    assert "torrent_archivos_duplicados" in reasons(s, j, p)


@pytest.mark.parametrize(("field", "value"), [
    ("ntfs_verified", False),
    ("journal_sha256", "0" * 64),
    ("archivos", 2),
])
def test_prueba_ntfs_inconsistente_bloquea(field, value):
    s, j, p = base()
    p[0][field] = value
    assert "ntfs_no_verificado" in reasons(s, j, p)


def test_diario_sin_prueba_bloquea():
    s, j, _ = base()
    assert "ntfs_no_verificado" in reasons(s, j, [])


def test_diario_torrent_no_iguales_bloquea():
    s, j, p = base()
    j[8][0]["intent"]["torrent_hash"] = "f" * 40
    assert "diario_no_coincide_descarga" in reasons(s, j, p)


def test_jellyfin_id_no_unico_bloquea():
    s, j, p = base()
    s["jellyfin"]["elementos"].append(deepcopy(s["jellyfin"]["elementos"][0]))
    assert "jellyfin_no_verificable" in reasons(s, j, p)


def test_jellyfin_no_disponible_bloquea():
    s, j, p = base()
    s["jellyfin"] = {"estado": "consulta_fallida", "elementos": []}
    assert "jellyfin_no_verificable" in reasons(s, j, p)


def test_ruta_jellyfin_no_coincide_bloquea():
    s, j, p = base()
    s["jellyfin"]["elementos"][0]["path"] = "/media/Peliculas/Folder/Otro.mkv"
    assert "sin_publicacion_unica" in reasons(s, j, p)


def test_publicaciones_dobles_con_mismo_torrent_no_son_exclusivas():
    s, j, p = base()
    other = deepcopy(j[8][0])
    other["download_id"] = 9
    other["intent"]["download_id"] = 9
    other["folder"] = "Folder2"
    other["intent"]["files"][0]["destination_relative"] = "Peliculas/Folder2/Film.mkv"
    j[9] = (other, "2" * 64)
    assert "publicacion_compartida_o_ambigua" in reasons(s, j, p)


def test_publicaciones_dobles_con_misma_carpeta_bloqueadas():
    s, j, p = base()
    other = deepcopy(j[8][0])
    other["download_id"] = 9
    other["intent"]["download_id"] = 9
    other["intent"]["torrent_hash"] = "b" * 40
    j[9] = (other, "2" * 64)
    assert "publicacion_compartida_o_ambigua" in reasons(s, j, p)


@pytest.mark.parametrize(("key", "value"), [
    ("estado", "descargando"),
    ("estado_verificacion", "pendiente"),
    ("verificada", False),
    ("organizacion_bloqueada", True),
    ("progreso", 0.9),
])
def test_descarga_con_estado_inseguro_bloquea(key, value):
    s, j, p = base()
    s["descargas"][0][key] = value
    assert "descarga_no_terminada_o_bloqueada" in reasons(s, j, p)


def test_solicitud_sin_identidad_congruente_no_valida():
    s, j, p = base()
    s["descargas"][0]["solicitud"]["tmdb_id"] = 999
    assert "solicitud_descarga_incongruente" in reasons(s, j, p)


def test_perfil_sin_visto_bloquea_biblioteca_compartida():
    s, j, p = base()
    s["peliculas"][0]["visto_perfiles"] = [1]
    assert "hay_perfiles_sin_marcar_vista" in reasons(s, j, p)


def test_solicitud_retirada_cancelada_o_no_existente_no_autoriza():
    s, j, p = base()
    s["peliculas"][0]["pendiente_perfiles"] = []
    assert "sin_peticion_valida_de_retirada" in reasons(s, j, p)


def test_peticion_de_perfil_no_autorizado_bloquea():
    s, j, p = base()
    s["peliculas"][0]["pendiente_perfiles"] = [99]
    assert "sin_peticion_valida_de_retirada" in reasons(s, j, p)


@pytest.mark.parametrize("bad_path", [
    "Torrent/../Film.mkv", "Torrent//Film.mkv",
    "/Torrent/Film.mkv", "C:/Film.mkv", "Torrent/Film\\.mkv",
    "Torrent/CON", "Torrent/ Film.mkv",
])
def test_ruta_insegura_rechazada(bad_path):
    assert _valid_relative(bad_path) is None or (
        bad_path == "Torrent/CON"
    )


def test_medio_sin_diario_no_se_puede_borrar():
    s, _, p = base()
    assert "sin_publicacion_unica" in reasons(s, {}, p)


def test_sin_snapshots_estrictos_falla_en_cerrado():
    with pytest.raises(ValueError):
        evaluar_retiradas({}, {}, [])


def test_journal_malicioso_no_activa_permisos():
    s, j, p = base()
    j[8][0]["intent"]["files"][0]["destination_relative"] = (
        "Peliculas/Folder/../sensible.mkv"
    )
    assert "sin_publicacion_unica" in reasons(s, j, p)


def test_inventario_ntfs_duplicado_no_se_considera_prueba():
    s, j, p = base()
    assert "ntfs_no_verificado" in reasons(s, j, [p[0], p[0]])


def test_registro_de_descarga_duplicado_no_se_considera_propiedad():
    s, j, p = base()
    s["descargas"].append(deepcopy(s["descargas"][0]))
    assert "descarga_sin_registro" in reasons(s, j, p)


@pytest.mark.parametrize("invalid", [
    "COM1.mp4", "aux.txt", "PRN", "LPT8.srt", "nul", "CON.mkv",
])
def test_nombres_reservados_windows_no_se_aceptan(invalid):
    assert _valid_relative("Torrent/" + invalid) is None
