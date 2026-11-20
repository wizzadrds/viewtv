"""Sondeo de capacidades de los indexadores configurados, solo GET.

Nunca publica identificadores, URLs, API keys, términos o contenidos del índice.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

import httpx
from app.config import get_settings
from app.jackett import JackettClient, JackettError


def capabilities_summary(raw: bytes) -> dict[str, str]:
    """Flags conservadores: una respuesta desconocida no es capacidad válida."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return {"CAPS_ESTADO": "XML_INVALIDO"}
    if root.tag.rsplit("}", 1)[-1].casefold() != "caps":
        return {"CAPS_ESTADO": "NO_CAPS"}
    names: set[str] = set()
    search_q: dict[str, bool] = {}
    for element in root.iter():
        kind = element.tag.rsplit("}", 1)[-1].casefold()
        if kind not in {"search", "movie-search", "tv-search"}:
            continue
        available = element.attrib.get("available", "").casefold() in {
            "yes",
            "true",
            "1",
        }
        if available:
            names.add(kind)
        params = {
            part.strip().casefold()
            for part in element.attrib.get("supportedParams", "").split(",")
        }
        search_q[kind] = available and "q" in params
    return {
        "CAPS_ESTADO": "OK",
        "CAPS_GENERAL": "SI" if "search" in names else "NO",
        "CAPS_MOVIE": "SI" if "movie-search" in names else "NO",
        "CAPS_TV": "SI" if "tv-search" in names else "NO",
        "CAPS_GENERAL_Q": "SI" if search_q.get("search") else "NO",
        "CAPS_MOVIE_Q": "SI" if search_q.get("movie-search") else "NO",
        "CAPS_TV_Q": "SI" if search_q.get("tv-search") else "NO",
    }


def configured_indexer_caps(client: JackettClient, indexer_id: str) -> dict[str, str]:
    """Consulta un indexador explícito; nunca envía una orden ni descarga."""
    if re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", indexer_id) is None:
        return {"CAPS_ESTADO": "ID_NO_ADMISIBLE"}
    s = client._settings
    try:
        with httpx.Client(
            base_url=s.jackett_base_url.rstrip("/"),
            timeout=s.jackett_timeout_seconds,
        ) as http:
            response = http.get(
                "/api/v2.0/indexers/"
                + quote(indexer_id, safe="")
                + "/results/torznab/api",
                params={"apikey": s.jackett_api_key, "t": "caps"},
            )
            response.raise_for_status()
    except httpx.HTTPError:
        return {"CAPS_ESTADO": "ERROR_HTTP_O_RED"}
    return capabilities_summary(response.content)


def main() -> None:
    settings = get_settings()
    if not settings.jackett_base_url or not settings.jackett_api_key:
        print("JACKETT_CAPS=NO_CONFIGURADO")
        return
    try:
        client = JackettClient(settings=settings)
        configured = [i for i in client.get_indexers() if i.configured is True]
    except (JackettError, OSError, ValueError, TypeError):
        print("JACKETT_CAPS=NO_DISPONIBLE")
        return

    print(
        "INDEXADORES_ACTIVOS_RANGO="
        + ("0" if not configured else "1" if len(configured) == 1 else "MAS_DE_UNO")
    )
    if len(configured) != 1:
        print("JACKETT_CAPS=REQUIERE_REVISION")
        return
    report = configured_indexer_caps(client, configured[0].id)
    for key, value in sorted(report.items()):
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
