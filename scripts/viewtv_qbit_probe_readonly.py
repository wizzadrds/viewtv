"""Consulta de conectividad GET a qBittorrent. Sin tocar torrents ni contraseñas.

Ejecutar por stdin en el worker activo. Solo consulta /api/v2/app/version.
"""

from __future__ import annotations

from app.config import get_settings
from app.qbittorrent import QBittorrentClient, QBittorrentError


def main() -> None:
    settings = get_settings()
    print("QBIT_URL_CONFIGURADA=" + str(bool(settings.qbittorrent_base_url)))
    print("QBIT_CLAVE_CONFIGURADA=" + str(bool(settings.qbittorrent_api_key)))
    if not settings.qbittorrent_base_url or not settings.qbittorrent_api_key:
        print("QBIT_LECTURA=OMITIDA_SIN_CONFIGURACION")
        return
    try:
        QBittorrentClient(settings=settings).version()
        print("QBIT_LECTURA_VERSION=OK")
    except QBittorrentError:
        print("QBIT_LECTURA_VERSION=FALLO_CONEXION")
    except (OSError, TypeError, ValueError):
        print("QBIT_LECTURA_VERSION=FALLO_NO_ESPERADO")


if __name__ == "__main__":
    main()
