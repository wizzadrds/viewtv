"""Smoke GET de catálogo ampliado en API productiva, sin modificar BD.

TestClient sustituye la autenticación únicamente en este proceso de ensayo,
no en el proceso que atiende al navegador. No imprime títulos ni secretos.
"""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth import get_current_profile
from app.catalogo_cache import status
from app.main import app

numbers = status()
assert numbers["total"] >= 100
assert numbers["peliculas"] > 0 and numbers["series"] > 0
print("CATALOGO_REAL_UNICO="+str(numbers["total"]))
print("CATALOGO_REAL_PELICULAS="+str(numbers["peliculas"]))
print("CATALOGO_REAL_SERIES="+str(numbers["series"]))

with TestClient(app) as browser:
    for path in ("/descubrir/catalogo/estado", "/descubrir/filas/catalogo"):
        result = browser.get(path)
        assert result.status_code == 401, (path, result.status_code)
    print("SIN_SESION_CATALOGO=401")

    app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id=1)
    try:
        state = browser.get("/descubrir/catalogo/estado")
        assert state.status_code == 200
        assert state.json()["total"] == numbers["total"]
        assert state.json()["solo_metadatos"] is True
        print("API_CONTADOR=200")

        first = browser.get("/descubrir/filas/catalogo?pagina=1")
        second = browser.get("/descubrir/filas/catalogo?pagina=2")
        assert first.status_code == second.status_code == 200
        a = first.json()
        b = second.json()
        assert a["total"] == numbers["total"]
        assert len(a["elementos"]) == len(b["elementos"]) == 20
        assert a["paginas"] >= 2
        a_ids = {(i["tipo"], i["tmdb_id"]) for i in a["elementos"]}
        b_ids = {(i["tipo"], i["tmdb_id"]) for i in b["elementos"]}
        assert a_ids.isdisjoint(b_ids)
        assert all(i.get("disponible_local") in (True, False) for i in a["elementos"])
        assert all(i.get("imagen_portada", "").startswith("https://image.tmdb.org/")
                   for i in a["elementos"] if i.get("imagen_portada"))
        print("CATALOGO_PAGINACION_2_PAGINAS=200")

        for category in ("recientes", "peliculas-nuevas", "terror",
                         "accion", "comedia", "ciencia-ficcion", "series-misterio"):
            result = browser.get("/descubrir/filas/" + category)
            assert result.status_code == 200, (category, result.status_code)
            assert result.json()["elementos"], category
            print("FILA_"+category+"=200")
        assert browser.get("/descubrir/filas/catalogo?pagina=2501").status_code == 422
        print("LIMITE_PAGINACION=422")
    finally:
        app.dependency_overrides.clear()
print("CATALOGO_AMPLIO_SOLO_LECTURA=PASS")
