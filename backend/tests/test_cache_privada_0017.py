"""Cuota y evicción de la caché EXCLUSIVA en directorios ficticios.

Nunca monta discos, torrents, Jellyfin ni películas reales.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.cache_privada import (
    CADUCIDAD_SEGUNDOS,
    DIR_CACHE,
    FICHERO_MARCA,
    MARCADOR_BLOQUEO,
    CacheNoConfiable,
    estado_cache,
    guardar_temporal,
    limpiar_cache,
)


def test_estado_no_crea_archivos(tmp_path):
    assert estado_cache(tmp_path, 80 * 1024**3) == {
        "estado": "vacia_sin_inicializar",
        "archivos": 0,
        "bytes": 0,
        "cuota_bytes": 80 * 1024**3,
        "cuota_efectiva_para_escritores_propios": True,
    }
    assert not (tmp_path / DIR_CACHE).exists()
    assert limpiar_cache(tmp_path, 1024) == {
        "estado": "sin_cache_gestionada", "archivos": 0, "bytes": 0,
    }


def test_escritura_y_limite_real(tmp_path):
    first = guardar_temporal(tmp_path, b"123456", 10)
    folder = tmp_path / DIR_CACHE
    assert (folder / first).read_bytes() == b"123456"
    assert (folder / first).stat().st_mode & 0o077 == 0
    second = guardar_temporal(tmp_path, b"abcdef", 10)
    assert not (folder / first).exists()
    assert (folder / second).read_bytes() == b"abcdef"
    assert estado_cache(tmp_path, 10)["bytes"] == 6
    assert estado_cache(tmp_path, 10)["archivos"] == 1
    assert (folder / FICHERO_MARCA).is_file()
    assert (folder / MARCADOR_BLOQUEO).is_file()


def test_expiracion_caducada_y_orden_lru(tmp_path):
    first = guardar_temporal(tmp_path, b"aaa", 15)
    folder = tmp_path / DIR_CACHE
    old = time.time() - CADUCIDAD_SEGUNDOS - 360
    os.utime(folder / first, (old, old))
    second = guardar_temporal(tmp_path, b"bbb", 15)
    assert not (folder / first).exists()
    assert (folder / second).exists()


def test_en_archivo_demasiado_grande_no_hay_borrado(tmp_path):
    saved = guardar_temporal(tmp_path, b"OK", 20)
    for data, quota in ((b"more" * 10, 20), (b"ok", 0), (b"x" * 4, -1)):
        with pytest.raises(ValueError):
            guardar_temporal(tmp_path, data, quota)
    assert (tmp_path / DIR_CACHE / saved).read_bytes() == b"OK"


def test_limpieza_conserva_marcador_y_raiz(tmp_path):
    folder = tmp_path / DIR_CACHE
    first = guardar_temporal(tmp_path, b"abc", 50)
    second = guardar_temporal(tmp_path, b"defg", 50)
    other = tmp_path / "pelicula.mkv"
    other.write_bytes(b"NO BORRAR")
    result = limpiar_cache(tmp_path, 50)
    assert result == {"estado": "limpiada", "archivos": 2, "bytes": 7}
    assert not (folder / first).exists() and not (folder / second).exists()
    assert (folder / FICHERO_MARCA).exists()
    assert (folder / MARCADOR_BLOQUEO).exists()
    assert other.read_bytes() == b"NO BORRAR"


def test_archivo_no_reconocido_bloquea_toda_operacion(tmp_path):
    first = guardar_temporal(tmp_path, b"original", 100)
    folder = tmp_path / DIR_CACHE
    unknown = folder / "pelicula.mkv"
    unknown.write_bytes(b"NO BORRAR")
    assert estado_cache(tmp_path, 100)["estado"] == "no_confiable"
    with pytest.raises(CacheNoConfiable):
        limpiar_cache(tmp_path, 100)
    with pytest.raises(CacheNoConfiable):
        guardar_temporal(tmp_path, b"nuevo", 100)
    assert (folder / first).read_bytes() == b"original"
    assert unknown.read_bytes() == b"NO BORRAR"


def test_enlaces_duros_y_simbolicos_son_bloqueo(tmp_path):
    normal = guardar_temporal(tmp_path, b"ok", 100)
    folder = tmp_path / DIR_CACHE
    outside = tmp_path / "unrelated.mp4"
    outside.write_bytes(b"exterior")
    link = folder / ("viewtv-" + "a" * 32 + ".tmp")
    link.symlink_to(outside)
    assert estado_cache(tmp_path, 100)["estado"] == "no_confiable"
    with pytest.raises(CacheNoConfiable):
        limpiar_cache(tmp_path, 100)
    link.unlink()
    hardlink = folder / ("viewtv-" + "b" * 32 + ".tmp")
    os.link(outside, hardlink)
    assert estado_cache(tmp_path, 100)["estado"] == "no_confiable"
    with pytest.raises(CacheNoConfiable):
        guardar_temporal(tmp_path, b"x", 100)
    assert (folder / normal).read_bytes() == b"ok"
    assert outside.read_bytes() == b"exterior"


def test_marcador_incorrecto_o_077_rechaza(tmp_path):
    original = guardar_temporal(tmp_path, b"good", 100)
    folder = tmp_path / DIR_CACHE
    (folder / FICHERO_MARCA).write_bytes(b"fake")
    assert estado_cache(tmp_path, 100)["estado"] == "no_confiable"
    with pytest.raises(CacheNoConfiable):
        limpiar_cache(tmp_path, 100)
    assert (folder / original).exists()
    (folder / FICHERO_MARCA).write_bytes(b"viewtv-temporales-v1\n")
    folder.chmod(0o777)
    assert estado_cache(tmp_path, 100)["estado"] == "no_confiable"


def test_raiz_ajena_o_symlink_rechaza(tmp_path):
    other = tmp_path / "exterior"
    other.mkdir()
    link = tmp_path / "redirigida"
    link.symlink_to(other, target_is_directory=True)
    assert estado_cache(link, 100)["estado"] == "no_confiable"
    with pytest.raises(CacheNoConfiable):
        guardar_temporal(link, b"x", 100)
    assert not list(other.iterdir())
    other.chmod(0o777)
    assert estado_cache(other, 100)["estado"] == "no_confiable"


def test_varios_escritores_comparten_bloqueo_y_cuota(tmp_path):
    def add(i: int) -> str:
        return guardar_temporal(tmp_path, bytes([i]) * 128, 512)

    with ThreadPoolExecutor(max_workers=6) as pool:
        names = list(pool.map(add, range(12)))
    assert len(set(names)) == 12
    status = estado_cache(tmp_path, 512)
    assert status["estado"] == "disponible"
    assert status["bytes"] <= 512
    assert status["archivos"] <= 4
