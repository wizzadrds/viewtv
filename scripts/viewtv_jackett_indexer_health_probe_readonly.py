"""Read-only: salud del único indexador configurado de Jackett.

Solo muestra flags y categorías; nunca la respuesta JSON, nombre del
indexador, clave, URLs, títulos ni mensajes privados del proveedor.
"""

from __future__ import annotations

import re
from urllib.parse import quote

import httpx
from app.config import get_settings
from app.jackett import JackettClient, JackettError


def health_summary(value: object, indexer_id: str) -> dict[str, str]:
    """Clasificación conservadora; no confundir ausencia de estado con OK."""
    if isinstance(value, list):
        matches = [
            item
            for item in value
            if isinstance(item, dict) and item.get("id") == indexer_id
        ]
        if len(matches) != 1:
            return {"INDEXADOR_SALUD": "NO_IDENTIFICABLE"}
        value = matches[0]
    if not isinstance(value, dict):
        return {"INDEXADOR_SALUD": "FORMATO_DESCONOCIDO"}
    result = {}
    for key, label in (
        ("configured", "CONFIGURADO"),
        ("enabled", "HABILITADO"),
        ("active", "ACTIVO"),
    ):
        present = value.get(key)
        result[label] = (
            "SI" if present is True else "NO" if present is False else "NO_INFORMADO"
        )
    error_present = value.get("lastError")
    result["ULTIMO_ERROR"] = (
        "SI"
        if isinstance(error_present, str) and bool(error_present.strip())
        else "NO"
        if isinstance(error_present, str)
        else "NO_INFORMADO"
    )
    status = value.get("status")
    if isinstance(status, str):
        lowered = status.casefold()
        result["ESTADO"] = (
            "NORMAL"
            if lowered in {"ok", "active", "healthy"}
            else "FALLO"
            if lowered in {"error", "failed", "unhealthy"}
            else "NO_CLASIFICADO"
        )
    else:
        result["ESTADO"] = "NO_INFORMADO"
    return result


def main() -> None:
    settings = get_settings()
    if not settings.jackett_base_url or not settings.jackett_api_key:
        print("JACKETT_ESTADO=NO_CONFIGURADO")
        return
    try:
        indexers = JackettClient(settings=settings).get_indexers()
        configured = [item for item in indexers if item.configured is True]
        if len(configured) != 1:
            print("JACKETT_ESTADO=REQUIERE_REVISION")
            return
        indexer_id = configured[0].id
        if re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", indexer_id) is None:
            print("JACKETT_ESTADO=ID_NO_VALIDA")
            return
        with httpx.Client(
            base_url=settings.jackett_base_url.rstrip("/"),
            timeout=settings.jackett_timeout_seconds,
        ) as client:
            response = client.get(
                "/api/v2.0/indexers/" + quote(indexer_id, safe=""),
                params={"apikey": settings.jackett_api_key},
            )
            if 300 <= response.status_code < 400:
                print("JACKETT_ESTADO=API_ADMINISTRATIVA_RESTRINGIDA")
                return
            response.raise_for_status()
            payload = response.json()
    except (JackettError, httpx.HTTPError, ValueError, TypeError, OSError):
        print("JACKETT_ESTADO=NO_VERIFICABLE")
        return

    summary = health_summary(payload, indexer_id)
    print("JACKETT_ESTADO=LECTURA_OK")
    for key, value in sorted(summary.items()):
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
