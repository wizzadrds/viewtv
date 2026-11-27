"""Jellyfin guard: dicts de sandbox, nunca sesiones reales.

Una lectura que no informa reproducción NO constituye permiso de borrar.
"""
from copy import deepcopy

import pytest
from worker.retirement_playback_guard_0021 import (
    SesionesNoConfiables,
    evaluar_sesiones,
    instantanea_sesiones,
)

FILMS = ["jf000000000000000000000000000001", "jf000000000000000000000000000002"]


def session(n: str, playing: str | None = None, *, paused=False, transcoding=None):
    return {
        "Id": n,
        "NowPlayingItem": {"Id": playing, "Name": "PRIVADO"} if playing else None,
        "PlayState": {"IsPaused": paused},
        "TranscodingInfo": transcoding,
        "UserName": "PRIVADO",
        "DeviceName": "PRIVADO",
    }


def test_vacia_no_autoriza_eliminacion():
    result = evaluar_sesiones([], FILMS)
    assert result["estado"] == "sin_reproduccion_reportada"
    assert result["peliculas_comprobadas"] == 2
    assert result["peliculas_bloqueadas"] == 0
    assert result["habilita_borrado_fisico"] is False


@pytest.mark.parametrize("paused", [False, True])
def test_pelicula_en_reproduccion_o_pausada_bloquea(paused):
    result = evaluar_sesiones([session("uno", FILMS[0], paused=paused)], FILMS)
    assert result["estado"] == "bloqueada"
    assert result["peliculas_bloqueadas"] == 1
    assert result["sesiones_pelicula_objetivo"] == 1
    assert not result["habilita_borrado_fisico"]


def test_otro_usuario_reproduciendo_mismo_id_bloquea_igualmente():
    result = evaluar_sesiones([
        session("uno", FILMS[0]),
        session("dos", FILMS[0], paused=True),
    ], FILMS)
    assert result["peliculas_bloqueadas"] == 1
    assert result["sesiones_pelicula_objetivo"] == 2


def test_sesion_otra_pelicula_no_bloquea_la_consultada():
    result = evaluar_sesiones([session("uno", "jf-otro")], FILMS)
    assert result["estado"] == "sin_reproduccion_reportada"
    assert result["sesiones_otras_peliculas"] == 1
    assert not result["habilita_borrado_fisico"]


def test_sesion_sin_reproduccion_permitida_solo_auditando():
    result = evaluar_sesiones([session("uno")], FILMS)
    assert result["sesiones_jellyfin"] == 1
    assert result["estado"] == "sin_reproduccion_reportada"
    assert result["habilita_borrado_fisico"] is False


def test_transcodificacion_sin_item_bloquea_por_ambiguedad():
    result = evaluar_sesiones([session("uno", transcoding={"VideoCodec": "h264"})], FILMS)
    assert result["estado"] == "bloqueada"
    assert result["sesiones_ambiguas"] == 1
    assert result["peliculas_bloqueadas"] == 2


@pytest.mark.parametrize("value", [
    {"Id": ""}, {}, {"Id": None}, {"Id": 123}, "incorrecto", [], False, {"Id": "a" * 200},
])
def test_item_actual_invalido_bloquea_toda_biblioteca(value):
    bad = session("uno")
    bad["NowPlayingItem"] = value
    result = evaluar_sesiones([bad], FILMS)
    assert result["estado"] == "bloqueada"
    assert result["peliculas_bloqueadas"] == 2


@pytest.mark.parametrize("value", [
    None, {}, "sesiones", [None], [False], [{}],
    [{"Id": ""}], [{"Id": 10}], [{"Id": "../movie"}],
    [{"Id": "uno"}, {"Id": "uno"}],
])
def test_estructura_sesiones_invalida_es_error(value):
    with pytest.raises(SesionesNoConfiables):
        evaluar_sesiones(value, FILMS)


@pytest.mark.parametrize("films", [
    [], None, {}, ["x", "x"], ["../bad"], [42], [""], ["a" * 200],
])
def test_identidad_catalogo_ambigua_denegada(films):
    with pytest.raises(SesionesNoConfiables):
        evaluar_sesiones([], films)


def test_limites_exhaustivos_bloquean_fuentes_demasiado_grandes():
    with pytest.raises(SesionesNoConfiables):
        evaluar_sesiones([session("id" + str(i)) for i in range(201)], FILMS)
    with pytest.raises(SesionesNoConfiables):
        evaluar_sesiones([], ["m" + str(i) for i in range(1001)])


def test_instantanea_acepta_cambio_de_orden_y_no_incluye_datos_privados():
    first = [session("uno", FILMS[0]), session("dos", FILMS[1])]
    second = list(reversed(deepcopy(first)))
    assert instantanea_sesiones(first) == instantanea_sesiones(second)
    assert "PRIVADO" not in str(instantanea_sesiones(first))
    assert "Name" not in str(instantanea_sesiones(first))


def test_instantanea_detecta_nueva_reproduccion_stream_y_sesion():
    before = [session("uno")]
    after = [session("uno", FILMS[0])]
    assert instantanea_sesiones(before) != instantanea_sesiones(after)
    before = [session("uno", FILMS[0])]
    after = [session("uno", FILMS[0], transcoding={"Path": "PRIVADO"})]
    assert instantanea_sesiones(before) != instantanea_sesiones(after)
    after = [session("uno", FILMS[0]), session("dos")]
    assert instantanea_sesiones(before) != instantanea_sesiones(after)


def test_instantanea_rechaza_duplicados():
    with pytest.raises(SesionesNoConfiables):
        instantanea_sesiones([session("uno"), session("uno")])


def test_ningun_estado_devuelve_permiso_positivo():
    cases = [
        [],
        [session("uno")],
        [session("uno", FILMS[0])],
        [session("uno", transcoding={"Url": "privado"})],
    ]
    for sessions in cases:
        result = evaluar_sesiones(sessions, FILMS)
        assert result["habilita_borrado_fisico"] is False
        assert "PRIVADO" not in str(result)
