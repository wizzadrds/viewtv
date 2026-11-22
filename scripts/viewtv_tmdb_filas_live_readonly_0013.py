"""Prueba GET de filas en la API REAL: sin descargas ni exponer claves.

TestClient usa una sustitución de identidad únicamente en este proceso efímero.
No modifica la autenticación de la aplicación que atiende al usuario.
"""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth import get_current_profile
from app.config import get_settings
from app.main import app

if not get_settings().tmdb_api_key:
    raise RuntimeError("TMDB no está configurada en la API")
with TestClient(app) as client:
    denied = client.get("/descubrir/filas")
    if denied.status_code != 401:
        raise RuntimeError("Protección del catálogo fallida")
    print("FILA_SIN_SESION=401")
    app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id=1)
    try:
        listing = client.get("/descubrir/filas")
        if listing.status_code != 200:
            raise RuntimeError("Filas no disponibles")
        data = listing.json()
        if data["tmdb_configurado"] is not True:
            raise RuntimeError("TMDB no está habilitada para el frontend")
        print("TMDB_ESTADO_HTTP=200 CONFIGURADA=SI")
        categories = [
            "recientes", "peliculas-nuevas", "tendencias",
            "accion", "terror", "comedia", "ciencia-ficcion",
            "series-tendencia", "series-misterio",
        ]
        listed = [row["id"] for row in data["filas"]]
        if listed != categories:
            raise RuntimeError("Orden de las filas inesperado")
        print("FILAS_DEFINIDAS=9")
        for category in categories:
            response = client.get("/descubrir/filas/" + category)
            if response.status_code != 200:
                print("CATEGORIA_ERROR=" + category + " STATUS=" + str(response.status_code))
                raise RuntimeError("Categoría HTTP incorrecta")
            elements = response.json().get("elementos")
            if not isinstance(elements, list) or not elements:
                raise RuntimeError("Categoría vacía: " + category)
            posters = sum(bool(x.get("imagen_portada")) for x in elements)
            if category != "recientes" and posters <= 0:
                raise RuntimeError("No hay carátulas TMDB: " + category)
            if category == "recientes" and not all(
                x.get("disponible_local") is True for x in elements
            ):
                raise RuntimeError("Recientes no son medios locales")
            print(
                "CATEGORIA=" + category + " HTTP=200 ELEMENTOS="
                + str(len(elements)) + " CON_POSTER=" + str(posters)
            )
    finally:
        app.dependency_overrides.clear()
print("VIEWTV_TMDB_FILAS_REAL=9_OK")
