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
