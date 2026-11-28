"""Smoke del catálogo 250k dentro de API actual; GET sin descargas."""
from types import SimpleNamespace

from app.auth import get_current_profile
from app.catalogador_cli import MAX_REQUESTS_PER_CYCLE
from app.catalogo_cache import (
    MAX_CACHE_DAYS,
    MAX_CATALOG,
    MAX_PAGE,
    open_reader,
    status,
)
from app.main import app
from fastapi.testclient import TestClient

assert MAX_CATALOG == 250_000, "La API no ha cargado el nuevo presupuesto."
assert MAX_PAGE == 50_000
assert MAX_CACHE_DAYS == 150
assert MAX_REQUESTS_PER_CYCLE == 96
print("API_CAPACIDAD_TITULOS=250000")
print("CADUCIDAD_MAX_DIAS=150")
print("PRESUPUESTO_MAX_CONSULTAS=96")

state = status()
assert state["total"] >= 1_428
assert state["peliculas"] > 0 and state["series"] > 0
print("FICHAS_UNICAS_ACTUALES=" + str(state["total"]))
print("PELICULAS=" + str(state["peliculas"]))
print("SERIES=" + str(state["series"]))

db = open_reader()
assert db is not None
try:
    assert db.execute("PRAGMA user_version").fetchone()[0] == 1
    count = db.execute("SELECT COUNT(*) FROM ficha").fetchone()[0]
    assert count >= state["total"]
    names = {row[1] for row in db.execute("PRAGMA index_list('ficha')")}
    assert "idx_ficha_actualizado_en" in names
finally:
    db.close()
print("ESQUEMA_REUTILIZADO_E_INDICE_CADUCIDAD=OK")

with TestClient(app) as browser:
    assert browser.get("/descubrir/catalogo/estado").status_code == 401
    assert browser.get("/descubrir/filas/catalogo").status_code == 401
    app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id=1)
    try:
        response = browser.get("/descubrir/catalogo/estado")
        assert response.status_code == 200
        assert response.json()["limite_fichas"] == 250_000
        assert response.json()["total"] == state["total"]
        first = browser.get("/descubrir/filas/catalogo?pagina=1")
        second = browser.get("/descubrir/filas/catalogo?pagina=2")
        assert first.status_code == second.status_code == 200
        a, b = first.json(), second.json()
        assert a["total"] == b["total"] == state["total"]
        assert len(a["elementos"]) == len(b["elementos"]) == 20
        assert {
            (item["tipo"], item["tmdb_id"]) for item in a["elementos"]
        }.isdisjoint({
            (item["tipo"], item["tmdb_id"]) for item in b["elementos"]
        })
        assert browser.get("/descubrir/filas/catalogo?pagina=50001").status_code == 422
    finally:
        app.dependency_overrides.clear()
print("CONTADOR_PRIVADO_PAGINACION_Y_CONTROL_ACCESO=OK")
print("CATALOGO_ESCALABLE_SMOKE=PASS")
