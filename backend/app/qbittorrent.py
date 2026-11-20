from __future__ import annotations

import httpx

from app.config import Settings, get_settings


class QBittorrentError(Exception):
    """Error controlado al comunicarse con qBittorrent."""


class QBittorrentAddPending(QBittorrentError):
    """qBittorrent aceptó un alta asíncrona; NO repetir su POST."""


class QBittorrentClient:
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._base_url = self._settings.qbittorrent_base_url.rstrip("/")
        self._api_key = self._settings.qbittorrent_api_key
        self._timeout = self._settings.qbittorrent_timeout_seconds
        self._transport = transport

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
    ) -> httpx.Response:
        if not self._base_url or not self._api_key:
            raise QBittorrentError("qBittorrent no está configurado.")

        try:
            with httpx.Client(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = client.request(
                    method,
                    path,
                    params=params,
                    data=data,
                )
                response.raise_for_status()
                return response
        except httpx.HTTPError:
            raise QBittorrentError(
                "Error de comunicación con qBittorrent."
            ) from None

    def version(self) -> str:
        response = self._request("GET", "/api/v2/app/version")
        version = response.text.strip()
        if not version:
            raise QBittorrentError(
                "qBittorrent devolvió una versión vacía."
            )
        return version

    def torrents_info(
        self,
        hashes: list[str] | None = None,
        *,
        tag: str | None = None,
    ) -> list[dict]:
        params = {}

        if hashes:
            params["hashes"] = "|".join(hashes)

        if tag:
            params["tag"] = tag

        response = self._request(
            "GET",
            "/api/v2/torrents/info",
            params=params,
        )
        try:
            payload = response.json()
        except ValueError:
            raise QBittorrentError(
                "qBittorrent devolvió una respuesta JSON no válida."
            ) from None

        if not isinstance(payload, list):
            raise QBittorrentError(
                "qBittorrent devolvió una lista de torrents no válida."
            )
        if not all(isinstance(item, dict) for item in payload):
            raise QBittorrentError(
                "qBittorrent devolvió datos de torrents no válidos."
            )
        return payload

    def torrent_files(self, torrent_hash: str) -> list[dict]:
        """Consulta los archivos asociados a un torrent."""
        if not isinstance(torrent_hash, str) or not torrent_hash.strip():
            raise ValueError("El hash del torrent no puede estar vacío.")

        import re

        if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", torrent_hash) is None:
            raise ValueError("El hash del torrent no es válido.")

        response = self._request(
            "GET",
            "/api/v2/torrents/files",
            params={"hash": torrent_hash},
        )

        try:
            payload = response.json()
        except ValueError:
            raise QBittorrentError(
                "qBittorrent devolvió una respuesta JSON no válida."
            ) from None

        if not isinstance(payload, list) or not all(
            isinstance(item, dict) for item in payload
        ):
            raise QBittorrentError(
                "qBittorrent devolvió una lista de archivos no válida."
            )

        return payload

    def start_torrent(self, torrent_hash: str) -> None:
        """Inicia exclusivamente el torrent identificado por su hash."""
        import re

        if not isinstance(torrent_hash, str) or re.fullmatch(
            r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}",
            torrent_hash,
        ) is None:
            raise ValueError("El hash del torrent no es válido.")

        self._request(
            "POST",
            "/api/v2/torrents/start",
            data={"hashes": torrent_hash},
        )

    def add_torrent(
        self,
        url: str,
        save_path: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        paused: bool = False,
        stopped: bool | None = None,
    ) -> None:
        if not url.strip():
            raise ValueError("La URL del torrent no puede estar vacía.")

        data = {"urls": url.strip()}
        if stopped is None:
            data["paused"] = str(paused).lower()
        else:
            data["stopped"] = str(stopped).lower()
        if save_path:
            data["savepath"] = save_path
        if category:
            data["category"] = category
        if tags:
            data["tags"] = ",".join(tags)

        response = self._request(
            "POST",
            "/api/v2/torrents/add",
            data=data,
        )
        # WebAPI 2.14+/qBittorrent 5.3 ya no responde solo "Ok.":
        # HTTP 202 y pending_count>0 significa que qBittorrent está
        # resolviendo el enlace ASÍNCRONAMENTE. Nunca repetir el POST
        # hasta reconciliar mediante GET de la etiqueta.
        if response.text.strip().lower() == "ok.":
            return

        try:
            details = response.json()
        except ValueError:
            details = None

        if isinstance(details, dict):
            if (
                details.get("success_count") == 1
                and details.get("pending_count") == 0
                and details.get("failure_count") == 0
            ):
                return

            if (
                response.status_code == 202
                and isinstance(details.get("pending_count"), int)
                and details["pending_count"] > 0
            ):
                raise QBittorrentAddPending(
                    "Alta aceptada y pendiente de confirmación en qBittorrent."
                )

        if response.status_code == 202:
            # Respuesta 202 sin JSON interpretable: posible alta aún
            # pendiente; fallo cerrado para impedir reenvío duplicado.
            raise QBittorrentAddPending(
                "Alta aceptada y pendiente de confirmación en qBittorrent."
            )

        raise QBittorrentError(
            "qBittorrent no confirmó el alta del torrent."
        )
