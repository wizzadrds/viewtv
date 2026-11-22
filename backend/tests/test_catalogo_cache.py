"""Catálogo de metadatos independiente, en fichero temporal y SIN descargas."""
from datetime import UTC, datetime, timedelta

import pytest

from app import catalogador_cli, catalogo_cache


def entry(number: int, kind: str = "pelicula", genre: int = 27,
          year: int = 2026, **extra) -> dict:
    result = {
        "id": number,
        "title": f"Película número {number}",
        "name": f"Serie número {number}",
        "overview": "Sinopsis de ejemplo.",
        "release_date": f"{year}-01-12",
        "first_air_date": f"{year}-01-12",
        "genre_ids": [genre],
        "adult": False,
        "poster_path": "/poster.png",
        "backdrop_path": "/fondo.jpg",
        "popularity": 100.0 - number / 10000,
    }
    result.update(extra)
    return result


@pytest.fixture
def isolated_catalog(monkeypatch, tmp_path):
    path = tmp_path / "metadatos.db"
    monkeypatch.setenv("VIEWTV_CATALOG_PATH", str(path))
    db = catalogo_cache.create_writer()
    yield db
    db.close()


def test_no_se_crea_catalogo_al_consultar(monkeypatch, tmp_path):
    path = tmp_path / "metadatos.db"
    monkeypatch.setenv("VIEWTV_CATALOG_PATH", str(path))
    assert catalogo_cache.open_reader() is None
    assert catalogo_cache.read_shelf("pelicula") is None
    assert catalogo_cache.status()["total"] == 0
    assert not path.exists()


def test_ingesta_deduplica_y_no_crea_tablas_viewtv(isolated_catalog, tmp_path):
    db = isolated_catalog
    result = {"results": [
        entry(1), entry(2, genre=28, year=2025),
        entry(3, adult=True),
        entry(4, poster_path="//atacante/foto.jpg"),
        entry(5, title="<script>archivo</script>"),
    ]}
    assert catalogo_cache.upsert_page(db, "pelicula", result) == 4
    db.commit()
    assert catalogo_cache.status()["total"] == 4
    assert catalogo_cache.status()["series"] == 0
    horror = catalogo_cache.read_shelf("pelicula", genre=27)
    assert horror is not None
    assert horror["total"] == 3
    assert horror["elementos"][0]["imagen_portada"].startswith("https://image.tmdb.org/")
    assert catalogo_cache.read_shelf("pelicula", genre=28)["total"] == 1
    assert catalogo_cache.read_shelf("pelicula", year=2025)["total"] == 1
    assert catalogo_cache.search_shelf("pelicula", "número 2")["total"] == 1
    assert catalogo_cache.search_shelf("pelicula", "%_")["total"] == 0
    assert catalogo_cache.search_shelf("pelicula", "script")["total"] == 1
    assert db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='descarga'"
    ).fetchone() is None
    assert db.execute("PRAGMA user_version").fetchone()[0] == 1
    assert (tmp_path / "metadatos.db").is_file()
    assert not (tmp_path / "viewtv.db").exists()


def test_reescribe_metadatos_no_duplica(isolated_catalog):
    db = isolated_catalog
    catalogo_cache.upsert_page(db, "pelicula", {"results": [entry(33)]})
    catalogo_cache.upsert_page(db, "pelicula", {
        "results": [entry(33, overview="Sinopsis actualizada")],
    })
    db.commit()
    assert catalogo_cache.status()["total"] == 1
    updated = catalogo_cache.read_shelf("pelicula")
    assert updated["elementos"][0]["sinopsis"] == "Sinopsis actualizada"


def test_paginacion_hasta_250_000_sin_cargarlo_todo(isolated_catalog):
    db = isolated_catalog
    for page in range(3):
        catalogo_cache.upsert_page(
            db, "pelicula",
            {"results": [entry(page * 20 + number + 1) for number in range(20)]},
        )
    db.commit()
    a = catalogo_cache.read_shelf("pelicula", page=1)
    b = catalogo_cache.read_shelf("pelicula", page=2)
    c = catalogo_cache.read_shelf("pelicula", page=3)
    assert a["total"] == 60
    assert a["paginas"] == 3
    assert len(a["elementos"]) == len(b["elementos"]) == len(c["elementos"]) == 20
    assert len({
        i["tmdb_id"] for page in (a, b, c) for i in page["elementos"]
    }) == 60
    assert catalogo_cache.read_shelf(None, page=2500)["elementos"] == []


