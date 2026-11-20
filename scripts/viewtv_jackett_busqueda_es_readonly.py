"""Diagnóstico GET de una película de título español; no crea solicitudes.

La salida es agregada: sin claves, identificadores del indexador, títulos
retornados, rutas privadas, hashes, magnets ni enlaces de descarga.
"""
from app.config import get_settings
from app.jackett import JackettClient, JackettError
from worker.processor import _to_database_results

TITLE = "Ocho apellidos vascos"


def main() -> None:
    settings = get_settings()
    if not settings.jackett_base_url or not settings.jackett_api_key:
        print("JACKETT_CONFIGURADO=NO")
        return
    client = JackettClient(settings=settings)
    for kind in ("movie", "search"):
        try:
            items = client.search(TITLE, search_type=kind)
        except (JackettError, ValueError, OSError) as exc:
            print(f"JACKETT_{kind.upper()}=FALLO_{type(exc).__name__}")
            continue
        selectable = sum(bool(item.download_url or item.magnet_url) for item in items)
        converted = _to_database_results(1, items)
        print(f"JACKETT_{kind.upper()}=OK")
        print(f"{kind.upper()}_RESULTADOS={len(items)}")
        print(f"{kind.upper()}_SELECCIONABLES={selectable}")
        print(f"{kind.upper()}_LISTOS_PARA_GUARDAR={len(converted)}")


if __name__ == "__main__":
    main()
