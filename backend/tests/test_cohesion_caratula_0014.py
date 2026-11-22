"""Regresión carátula TMDB -> solicitud -> worker -> resultados sin torrents reales."""
import base64
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from worker.processor import _result_key

import app.titulo_cohesion as cohesion
from app import descubrir
from app.models import Perfil, Solicitud
from app.solicitudes import CrearSolicitudInput
from app.titulo_cohesion import aliases_para_solicitud, consultas_jackett


@pytest.fixture
def local_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_carátula_persiste_id_sin_confiar_en_json(monkeypatch, local_db):
    with Session(local_db) as session:
        profile = Perfil(nombre="Prueba", pin_hash="hash-inocuo")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        monkeypatch.setattr(descubrir, "_detail_data", lambda *args: {
            "titulo": "Vengadores: Doomsday",
            "anio": 2026,
            "disponible_local": False,
        })
        response = descubrir.solicitar_descarga("pelicula", 1003596, profile, session)
        assert response["estado"] == "solicitud_creada"
        row = session.get(Solicitud, response["solicitud_id"])
        assert row is not None
        assert row.tmdb_id == 1003596
        assert row.titulo == "Vengadores: Doomsday"
        assert row.anio == 2026

    injected = CrearSolicitudInput.model_validate({
        "titulo": "Otra película", "tipo_medio": "pelicula", "anio": 2020,
        "_tmdb_id": 1003596,
    })
    assert injected._tmdb_id is None
    assert "_tmdb_id" not in injected.model_dump()


def test_id_caratula_no_resuelve_otra_pelicula_aun_con_mismo_nombre(monkeypatch):
    class FakeTMDB:
        def search(self, kind, title):
            raise AssertionError("No debe buscar por nombre una carátula con ID")

        def details_with_aliases(self, kind, tmdb_id):
            assert kind == "pelicula"
            assert tmdb_id == 1003596
            return {
                "id": tmdb_id,
                "title": "Vengadores: Doomsday",
                "original_title": "Avengers: Doomsday",
                "release_date": "2026-12-18",
                "translations": {"translations": []},
                "alternative_titles": {"titles": []},
            }

    monkeypatch.setattr(cohesion, "TMDBClient", FakeTMDB)
    cohesion.aliases_para_solicitud.cache_clear()
    try:
        aliases = aliases_para_solicitud(
            "Vengadores: Doomsday", "pelicula", 2026, 1003596,
        )
        assert "Avengers: Doomsday" in aliases
        queries = consultas_jackett(
            "Vengadores: Doomsday", "pelicula", 2026, aliases,
        )
        assert "Vengadores: Doomsday 2026" in queries
        assert "Vengadores: Doomsday" in queries
        assert "Avengers: Doomsday 2026" in queries
        assert "Avengers: Doomsday" in queries
        assert "Doomsday" in queries
        assert len(queries) <= 6
    finally:
        cohesion.aliases_para_solicitud.cache_clear()


def test_dos_remakes_sin_anio_no_proporcionan_alias(monkeypatch):
    class FakeTMDB:
        def search(self, kind, title):
            return [
                {"id": 1, "title": "The Thing",
                 "original_title": "The Thing", "release_date": "1982-06-25"},
                {"id": 2, "title": "The Thing",
                 "original_title": "The Thing", "release_date": "2011-10-14"},
            ]

        def details_with_aliases(self, kind, identity):
            return {
                "id": identity, "title": "The Thing",
                "original_title": "The Thing",
                "release_date": "1982-06-25" if identity == 1 else "2011-10-14",
            }

    monkeypatch.setattr(cohesion, "TMDBClient", FakeTMDB)
    cohesion.aliases_para_solicitud.cache_clear()
    try:
        assert aliases_para_solicitud("The Thing", "pelicula", None) == ()
        assert aliases_para_solicitud("The Thing", "pelicula", 1982)
        assert aliases_para_solicitud("The Thing", "pelicula", 2011)
        assert aliases_para_solicitud("The Thing", "pelicula", 2000) == ()
    finally:
        cohesion.aliases_para_solicitud.cache_clear()


def test_deduplicacion_infohash_hex_base32_y_magnet():
    digest = "a1" * 20
    encoded = base64.b32encode(bytes.fromhex(digest)).decode("ascii")
    key1 = _result_key(digest, None, "https://ejemplo.test/a")
    key2 = _result_key(None, f"magnet:?xt=urn:btih:{encoded}&dn=una", None)
    key3 = _result_key(None, f"magnet:?xt=urn:btih:{digest.upper()}&dn=otra", None)
    assert key1 == key2 == key3
    assert key1 != _result_key("b2" * 20, None, "https://ejemplo.test/b")


def test_migracion_0014_aditiva_y_reversion_segura():
    root = Path(__file__).resolve().parents[1]
    path = root / "migrations" / "versions" / "0014_identidad_tmdb_solicitud.py"
    spec = importlib.util.spec_from_file_location("cohesion_0014", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE solicitud (id INTEGER PRIMARY KEY, titulo TEXT NOT NULL)"))
        conn.execute(text("INSERT INTO solicitud(id, titulo) VALUES (1, 'Registro anterior')"))
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            module.upgrade()
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(solicitud)")]
        assert "tmdb_id" in cols
        assert conn.execute(text("SELECT titulo, tmdb_id FROM solicitud WHERE id=1")).one() == (
            "Registro anterior", None,
        )
        with Operations.context(context):
            module.downgrade()
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(solicitud)")]
        assert "tmdb_id" not in cols
        with Operations.context(context):
            module.upgrade()
        conn.execute(text("UPDATE solicitud SET tmdb_id=1003596 WHERE id=1"))
        with Operations.context(context):
            with pytest.raises(RuntimeError, match="solicitudes vinculadas"):
                module.downgrade()
    engine.dispose()


def test_ambiguedad_manual_sin_anio_bloquea_resultados(monkeypatch):
    from fastapi import HTTPException

    from app.solicitudes import _rechazar_ambiguedad

    class FakeTMDB:
        def search(self, kind, title):
            return [
                {"id": 11, "title": "The Thing", "original_title": "The Thing"},
                {"id": 12, "title": "The Thing", "original_title": "The Thing"},
            ]

    monkeypatch.setattr(cohesion, "TMDBClient", FakeTMDB)
    cohesion.solicitud_sin_anio_ambigua.cache_clear()
    try:
        assert cohesion.solicitud_sin_anio_ambigua("The Thing", "pelicula")
        with pytest.raises(HTTPException) as exc:
            _rechazar_ambiguedad(
                Solicitud(perfil_id=1, titulo="The Thing", tipo_medio="pelicula"),
            )
        assert exc.value.status_code == 409
        # El ID elegido en una carátula evita esta ambigüedad.
        _rechazar_ambiguedad(
            Solicitud(
                perfil_id=1, titulo="The Thing",
                tipo_medio="pelicula", tmdb_id=11,
            ),
        )
    finally:
        cohesion.solicitud_sin_anio_ambigua.cache_clear()
