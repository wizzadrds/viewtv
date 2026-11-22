"""Búsqueda coherente por identidad TMDB; no torrent ni red real."""
import pytest

import app.titulo_cohesion as cohesion
from app.relevancia_resultado import coincide_con_solicitud


class FakeTMDB:
    def __init__(self):
        self.calls = []

    def search(self, kind, title):
        self.calls.append(("search", kind, title))
        if title == "Vengadores: Doomsday":
            return [{
                "id": 12345,
                "title": "Vengadores: Doomsday",
                "original_title": "Avengers: Doomsday",
                "release_date": "2026-12-18",
            }]
        if title == "Serie de prueba":
            return [{
                "id": 900,
                "name": "Serie de prueba",
                "original_name": "Sample Show",
                "first_air_date": "2023-05-10",
            }]
        return []

    def details_with_aliases(self, kind, mid):
        self.calls.append(("details", kind, mid))
        if mid == 12345:
            return {
                "id": mid, "title": "Vengadores: Doomsday",
                "original_title": "Avengers: Doomsday",
                "adult": False,
                "translations": {"translations": [
                    {"iso_639_1": "es", "data": {"title": "Vengadores: Doomsday"}},
                    {"iso_639_1": "en", "data": {"title": "Avengers: Doomsday"}},
                    {"iso_639_1": "fr", "data": {"title": "Autre film"}},
                ]},
                "alternative_titles": {"titles": [
                    {"iso_3166_1": "US", "title": "Marvel Avengers: Doomsday"},
                ]},
            }
        return {
            "id": mid, "name": "Serie de prueba", "original_name": "Sample Show",
            "adult": False,
        }


@pytest.fixture(autouse=True)
def reset_cache():
    cohesion.aliases_para_solicitud.cache_clear()
    yield
    cohesion.aliases_para_solicitud.cache_clear()


def test_tmdb_oficial_identifica_caratula_en_es_y_publicacion_en_ingles(monkeypatch):
    fake = FakeTMDB()
    monkeypatch.setattr(cohesion, "TMDBClient", lambda: fake)
    aliases = cohesion.aliases_para_solicitud("Vengadores: Doomsday", "pelicula", 2026)
    assert "Avengers: Doomsday" in aliases
    assert "Vengadores: Doomsday" in aliases
    assert "Autre film" not in aliases
    queries = cohesion.consultas_jackett(
        "Vengadores: Doomsday", "pelicula", 2026, aliases,
    )
    assert queries[0] == "Vengadores: Doomsday 2026"
    assert "Avengers: Doomsday 2026" in queries
    assert any(q == "Doomsday" for q in queries)
    assert len(queries) <= 6
    assert coincide_con_solicitud(
        "Vengadores: Doomsday", "pelicula", 2026,
        "Avengers.Doomsday.2026.1080p.WEB-DL", aliases,
    )
    assert not coincide_con_solicitud(
        "Vengadores: Doomsday", "pelicula", 2026,
        "Doomsday.2026.1080p", aliases,
    )
    assert coincide_con_solicitud(
        "Vengadores: Doomsday", "pelicula", 2026,
        "Avengers.Doomsday.2025.1080p", aliases,
    )
    assert not coincide_con_solicitud(
        "Vengadores: Doomsday", "pelicula", 2026,
        "Avengers.Doomsday.Part.Two.2026", aliases,
    )
    assert len(fake.calls) == 2


def test_sin_identidad_tmdb_no_inventa_traducciones(monkeypatch):
    fake = FakeTMDB()
    monkeypatch.setattr(cohesion, "TMDBClient", lambda: fake)
    assert cohesion.aliases_para_solicitud("La película inexistente", "pelicula", 2026) == ()
    assert cohesion.consultas_jackett("La película inexistente", "pelicula", 2026, ()) == (
        "La película inexistente 2026", "La película inexistente",
    )
    assert not coincide_con_solicitud(
        "La película inexistente", "pelicula", 2026,
        "Unrelated Movie 2026", (),
    )


def test_anio_distinto_no_enlaza_fichas(monkeypatch):
    monkeypatch.setattr(cohesion, "TMDBClient", FakeTMDB)
    assert cohesion.aliases_para_solicitud("Vengadores: Doomsday", "pelicula", 2022) == ()


def test_series_mantienen_episodio_en_idioma_original(monkeypatch):
    monkeypatch.setattr(cohesion, "TMDBClient", FakeTMDB)
    aliases = cohesion.aliases_para_solicitud("Serie de prueba S01E02", "serie", None)
    assert "Sample Show" in aliases
    queries = cohesion.consultas_jackett("Serie de prueba S01E02", "serie", None, aliases)
    assert "Sample Show S01E02" in queries
    assert coincide_con_solicitud(
        "Serie de prueba S01E02", "serie", None,
        "Sample.Show.S01E02.1080p", aliases,
    )
    assert not coincide_con_solicitud(
        "Serie de prueba S01E02", "serie", None,
        "Sample.Show.S01E03.1080p", aliases,
    )
    assert not coincide_con_solicitud(
        "Serie de prueba S01E02", "serie", None,
        "Sample.Show.S01E02E03.PACK", aliases,
    )


def test_pruebas_rechazo_datos_no_confiables(monkeypatch):
    fake = FakeTMDB()
    monkeypatch.setattr(cohesion, "TMDBClient", lambda: fake)
    assert cohesion._valid_title("x") is None
    assert cohesion._valid_title("Avengers\nDoomsday") is None
    assert cohesion._valid_title("<iframe>") is not None
    assert cohesion.consultas_jackett("Serie de prueba S01E01", "serie", None, ()) == (
        "Serie de prueba S01E01",
    )


def test_reserva_busqueda_corta_con_muchas_traducciones():
    aliases = (
        "Vengadores: Doomsday", "Avengers: Doomsday",
        "Marvel Avengers: Doomsday", "Avengers: Final Judgment",
        "Avengers: Doom", "The Avengers: Doomsday",
    )
    queries = cohesion.consultas_jackett(
        "Vengadores: Doomsday", "pelicula", 2026, aliases,
    )
    assert queries[0] == "Vengadores: Doomsday 2026"
    assert "Avengers: Doomsday 2026" in queries
    assert queries[-1] == "Doomsday"
    assert len(queries) <= 6
