"""0024: solicitud desde perfil realista sin convertirla en permiso físico.

Solo datos sintéticos, ninguna película ni cuenta ni fuente productiva.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from test_retirada_preflight_0018 import base
from worker.retirement_preflight_0018 import evaluar_retiradas
from worker.retirement_request_review_0024 import (
    RevisionNoConfiable,
    resumir_revision,
)


def setup():
    snapshot, journals, ntfs = base()
    detail = {
        "estado": "unica",
        "medio_id": 2,
        "jellyfin_id": "jf-unique",
        "perfiles_activos": [1, 2],
        "visto_perfiles": [1, 2],
        "pendiente_perfiles": [1],
        "solicitudes_canceladas": 0,
    }
    return snapshot, journals, ntfs, detail


def review(snapshot, journals, ntfs, detail):
    assessments = evaluar_retiradas(snapshot, journals, ntfs)
    return resumir_revision(snapshot, assessments, detail)


def test_peticion_de_un_perfil_y_otra_persona_pendiente_nunca_borra():
    snapshot, journals, ntfs, detail = setup()
    snapshot["peliculas"][0]["visto_perfiles"] = [1]
    detail["visto_perfiles"] = [1]
    result = review(snapshot, journals, ntfs, detail)
    assert result["estado"] == "pendiente_revision_bloqueada"
    assert result["solicitud_valida_registrada"] is True
    assert result["perfiles_activos"] == 2
    assert result["perfiles_con_visto"] == 1
    assert result["perfiles_sin_visto"] == 1
    assert result["solicitudes_pendientes"] == 1
    assert result["vista_en_todos_los_perfiles"] is False
    assert "hay_perfiles_sin_marcar_vista" in result["bloqueos"]
    assert "falta_autorizacion_administrador" in result["bloqueos"]
    assert result["autoriza_borrado_fisico"] is False
    assert result["aprobacion_administrativa_emitida"] is False
    assert result["archivos_eliminados"] == 0
    assert result["torrents_modificados"] == 0
    assert "jf-unique" not in str(result)


def test_ni_aunque_todos_la_vieran_es_permisible_borrar():
    snapshot, journals, ntfs, detail = setup()
    result = review(snapshot, journals, ntfs, detail)
    assert result["vista_en_todos_los_perfiles"] is True
    assert result["bloqueos"] == ["falta_autorizacion_administrador"]
    assert result["autoriza_borrado_fisico"] is False


def test_si_qbit_esta_activo_sigue_bloqueado_aun_todos_vistos():
    snapshot, journals, ntfs, detail = setup()
    snapshot["qbittorrent"]["8"]["torrent"]["state"] = "uploading"
    result = review(snapshot, journals, ntfs, detail)
    assert "torrent_activo_o_incompleto" in result["bloqueos"]
    assert result["autoriza_borrado_fisico"] is False


def test_solicitud_cancelada_y_vista_conservada_no_autoriza():
    snapshot, journals, ntfs, detail = setup()
    snapshot["peliculas"][0]["pendiente_perfiles"] = []
    detail["pendiente_perfiles"] = []
    detail["solicitudes_canceladas"] = 1
    result = review(snapshot, journals, ntfs, detail)
    assert result["estado"] == "sin_peticion_valida"
    assert result["perfiles_con_visto"] == 2
    assert result["solicitudes_pendientes"] == 0
    assert "sin_peticion_valida_de_retirada" in result["bloqueos"]


@pytest.mark.parametrize("change", [
    "visto", "retirada", "activos", "identidad", "medio", "desconocida",
    "medios_duplicados", "preflight_duplicado",
])
def test_si_difieren_las_dos_consultas_no_se_revisa(change):
    snapshot, journals, ntfs, detail = setup()
    assessments = evaluar_retiradas(snapshot, journals, ntfs)
    if change == "visto":
        detail["visto_perfiles"] = [1]
    elif change == "retirada":
        detail["pendiente_perfiles"] = []
    elif change == "activos":
        detail["perfiles_activos"] = [1]
    elif change == "identidad":
        detail["jellyfin_id"] = "otra"
    elif change == "medio":
        detail["medio_id"] = 99
    elif change == "desconocida":
        detail["estado"] = "pelicula_no_unica"
    elif change == "medios_duplicados":
        snapshot["peliculas"].append(deepcopy(snapshot["peliculas"][0]))
    elif change == "preflight_duplicado":
        assessments.append(deepcopy(assessments[0]))
    with pytest.raises(RevisionNoConfiable):
        resumir_revision(snapshot, assessments, detail)


@pytest.mark.parametrize("tampered", [
    [1, 1], [0, 1], [True, 1], ["1"], None, "1",
])
def test_perfiles_activos_ambiguos_cerrado(tampered):
    snapshot, journals, ntfs, detail = setup()
    assessments = evaluar_retiradas(snapshot, journals, ntfs)
    snapshot["perfiles_activos"] = tampered
    with pytest.raises(RevisionNoConfiable):
        resumir_revision(snapshot, assessments, detail)


@pytest.mark.parametrize("bad", [
    -1, True, "1", None, 999, 3,
])
def test_solicitudes_canceladas_dudosas(bad):
    snapshot, journals, ntfs, detail = setup()
    detail["solicitudes_canceladas"] = bad
    with pytest.raises(RevisionNoConfiable):
        review(snapshot, journals, ntfs, detail)


def test_solicitud_de_perfil_no_activo_se_deniega():
    snapshot, journals, ntfs, detail = setup()
    detail["pendiente_perfiles"] = [3]
    with pytest.raises(RevisionNoConfiable):
        review(snapshot, journals, ntfs, detail)


def test_preflight_no_puede_ser_inventado_sin_motivo_admin():
    snapshot, journals, ntfs, detail = setup()
    preflight = evaluar_retiradas(snapshot, journals, ntfs)
    preflight[0]["motivos"] = []
    with pytest.raises(RevisionNoConfiable):
        resumir_revision(snapshot, preflight, detail)


def test_si_cambia_bloqueo_de_perfil_se_rechaza_la_prueba():
    snapshot, journals, ntfs, detail = setup()
    preflight = evaluar_retiradas(snapshot, journals, ntfs)
    preflight[0]["motivos"].append("hay_perfiles_sin_marcar_vista")
    with pytest.raises(RevisionNoConfiable):
        resumir_revision(snapshot, preflight, detail)


def test_peticion_de_usuario_sin_vista_es_invalida():
    snapshot, journals, ntfs, detail = setup()
    snapshot["peliculas"][0]["visto_perfiles"] = [2]
    detail["visto_perfiles"] = [2]
    result = review(snapshot, journals, ntfs, detail)
    assert result["estado"] == "sin_peticion_valida"
    assert result["solicitud_valida_registrada"] is False
    assert "sin_peticion_valida_de_retirada" in result["bloqueos"]
