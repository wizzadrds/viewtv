"""Comprobación read-only de la carpeta por defecto de qBittorrent.

Ejecutar por stdin dentro del worker. Nunca imprime preferencias, URLs,
nombres de torrents, credenciales ni rutas reales. Solo booleanos.
La ruta de descarga de VIEWTV se solicita explícitamente en el POST,
por lo que una carpeta predeterminada distinta no demuestra fallo.
"""

from __future__ import annotations

import ntpath
import re

from app.config import get_settings
from app.qbittorrent import QBittorrentClient, QBittorrentError
from worker.download_processor import STAGING_PATH


def comparable_windows_path(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    drive, _ = ntpath.splitdrive(value)
    if (
        not ntpath.isabs(value)
        or re.fullmatch(r"[A-Za-z]:", drive) is None
        or ".." in value.replace("/", "\\").split("\\")
    ):
        return None
    return ntpath.normcase(ntpath.normpath(value))


def classify_preferences(payload: object) -> dict[str, str]:
    """Compara sin exponer los valores originales del servidor."""
    if not isinstance(payload, dict):
        return {"PREFERENCIAS_FORMATO": "INVALIDO"}
    reference = comparable_windows_path(STAGING_PATH)
    result: dict[str, str] = {}
    for key in ("save_path", "temp_path"):
        path = comparable_windows_path(payload.get(key))
        label = "RUTA_DEFECTO" if key == "save_path" else "RUTA_TEMPORAL"
        if path is None:
            result[label] = "NO_COMPARABLE"
        else:
            result[label] = "IGUAL" if path == reference else "DISTINTA"
    result["USO_CARPETA_TEMPORAL"] = (
        "SI" if payload.get("temp_path_enabled") is True else "NO"
    )
    return result


def main() -> None:
    settings = get_settings()
    if not settings.qbittorrent_base_url or not settings.qbittorrent_api_key:
        print("QBIT_PREFERENCIAS=NO_CONFIGURADO")
        return
    try:
        response = QBittorrentClient(settings=settings)._request(
            "GET", "/api/v2/app/preferences"
        )
        result = classify_preferences(response.json())
    except (QBittorrentError, ValueError, TypeError, OSError):
        print("QBIT_PREFERENCIAS=NO_DISPONIBLE")
        return
    print("QBIT_PREFERENCIAS=OK")
    for key, value in sorted(result.items()):
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