def test_validacion_rechaza_adultos_y_datos_erroneos(isolated_catalog):
    db = isolated_catalog
    assert catalogo_cache.normalize_entry(entry(1, adult=True), "pelicula") is None
    assert catalogo_cache.normalize_entry(entry(2, id=True), "pelicula") is None
    assert catalogo_cache.normalize_entry(entry(3, title="\n"), "pelicula") is None
    assert catalogo_cache.normalize_entry(entry(4), "episodio") is None
    assert catalogo_cache.normalize_entry(entry(5, poster_path="//bad.site/photo.png"), "pelicula")[
        "imagen_portada"
    ] is None
    with pytest.raises(ValueError):
        catalogo_cache.upsert_page(db, "serie", {"results": "texto"})
    with pytest.raises(ValueError):
        catalogo_cache.upsert_page(db, "serie", {"results": [entry(i) for i in range(21)]})


class FakeTMDB:
    def __init__(self):
        self.calls = []

    def discover(self, kind, *, genre_id=None, release_year=None, page=1):
        number = len(self.calls) + 1
        self.calls.append((kind, genre_id, release_year, page))
        return {"results": [entry(
            number, kind=kind, genre=genre_id or 28,
            year=release_year or 2026,
        )], "total_pages": 500}


def test_catalogador_avanza_por_fuentey_no_repite_tras_reinicio(
    monkeypatch, tmp_path,
):
    monkeypatch.setenv("VIEWTV_CATALOG_PATH", str(tmp_path / "metadatos.db"))
    client = FakeTMDB()
    now = datetime.now(UTC)
    first = catalogador_cli.refresh(now=now, pause=0, pages_per_stream=2, client=client)
    assert first["estado"] == "correcto"
    assert first["peticiones"] == 2 * len(catalogador_cli._streams())
    # Clave compuesta (tipo, tmdb_id): los mismos IDs pueden ser película o serie.
    assert catalogo_cache.status()["total"] >= len(client.calls) // 2
    second = catalogador_cli.refresh(
        now=now + timedelta(hours=1), pause=0, client=client,
    )
    assert second["estado"] == "esperando_proximo_ciclo"
    assert second["peticiones"] == 0
    db = catalogo_cache.open_reader()
    assert db is not None
    try:
        cursors = db.execute("SELECT pagina_siguiente FROM cursor_ingesta").fetchall()
        assert len(cursors) == len(catalogador_cli._streams())
        assert all(row[0] == 3 for row in cursors)
    finally:
        db.close()


def test_presupuesto_consultas_restringido():
    with pytest.raises(ValueError):
        catalogador_cli.refresh(pages_per_stream=1000)
    with pytest.raises(ValueError):
        catalogador_cli.refresh(pause=-1)


def test_busqueda_SQL_segura_incluye_escape_literal(isolated_catalog):
    db = isolated_catalog
    catalogo_cache.upsert_page(db, "pelicula", {"results": [entry(1)]})
    db.commit()
    assert catalogo_cache.search_shelf("pelicula", "' OR 1=1 --")["total"] == 0
    assert catalogo_cache.status()["total"] == 1


def test_limite_duro_de_fichas_sin_borrar_existentes(isolated_catalog, monkeypatch):
    db = isolated_catalog
    monkeypatch.setattr(catalogo_cache, "MAX_CATALOG", 3)
    total = catalogo_cache.upsert_page(
        db, "pelicula",
        {"results": [entry(i) for i in range(1, 6)]},
    )
    db.commit()
    assert total == 3
    assert catalogo_cache.status()["total"] == 3
    # Un título ya guardado sí puede refrescar sus metadatos en el límite.
    catalogo_cache.upsert_page(
        db, "pelicula",
        {"results": [entry(1, overview="Portada revisada"), entry(99)]},
    )
    db.commit()
    assert catalogo_cache.status()["total"] == 3
    assert catalogo_cache.search_shelf("pelicula", "número 99")["total"] == 0
    assert catalogo_cache.read_shelf("pelicula")["elementos"][0]["sinopsis"] == "Portada revisada"


