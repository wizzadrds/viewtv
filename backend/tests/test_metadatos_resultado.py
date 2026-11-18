import pytest

from app.metadatos_resultado import extraer_metadatos


@pytest.mark.parametrize(
    ("titulo", "esperado"),
    [
        (
            "Nadie.2.2025.2160p.BluRay.HEVC.SPANISH",
            {
                "resolucion": "2160p",
                "calidad": "4K",
                "fuente": "BluRay",
                "codec": "HEVC",
                "idioma": "Español",
            },
        ),
        (
            "Pelicula.2025.1080p.WEB-DL.x264.LATINO",
            {
                "resolucion": "1080p",
                "calidad": "Full HD",
                "fuente": "WEB-DL",
                "codec": "H.264",
                "idioma": "Latino",
            },
        ),
        (
            "Serie.2025.720p.WEBRip.DUAL",
            {
                "resolucion": "720p",
                "calidad": "HD",
                "fuente": "WEBRip",
                "codec": None,
                "idioma": "Dual/Multi",
            },
        ),
        (
            "Contenido.sin.datos",
            {
                "resolucion": None,
                "calidad": "No especificada",
                "fuente": None,
                "codec": None,
                "idioma": None,
            },
        ),
    ],
)
def test_extraer_metadatos(titulo, esperado):
    assert extraer_metadatos(titulo) == esperado
