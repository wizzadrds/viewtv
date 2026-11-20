"""Sondeo GET de búsqueda en Jackett, sin crear solicitudes ni descargas.

Usa exclusivamente el título de una obra de animación libre de Blender.
No imprime títulos obtenidos, índices, enlaces, URLs, hashes ni claves.
"""

from __future__ import annotations

from app.config import get_settings
from app.jackett import JackettClient, JackettError, JackettResult

PROBE_QUERY = "Big Buck Bunny"


def result_summary(results: list[JackettResult]) -> dict[str, str]:
    """Agrega la búsqueda sin exponer ningún dato devuelto por el índice."""
    count = len(results)
    if count == 0:
        amount = "0"
    elif count <= 5:
        amount = "1_A_5"
    elif count <= 20:
        amount = "6_A_20"
    else:
        amount = "MAS_DE_20"
    return {
        "JACKETT_RESULTADOS_RANGO": amount,
        "JACKETT_RESULTADOS_ENLACE": (
            "SI" if any(r.magnet_url or r.download_url for r in results) else "NO"
        ),
    }


def main() -> None:
    settings = get_settings()
    if not settings.jackett_base_url or not settings.jackett_api_key:
        print("JACKETT_BUSQUEDA_PRUEBA=NO_CONFIGURADO")
        return
    client = JackettClient(settings=settings)
    for kind, query in (("movie", PROBE_QUERY), ("search", "ubuntu")):
        try:
            results = client.search(query, search_type=kind)
        except (JackettError, ValueError, OSError):
            print(f"JACKETT_BUSQUEDA_{kind.upper()}=FALLO")
            continue
        print(f"JACKETT_BUSQUEDA_{kind.upper()}=OK")
        for name, value in sorted(result_summary(results).items()):
            print(f"{kind.upper()}_{name}={value}")


if __name__ == "__main__":
    main()