def test_cuota_escalable_y_rechazo_de_configuracion_no_segura():
    assert catalogo_cache._catalog_limit("250000") == 250_000
    assert catalogo_cache._catalog_limit("1000000") == 1_000_000
    assert catalogo_cache.MAX_PAGE >= 50_000
    for value in ("", "-1", "0", "100", "1000001", "sin_limite", "1.2"):
        with pytest.raises(ValueError):
            catalogo_cache._catalog_limit(value)


def test_metadatos_caducados_no_se_sirven_ni_se_cuentan(isolated_catalog):
    db = isolated_catalog
    assert catalogo_cache.upsert_page(
        db, "pelicula", {"results": [entry(10), entry(11)]},
    ) == 2
    db.execute(
        "UPDATE ficha SET actualizado_en = datetime('now','-151 days') "
        "WHERE tmdb_id = 10",
    )
    db.commit()
    assert catalogo_cache.status()["total"] == 1
    assert catalogo_cache.read_shelf("pelicula")["total"] == 1
    assert catalogo_cache.search_shelf("pelicula", "número 10")["total"] == 0
    assert catalogo_cache.prune_expired(db, now=datetime.now(UTC)) == 1
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM ficha").fetchone()[0] == 1
    assert catalogo_cache.prune_expired(db, now=datetime.now(UTC)) == 0


def test_catalogador_renueva_los_existentes_con_limite_alcanzado(monkeypatch, tmp_path):
    monkeypatch.setenv("VIEWTV_CATALOG_PATH", str(tmp_path / "metadatos.db"))
    monkeypatch.setattr(catalogo_cache, "MAX_CATALOG", 1)
    mock = FakeTMDB()
    first = catalogador_cli.refresh(
        now=datetime.now(UTC), pause=0, pages_per_stream=1, client=mock,
    )
    assert first["estado"] == "correcto"
    assert first["peticiones"] == len(catalogador_cli._streams())
    assert catalogo_cache.status()["total"] == 1
    # El tope no bloquea la renovación: se consultan fuentes igualmente.
    assert catalogo_cache.open_reader() is not None


def test_catalogador_elimina_caducados_aunque_no_toque_ciclo(monkeypatch, tmp_path):
    monkeypatch.setenv("VIEWTV_CATALOG_PATH", str(tmp_path / "metadatos.db"))
    source = FakeTMDB()
    instant = datetime.now(UTC)
    first = catalogador_cli.refresh(
        now=instant, pause=0, pages_per_stream=1, client=source,
    )
    assert first["estado"] == "correcto"
    db = catalogo_cache.create_writer()
    try:
        db.execute("UPDATE ficha SET actualizado_en = datetime('now','-151 days')")
        db.commit()
    finally:
        db.close()
    no_request_count = len(source.calls)
    result = catalogador_cli.refresh(
        now=instant + timedelta(minutes=10), pause=0, client=source,
    )
    assert result["estado"] == "esperando_proximo_ciclo"
    assert len(source.calls) == no_request_count
    assert catalogo_cache.status()["total"] == 0
    db = catalogo_cache.open_reader()
    assert db is not None
    try:
        assert db.execute("SELECT COUNT(*) FROM ficha").fetchone()[0] == 0
    finally:
        db.close()


def test_presupuesto_maximo_por_ciclo(monkeypatch, tmp_path):
    monkeypatch.setenv("VIEWTV_CATALOG_PATH", str(tmp_path / "metadatos.db"))
    # Nunca más de 96 peticiones aunque se añadan fuentes en el futuro.
    streams = [("s-" + str(i), "pelicula", None, None) for i in range(120)]
    monkeypatch.setattr(catalogador_cli, "_streams", lambda: streams)
    mock = FakeTMDB()
    result = catalogador_cli.refresh(
        now=datetime.now(UTC), pause=0, pages_per_stream=1, client=mock,
    )
    assert result["estado"] == "correcto"
    assert result["peticiones"] == catalogador_cli.MAX_REQUESTS_PER_CYCLE
    assert len(mock.calls) == catalogador_cli.MAX_REQUESTS_PER_CYCLE



def test_indice_caducidad_creado_sin_migrar_base_principal(isolated_catalog):
    db = isolated_catalog
    indexes = {r[1] for r in db.execute("PRAGMA index_list('ficha')").fetchall()}
    assert "idx_ficha_actualizado_en" in indexes
    assert db.execute("PRAGMA user_version").fetchone()[0] == 1
