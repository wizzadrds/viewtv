"""Sondeo seguro GET de traducciones del título. Solo salida agregada.

No descarga torrents ni toca SQLite, no revela tokens ni proveedores.
"""
import os
import re

from app.config import get_settings
from app.jackett import JackettClient, JackettError
from worker.processor import _to_database_results

TERMS = (
    ("ES", "Nadie 2", "movie"),
    ("ES_ANIO", "Nadie 2 2025", "movie"),
    ("ORIGINAL", "Nobody 2", "movie"),
    ("ORIGINAL_ANIO", "Nobody 2 2025", "movie"),
    ("ORIGINAL_GENERAL", "Nobody 2", "search"),
)


def main() -> None:
    settings = get_settings()
    if not settings.jackett_base_url or not settings.jackett_api_key:
        print("CONFIG=NO_DISPONIBLE", flush=True)
        return
    client = JackettClient(settings=settings)
    for label, title, kind in TERMS:
        if os.environ.get("VIEWTV_PROBE_ONLY_YEAR") == "1" and label != "ES_ANIO":
            continue
        try:
            results = client.search(title, search_type=kind)
            ready = _to_database_results(1, results)
        except (JackettError, ValueError, OSError) as error:
            print(f"{label}_ESTADO=ERROR_{type(error).__name__}", flush=True)
            continue
        print(
            f"{label}_ESTADO=OK RESULTADOS={len(results)} "
            f"LISTOS_PARA_GUARDAR={len(ready)}",
            flush=True,
        )
        if label == "ES_ANIO":
            coinciden_titulo = 0
            coinciden_anio = 0
            for item in ready:
                tokens = re.findall(r"[a-z0-9]+", item.titulo.casefold())
                if ("nadie" in tokens or "nobody" in tokens) and "2" in tokens:
                    coinciden_titulo += 1
                if "2025" in tokens:
                    coinciden_anio += 1
            print(f"ES_ANIO_COINCIDEN_TITULO={coinciden_titulo}", flush=True)
            print(f"ES_ANIO_MENCIONAN_2025={coinciden_anio}", flush=True)


if __name__ == "__main__":
    main()
