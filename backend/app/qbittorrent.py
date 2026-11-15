from __future__ import annotations

import httpx

from app.config import Settings, get_settings


class QBittorrentError(Exception):
    """Error controlado al comunicarse con qBittorrent."""


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
    ) -> list[dict[str, object]]:
        params = {"hashes": "|".join(hashes)} if hashes else None
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

    def add_torrent(
        self,
        url: str,
        save_path: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        paused: bool = False,
    ) -> None:
        if not url.strip():
            raise ValueError("La URL del torrent no puede estar vacía.")

        data = {"urls": url.strip(), "paused": str(paused).lower()}
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
        if response.text.strip().lower() != "ok.":
            raise QBittorrentError(
                "qBittorrent no confirmó el alta del torrent."
            )
