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


def test_catalogo_persistente_http_con_contador_y_paginacion(
    client, monkeypatch, tmp_path,
):
    from app import catalogo_cache

    browser, engine = client
    monkeypatch.setenv("VIEWTV_CATALOG_PATH", str(tmp_path / "metadatos.db"))
    db = catalogo_cache.create_writer()
    try:
        for part in range(2):
            raw = {"results": [
                media(1000 + part * 20 + i,
                      title="Terror nuevo " + str(part * 20 + i),
                      genre_ids=[27], popularity=60 - i)
                for i in range(20)
            ]}
            catalogo_cache.upsert_page(db, "pelicula", raw)
        db.commit()
    finally:
        db.close()
    stats = browser.get("/descubrir/catalogo/estado")
    assert stats.status_code == 200
    assert stats.json()["total"] == 40
    assert stats.json()["solo_metadatos"] is True
    assert stats.json()["limite_fichas"] == 250_000

    full = browser.get("/descubrir/filas/catalogo")
    assert full.status_code == 200
    assert full.json()["total"] == 40
    assert full.json()["paginas"] == 2
    assert len(full.json()["elementos"]) == 20
    second = browser.get("/descubrir/filas/catalogo?pagina=2")
    assert second.status_code == 200
    assert len(second.json()["elementos"]) == 20
    assert {
        element["tmdb_id"] for element in full.json()["elementos"]
    }.isdisjoint({
        element["tmdb_id"] for element in second.json()["elementos"]
    })
    horror = browser.get("/descubrir/filas/terror")
    assert horror.status_code == 200
    assert horror.json()["total"] == 40
    with Session(engine) as s:
        assert not s.exec(select(Solicitud)).all()
        assert not s.exec(select(Descarga)).all()


def test_catalogo_estadisticas_requieren_sesion(client):
    browser, _ = client
    app.dependency_overrides.pop(get_current_profile)
    assert browser.get("/descubrir/catalogo/estado").status_code == 401
    assert browser.get("/descubrir/filas/catalogo").status_code == 401


def test_catalogo_reciente_sin_volumen_de_metadatos(client, monkeypatch, tmp_path):
    browser, _ = client
    monkeypatch.setenv("VIEWTV_CATALOG_PATH", str(tmp_path / "metadatos.db"))
    assert browser.get("/descubrir/catalogo/estado").json()["total"] == 0
    assert browser.get("/descubrir/filas/catalogo").json()["elementos"] == []
    assert browser.get("/descubrir/filas/recientes").status_code == 200


class SeasonTMDB(StubTMDB):
    """TMDB falso: ni web, ni qBittorrent, ni contenido privado."""
    def details(self, media_type, tmdb_id):
        result = super().details(media_type, tmdb_id)
        if media_type == "serie":
            result["name"] = "Serie de prueba"
            result["seasons"] = [
                {"season_number": 0, "name": "Especiales", "episode_count": 1},
                {"season_number": 1, "name": "Temporada 1", "episode_count": 42,
                 "poster_path": "/temporada.jpg", "air_date": "2020-04-12"},
                {"season_number": 2, "name": "Temporada 2", "episode_count": 1},
            ]
        return result

    def season_details(self, tmdb_id, season_number):
        count = 42 if season_number == 1 else 1
        return {
            "season_number": season_number, "name": "Temporada de prueba",
            "overview": "Sinopsis de la temporada",
            "episodes": [
                {
                    "id": 8000 + n, "season_number": season_number,
                    "episode_number": n, "name": f"Capítulo {n}",
                    "overview": f"Trama del capítulo {n}",
                    "runtime": 44, "still_path": "/fotograma.jpg",
                    "air_date": "2999-01-01" if n == 42 else "2020-04-12",
                }
                for n in range(1, count + 1)
            ],
        }


def test_serie_tiene_una_ficha_con_temporadas_y_especiales(client, monkeypatch):
    browser, db = client
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: SeasonTMDB())
    detail = browser.get("/descubrir/serie/15")
    assert detail.status_code == 200
    assert detail.json()["titulo"] == "Serie de prueba"
    assert [s["temporada"] for s in detail.json()["temporadas"]] == [0, 1, 2]
    assert detail.json()["temporadas"][1]["imagen_portada"].startswith(
        "https://image.tmdb.org/t/p/w500/"
    )
    with Session(db) as s:
        assert not s.exec(select(Solicitud)).all()
        assert not s.exec(select(Descarga)).all()


def test_temporada_episodios_paginados_sin_iniciar_descargas(client, monkeypatch):
    browser, db = client
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: SeasonTMDB())
    first = browser.get("/descubrir/serie/15/temporadas/1?pagina=1")
    second = browser.get("/descubrir/serie/15/temporadas/1?pagina=2")
    assert first.status_code == second.status_code == 200
    a, b = first.json(), second.json()
    assert a["total"] == 42 and a["paginas"] == 2
    assert len(a["episodios"]) == 40 and len(b["episodios"]) == 2
    assert a["episodios"][0]["episodio"] == 1
    assert a["episodios"][0]["imagen"].startswith("https://image.tmdb.org/t/p/w500/")
    assert a["episodios"][0]["duracion_minutos"] == 44
    assert b["episodios"][-1]["episodio"] == 42
    assert b["episodios"][-1]["solicitable"] is False
    assert browser.get("/descubrir/serie/15/temporadas/0").status_code == 200
    with Session(db) as s:
        assert not s.exec(select(Solicitud)).all()
        assert not s.exec(select(Descarga)).all()


