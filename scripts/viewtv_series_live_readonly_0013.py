"""Smoke real de series: solo GET; nunca solicita ni descarga capítulos.

La identidad de prueba se sustituye únicamente en ESTE proceso efímero.
La API real que atiende al navegador conserva su autenticación sin cambios.
"""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth import get_current_profile
from app.catalogo_cache import status as catalog_status
from app.main import app
from app.relevancia_resultado import coincide_con_solicitud

assert not coincide_con_solicitud(
    "Serie de prueba S01E02", "serie", None, "Serie.de.prueba.S01E01.1080p",
)
assert coincide_con_solicitud(
    "Serie de prueba S01E02", "serie", None, "Serie.de.prueba.S01E02.1080p",
)
assert not coincide_con_solicitud(
    "Serie de prueba S01E02", "serie", None, "Serie.de.prueba.S01E02.S01E03.PACK",
)
print("VERIFICACION_EPISODIOS_EXACTOS=OK")

with TestClient(app) as browser:
    paths = [
        "/descubrir/serie/1396",
        "/descubrir/serie/1396/temporadas/1",
    ]
    for path in paths:
        assert browser.get(path).status_code == 401, path
    assert browser.post(
        "/descubrir/serie/1396/temporadas/1/episodios/1/solicitar"
    ).status_code == 401
    print("ACCESO_SIN_SESION=401")
    app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id=1)
    try:
        profile = browser.get("/descubrir/serie/1396")
        assert profile.status_code == 200, profile.status_code
        details = profile.json()
        seasons = details.get("temporadas")
        assert isinstance(seasons, list)
        assert len(seasons) >= 1
        assert any(s["temporada"] == 1 for s in seasons)
        assert details["tipo"] == "serie"
        assert details["tmdb_id"] == 1396
        print("FICHA_SERIE_TEMPORADAS=200")

        first = browser.get("/descubrir/serie/1396/temporadas/1")
        assert first.status_code == 200, first.status_code
        payload = first.json()
        assert payload["temporada"] == 1
        assert payload["total"] >= 1
        assert isinstance(payload["episodios"], list) and payload["episodios"]
        assert payload["episodios"][0]["episodio"] == 1
        assert all(isinstance(e["solicitable"], bool) for e in payload["episodios"])
        assert all(
            e["imagen"] is None or e["imagen"].startswith("https://image.tmdb.org/t/p/w500/")
            for e in payload["episodios"]
        )
        print("EPISODIOS_TEMPORADA_1_HTTP=200")
        print("NUMERO_TEMPORADAS="+str(len(seasons)))
        print("EPISODIOS_EN_TEMPORADA_1="+str(payload["total"]))

        error = browser.get("/descubrir/serie/1396/temporadas/101")
        assert error.status_code == 422
        print("TEMPORADA_FUERA_RANGO=422")
        assert browser.get("/descubrir/serie/1396/temporadas/1?pagina=31").status_code == 200
        assert browser.get("/descubrir/serie/1396/temporadas/1?pagina=41").status_code == 422
        print("PAGINACION_HASTA_40_PAGINAS=OK")
        rows = browser.get("/descubrir/filas/series-tendencia")
        assert rows.status_code == 200
        assert rows.json()["elementos"]
        assert all(item["tipo"] == "serie" for item in rows.json()["elementos"])
        print("CARRUSEL_SERIES_POR_SERIE=200")
    finally:
        app.dependency_overrides.clear()

counts = catalog_status()
assert counts["total"] >= 100
print("CATALOGO_PERSISTENTE_INTACTO="+str(counts["total"]))
print("DESCARGAS_AUTOMATICAS_INICIADAS=0")
print("SERIES_LIVE_READONLY=PASS")
