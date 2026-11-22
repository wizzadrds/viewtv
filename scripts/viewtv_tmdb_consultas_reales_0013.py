"""Sondeo TMDB real SOLO METADATOS, sin solicitudes, descargas ni títulos.

Para ejecutar exclusivamente en contenedor efímero del propietario. No imprime
claves, tokens, URLs de respuesta, títulos ni medios privados.
"""
from datetime import UTC, datetime

from app.config import get_settings
from app.tmdb import TMDBClient, TMDBError

settings = get_settings()
if not settings.tmdb_api_key:
    raise SystemExit("TMDB_CONFIGURADA=NO")
print("TMDB_CONFIGURADA=SI")
client = TMDBClient()
year = datetime.now(UTC).year
jobs = [
    ("TENDENCIAS_PELICULAS", lambda: client.trending("pelicula", 1)),
    ("ESTRENOS_DEL_ANIO", lambda: client.discover("pelicula", release_year=year)),
    ("ACCION", lambda: client.discover("pelicula", genre_id=28)),
    ("TERROR", lambda: client.discover("pelicula", genre_id=27)),
    ("SERIES", lambda: client.trending("serie", 1)),
]
success = 0
for label, call in jobs:
    try:
        result = call()
    except TMDBError:
        print(f"{label}=ERROR_CONSULTA")
        continue
    items = result.get("results")
    if not isinstance(items, list):
        print(f"{label}=RESULTADO_INVALIDO")
        continue
    safe_items = [
        item for item in items
        if isinstance(item, dict) and item.get("adult") is not True
        and isinstance(item.get("id"), int)
    ]
    posters = sum(bool(item.get("poster_path")) for item in safe_items)
    print(f"{label}=OK ELEMENTOS={len(safe_items)} CON_POSTER={posters}")
    success += 1
if success != len(jobs):
    raise SystemExit("TMDB_CONSULTAS_INCOMPLETAS")
print("TMDB_REAL_5_CATEGORIAS=OK")