def test_pedir_episodio_crea_solo_solicitud_individual(client, monkeypatch):
    browser, db = client
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: SeasonTMDB())
    endpoint = "/descubrir/serie/15/temporadas/1/episodios/2/solicitar"
    created = browser.post(endpoint)
    assert created.status_code == 201
    assert created.json()["temporada"] == 1
    assert created.json()["episodio"] == 2
    assert "fuente autorizada" in created.json()["mensaje"]
    with Session(db) as s:
        pending = s.exec(select(Solicitud)).all()
        assert len(pending) == 1
        assert pending[0].tipo_medio == "serie"
        assert pending[0].titulo == "Serie de prueba S01E02"
        assert pending[0].anio is None
        assert not s.exec(select(Descarga)).all()
    assert browser.post(endpoint).status_code == 409
    other = browser.post("/descubrir/serie/15/temporadas/1/episodios/3/solicitar")
    assert other.status_code == 201
    with Session(db) as s:
        titles = [item.titulo for item in s.exec(select(Solicitud)).all()]
        assert titles == ["Serie de prueba S01E02", "Serie de prueba S01E03"]
        assert not s.exec(select(Descarga)).all()


def test_serie_instalada_no_impide_elegir_otro_episodio(client, monkeypatch):
    browser, db = client
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: SeasonTMDB())
    with Session(db) as s:
        s.add(Medio(
            jellyfin_id="jf-serie", tipo="serie", titulo="Serie de prueba",
            tmdb_id=15, disponible_en_jellyfin=True,
        ))
        s.commit()
    loaded = browser.get("/descubrir/serie/15/temporadas/1")
    assert loaded.status_code == 200
    assert loaded.json()["disponible_local"] is True
    assert "No se ha verificado" in loaded.json()["aviso_disponibilidad"]
    assert browser.post("/descubrir/serie/15/temporadas/1/episodios/2/solicitar").status_code == 201


@pytest.mark.parametrize(("path", "expected"), [
    ("/descubrir/serie/15/temporadas/3", 404),
    ("/descubrir/serie/15/temporadas/-1", 422),
    ("/descubrir/serie/15/temporadas/101", 422),
    ("/descubrir/serie/15/temporadas/1?pagina=41", 422),
    ("/descubrir/serie/15/temporadas/1/episodios/99/solicitar", 404),
    ("/descubrir/serie/15/temporadas/1/episodios/42/solicitar", 409),
    ("/descubrir/serie/15/solicitar", 422),
])
def test_serie_rechaza_episodios_y_temporadas_incorrectos(client, monkeypatch, path, expected):
    browser, db = client
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: SeasonTMDB())
    result = browser.post(path) if path.endswith("/solicitar") else browser.get(path)
    assert result.status_code == expected
    with Session(db) as s:
        assert not s.exec(select(Solicitud)).all()
        assert not s.exec(select(Descarga)).all()


def test_temporada_no_fiable_o_show_adulto_se_rechaza(client, monkeypatch):
    browser, db = client
    class WrongSeason(SeasonTMDB):
        def season_details(self, tmdb_id, season_number):
            return {**super().season_details(tmdb_id, season_number), "season_number": 5}
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: WrongSeason())
    assert browser.get("/descubrir/serie/15/temporadas/1").status_code == 404
    assert browser.post(
        "/descubrir/serie/15/temporadas/1/episodios/2/solicitar"
    ).status_code == 404

    class AdultShow(SeasonTMDB):
        def details(self, media_type, tmdb_id):
            return {**super().details(media_type, tmdb_id), "adult": True}
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: AdultShow())
    assert browser.get("/descubrir/serie/15/temporadas/1").status_code == 404
    assert browser.post(
        "/descubrir/serie/15/temporadas/1/episodios/2/solicitar"
    ).status_code == 404
    with Session(db) as s:
        assert not s.exec(select(Solicitud)).all()


def test_temporadas_necesitan_sesion(client, monkeypatch):
    browser, _ = client
    monkeypatch.setattr(descubrir, "_tmdb_client", lambda: SeasonTMDB())
    app.dependency_overrides.pop(get_current_profile)
    assert browser.get("/descubrir/serie/15/temporadas/1").status_code == 401
    assert browser.post(
        "/descubrir/serie/15/temporadas/1/episodios/2/solicitar"
    ).status_code == 401


def test_cliente_tmdb_restringe_urls_de_temporada(monkeypatch):
    from app.tmdb import TMDBClient, TMDBError

    fake = object.__new__(TMDBClient)
    paths = []
    def fake_get(path, params=None):
        paths.append(path)
        return {"season_number": 1, "episodes": []}
    monkeypatch.setattr(fake, "_get", fake_get)
    assert fake.season_details(15, 1)["season_number"] == 1
    assert paths == ["tv/15/season/1"]
    for series_id, season in [(0, 1), (15, -1), (15, 101), (True, 1), (15, True)]:
        with pytest.raises(TMDBError):
            fake.season_details(series_id, season)
    assert paths == ["tv/15/season/1"]
