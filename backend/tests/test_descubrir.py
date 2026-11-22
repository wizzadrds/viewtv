"""Descubrimiento solo metadatos y solicitud explícita: sin descargas."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import descubrir
from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Descarga, Medio, Perfil, Solicitud
from app.tmdb import TMDBError


@pytest.fixture
def client(monkeypatch):
    db = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(db)
    with Session(db) as s:
        s.add(Perfil(id=1, nombre="Ensayo", pin_hash="no-es-un-pin"))
        s.commit()

    def session():
        with Session(db) as s:
            yield s

    app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_session] = session
    monkeypatch.setattr(
        descubrir, "get_settings",
        lambda: SimpleNamespace(tmdb_api_key="test-not-shared"),
    )
    with TestClient(app) as browser:
        yield browser, db
    app.dependency_overrides.clear()
    db.dispose()


def media(id=15, title="Pelicula Autorizada", year=2020, kind="pelicula", **extra):
    result = {
        "id": id, "title": title, "name": title,
        "release_date": f"{year}-01-20",
        "first_air_date": f"{year}-04-12",
        "overview": "Sinopsis de metadatos", "adult": False,
        "poster_path": "/poster-test.jpg", "backdrop_path": "/fondo-test.jpg",
    }
    result.update(extra)
    return result


class StubTMDB:
    def trending(self, media_type, page):
        return {"results": [
            media(), media(16, title="Oculto", adult=True),
            media(17, title="Con URL maliciosa", poster_path="//example.com/a.jpg"),
            {"id": 0, "title": "ID incorrecta"},
        ], "total_pages": 2}

    def search_page(self, media_type, title, page):
        return {"results": [media(42, title="Serie de prueba", kind="serie")],
                "total_pages": 1}

    def details(self, media_type, tmdb_id):
        result = media(tmdb_id)
        if media_type == "serie":
            result["name"] = "Serie de prueba"
        result["genres"] = [{"name": "Aventura"}]
        result["runtime"] = 119
        return result


def test_estado_configurado_no_revela_clave(client):
    browser, _ = client
    assert browser.get("/descubrir/estado").json() == {"tmdb_configurado": True}
    assert "test-not-shared" not in str(browser.get("/descubrir/estado").json())


def test_trending_filtra_adultos_y_valida_imagenes(client, monkeypatch):
    browser, db = client
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: StubTMDB())
    response = browser.get("/descubrir/tendencias?tipo=pelicula&pagina=1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["paginas"] == 2
    assert len(payload["elementos"]) == 2
    first, second = payload["elementos"]
    assert first["tmdb_id"] == 15
    assert first["imagen_portada"].startswith("https://image.tmdb.org/t/p/w500/")
    assert first["disponible_local"] is False
    assert second["imagen_portada"] is None
    with Session(db) as s:
        assert s.exec(select(Solicitud)).all() == []
        assert s.exec(select(Descarga)).all() == []


def test_buscar_series_sin_descarga(client, monkeypatch):
    browser, _ = client
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: StubTMDB())
    result = browser.get("/descubrir/buscar?tipo=serie&titulo=Prueba")
    assert result.status_code == 200
    row = result.json()["elementos"][0]
    assert row["tipo"] == "serie"
    assert row["titulo"] == "Serie de prueba"


def test_detalle_generos_duracion_y_portada(client, monkeypatch):
    browser, _ = client
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: StubTMDB())
    result = browser.get("/descubrir/pelicula/15")
    assert result.status_code == 200
    assert result.json()["generos"] == ["Aventura"]
    assert result.json()["duracion_minutos"] == 119


def test_marca_instalado_solo_si_unico_y_coincidencia_fuerte(client, monkeypatch):
    browser, db = client
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: StubTMDB())
    with Session(db) as s:
        s.add(Medio(
            jellyfin_id="jf-local", titulo="Pelicula Autorizada",
            tipo="pelicula", anio=2020, disponible_en_jellyfin=True,
        ))
        s.commit()
    item = browser.get("/descubrir/tendencias").json()["elementos"][0]
    assert item["disponible_local"] is True
    assert type(item["medio_id"]) is int
    with Session(db) as s:
        m = s.exec(select(Medio)).first()
        m.anio = 2019
        s.add(m)
        s.commit()
    assert browser.get("/descubrir/tendencias").json()["elementos"][0]["disponible_local"] is False


def test_solicitar_explicito_crea_solicitud_sin_torrent(client, monkeypatch):
    browser, db = client
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: StubTMDB())
    # Abrir tendencias NO crea la solicitud ni descarga.
    assert browser.get("/descubrir/tendencias").status_code == 200
    with Session(db) as s:
        assert not s.exec(select(Solicitud)).all()
        assert not s.exec(select(Descarga)).all()
    created = browser.post("/descubrir/pelicula/15/solicitar")
    assert created.status_code == 201
    assert created.json()["estado"] == "solicitud_creada"
    assert "fuente autorizada" in created.json()["mensaje"]
    with Session(db) as s:
        jobs = s.exec(select(Solicitud)).all()
        assert len(jobs) == 1
        assert jobs[0].tipo_medio == "pelicula"
        assert jobs[0].titulo == "Pelicula Autorizada"
        assert not s.exec(select(Descarga)).all()
    assert browser.post("/descubrir/pelicula/15/solicitar").status_code == 409


def test_no_solicita_si_ya_instalado(client, monkeypatch):
    browser, db = client
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: StubTMDB())
    with Session(db) as s:
        s.add(Medio(
            jellyfin_id="jf-installed", tmdb_id=15,
            titulo="Otro título", tipo="pelicula",
            disponible_en_jellyfin=True,
        ))
        s.commit()
    assert browser.post("/descubrir/pelicula/15/solicitar").status_code == 409


@pytest.mark.parametrize("url", [
    "/descubrir/tendencias?pagina=100",
    "/descubrir/tendencias?tipo=episodio",
    "/descubrir/buscar?titulo=x",
    "/descubrir/pelicula/0",
    "/descubrir/serie/99999999999",
])
def test_validacion_de_parametros(client, url):
    browser, _ = client
    assert browser.get(url).status_code == 422


def test_upstream_error_es_controlado(client, monkeypatch):
    browser, _ = client
    monkeypatch.setattr(
        descubrir, "_tmdb_client",
        lambda: (_ for _ in ()).throw(TMDBError("Detalle privado")),
    )
    response = browser.get("/descubrir/tendencias")
    assert response.status_code == 503
    assert "Detalle privado" not in response.text


def test_solicitud_no_sigue_id_de_otro_detalle(client, monkeypatch):
    browser, db = client

    class Mismatched(StubTMDB):
        def details(self, media_type, tmdb_id):
            return media(999)

    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: Mismatched())
    assert browser.post("/descubrir/pelicula/15/solicitar").status_code == 404
    with Session(db) as s:
        assert not s.exec(select(Solicitud)).all()


def test_solicitud_filtra_adulto_incluso_si_id_es_valido(client, monkeypatch):
    browser, db = client

    class Adult(StubTMDB):
        def details(self, media_type, tmdb_id):
            return media(tmdb_id, adult=True)

    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: Adult())
    assert browser.post("/descubrir/pelicula/15/solicitar").status_code == 404
    with Session(db) as s:
        assert not s.exec(select(Solicitud)).all()


def test_falta_tmdb_no_crea_solicitudes(client, monkeypatch):
    browser, db = client
    monkeypatch.setattr(descubrir, "get_settings", lambda: SimpleNamespace(tmdb_api_key=""))
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: descubrir.TMDBClient())
    assert browser.get("/descubrir/estado").json()["tmdb_configurado"] is False
    assert browser.get("/descubrir/tendencias").status_code == 503
    assert browser.post("/descubrir/pelicula/15/solicitar").status_code == 503
    with Session(db) as s:
        assert not s.exec(select(Solicitud)).all()


def test_descubrimiento_requiere_sesion(client):
    browser, _ = client
    app.dependency_overrides.pop(get_current_profile)
    response = browser.get("/descubrir/estado")
    assert response.status_code == 401


def test_filas_definidas_con_local_primera_y_generos(client):
    browser, _ = client
    response = browser.get("/descubrir/filas")
    assert response.status_code == 200
    payload = response.json()
    assert payload["tmdb_configurado"] is True
    assert [row["id"] for row in payload["filas"]][:5] == [
        "recientes", "peliculas-nuevas", "tendencias", "accion", "terror",
    ]
    assert any(row["id"] == "series-tendencia" for row in payload["filas"])
    assert any("Películas nuevas de" in row["titulo"] for row in payload["filas"])
    assert all("torrent" not in str(row).lower() for row in payload["filas"])


def test_fila_recientes_funciona_sin_tmdb_y_no_crea_descargas(client, monkeypatch):
    browser, db = client
    monkeypatch.setattr(descubrir, "get_settings", lambda: SimpleNamespace(tmdb_api_key=""))
    with Session(db) as s:
        s.add(Medio(
            jellyfin_id="local-1", titulo="Primera", tipo="pelicula",
            anio=2022, imagen_portada="/jellyfin/media/1/images/primary",
            disponible_en_jellyfin=True,
        ))
        s.add(Medio(
            jellyfin_id="local-2", titulo="Segunda", tipo="serie",
            disponible_en_jellyfin=True,
        ))
        s.add(Medio(
            jellyfin_id="retirada", titulo="Retirada", tipo="pelicula",
            disponible_en_jellyfin=False,
        ))
        s.commit()
    payload = browser.get("/descubrir/filas/recientes").json()
    assert [row["titulo"] for row in payload["elementos"]] == ["Segunda", "Primera"]
    assert payload["elementos"][0]["tmdb_id"] is None
    assert payload["elementos"][0]["disponible_local"] is True
    assert payload["elementos"][1]["imagen_portada"].startswith("/jellyfin/media/")
    assert browser.get("/descubrir/filas").json()["tmdb_configurado"] is False
    assert browser.get("/descubrir/filas/accion").status_code == 503
    with Session(db) as s:
        assert not s.exec(select(Solicitud)).all()
        assert not s.exec(select(Descarga)).all()


@pytest.mark.parametrize(("shelf", "kind", "genre"), [
    ("accion", "pelicula", 28),
    ("terror", "pelicula", 27),
    ("comedia", "pelicula", 35),
    ("ciencia-ficcion", "pelicula", 878),
    ("series-misterio", "serie", 9648),
])
def test_generos_api_usan_solo_filtro_fijo_y_sin_torrent(
    client, monkeypatch, shelf, kind, genre,
):
    browser, db = client
    calls = []

    class CatalogStub(StubTMDB):
        def discover(self, media_type, *, genre_id=None, release_year=None, page=1):
            calls.append((media_type, genre_id, release_year, page))
            return {"results": [media(111, kind=media_type)], "total_pages": 1}

    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: CatalogStub())
    response = browser.get("/descubrir/filas/" + shelf)
    assert response.status_code == 200
    assert response.json()["elementos"][0]["disponible_local"] is False
    assert calls == [(kind, genre, None, 1)]
    with Session(db) as s:
        assert not s.exec(select(Solicitud)).all()
        assert not s.exec(select(Descarga)).all()


def test_fila_de_estrenos_limita_ano_de_lanzamiento(client, monkeypatch):
    browser, _ = client
    captured = []

    class CatalogStub(StubTMDB):
        def discover(self, media_type, *, genre_id=None, release_year=None, page=1):
            captured.append((media_type, genre_id, release_year))
            return {"results": [media()], "total_pages": 1}

    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: CatalogStub())
    response = browser.get("/descubrir/filas/peliculas-nuevas")
    assert response.status_code == 200
    from datetime import UTC, datetime
    assert captured == [("pelicula", None, datetime.now(UTC).year)]


def test_fila_tendencias_series(client, monkeypatch):
    browser, _ = client
    calls = []

    class CatalogStub(StubTMDB):
        def trending(self, media_type, page):
            calls.append((media_type, page))
            return {"results": [media(81, kind="serie")], "total_pages": 1}

    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: CatalogStub())
    response = browser.get("/descubrir/filas/series-tendencia")
    assert response.status_code == 200
    assert response.json()["elementos"][0]["tipo"] == "serie"
    assert calls == [("serie", 1)]


@pytest.mark.parametrize("shelf", ["sin-categoria", "../media", "hack", "adultos"])
def test_fila_no_autorizada_no_consulta_proveedor(client, monkeypatch, shelf):
    browser, _ = client
    monkeypatch.setattr(
        descubrir, "_tmdb_client",
        lambda: (_ for _ in ()).throw(AssertionError("no consultar TMDB")),
    )
    assert browser.get("/descubrir/filas/" + shelf).status_code in (404, 422)


def test_filtrar_ano_y_genero_en_cliente_tmdb_sin_exponer_clave(monkeypatch):
    from datetime import UTC, datetime

    from app.tmdb import TMDBClient, TMDBError

    tmdb = object.__new__(TMDBClient)
    called = []
    def fake_get(path, params=None):
        called.append((path, params))
        return {"results": []}
    monkeypatch.setattr(tmdb, "_get", fake_get)

    year = datetime.now(UTC).year
    assert tmdb.discover("pelicula", genre_id=27, release_year=year) == {"results": []}
    path, options = called[0]
    assert path == "discover/movie"
    assert options["with_genres"] == 27
    assert options["primary_release_year"] == year
    assert options["primary_release_date.lte"] <= datetime.now(UTC).date().isoformat()
    assert options["include_adult"] == "false"
    assert options["sort_by"] == "popularity.desc"
    with pytest.raises(TMDBError):
        tmdb.discover("serie", genre_id=27)
    with pytest.raises(TMDBError):
        tmdb.discover("pelicula", release_year=year + 1)
    assert len(called) == 1


def test_filas_requieren_autenticacion(client):
    browser, _ = client
    app.dependency_overrides.pop(get_current_profile)
    assert browser.get("/descubrir/filas").status_code == 401
    assert browser.get("/descubrir/filas/recientes").status_code == 401
