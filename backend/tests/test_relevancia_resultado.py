"""Filtro de coincidencias: no confundir películas con episodios."""
import pytest

from app.relevancia_resultado import coincide_con_solicitud


@pytest.mark.parametrize(
    "original,tipo,anio,resultado,esperado",
    [
        ("Nadie 2", "pelicula", None, "Cuando.nadie.nos.ve.S01E01.HDTV.720p.720P.SPANISH", False),
        ("Nadie 2", "pelicula", None, "Nadie.2.2025.1080p.WEB.SPANISH", True),
        ("Nadie 2", "pelicula", 2025, "Nadie2.2025.1080p", True),
        ("Nadie 2", "pelicula", None, "Nadie.20.2025.1080p", False),
        ("Nadie 2", "pelicula", 2025, "Nadie.2.2022.1080p", False),
        ("Nadie 2", "pelicula", 2025, "Nadie.2.1080p.WEB", True),
        ("Nadie 2", "pelicula", None, "Nadie.2.S01E01.720p", False),
        ("Nadie 2", "pelicula", None, "Nadie 2 1x03 HDTV", False),
        ("Nadie 2", "pelicula", None, "Nadie 2 S01 HDTV", False),
        ("Nadie 2", "pelicula", None, "Nadie 2.2025.720p", True),
        ("Ocho apellidos vascos", "pelicula", None, "Ocho.Apellidos.Vascos.2014.BDRip", True),
        ("La vida es bella", "pelicula", 1997, "La.Vida.Es.Bella.1997.1080p", True),
        ("El secreto", "pelicula", None, "El secreto de otros 1080p", True),
        ("Serie de prueba", "serie", None, "Serie.de.prueba.S01E01.720p", True),
        ("Serie de prueba", "serie", None, "Otra.serie.S01E01.720p", False),
        ("", "pelicula", None, "Nadie.2.2025", False),
    ],
)
def test_filtro_conservador(original, tipo, anio, resultado, esperado):
    assert coincide_con_solicitud(original, tipo, anio, resultado) is esperado
