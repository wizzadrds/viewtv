from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Literal

import httpx

from app.config import Settings, get_settings


class JackettError(Exception):
    """Error controlado al comunicarse con Jackett."""


@dataclass(frozen=True, slots=True)
class JackettResult:
    title: str
    download_url: str | None
    magnet_url: str | None
    info_hash: str | None
    seeders: int | None
    peers: int | None
    size_bytes: int | None
    categories: tuple[str, ...]
    indexer: str | None
    published_at: str | None


@dataclass(frozen=True, slots=True)
class JackettIndexer:
    id: str
    configured: bool | None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _torznab_attributes(item: ET.Element) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for element in item.iter():
        if _local_name(element.tag) != "attr":
            continue
        name = element.attrib.get("name")
        value = element.attrib.get("value")
        if name and value is not None:
            attributes[name.lower()] = value
    return attributes


def _optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class JackettClient:
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._base_url = self._settings.jackett_base_url.rstrip("/")
        self._api_key = self._settings.jackett_api_key
        self._timeout = self._settings.jackett_timeout_seconds
        self._transport = transport

    def _request(self, params: dict[str, str]) -> ET.Element:
        if not self._base_url or not self._api_key:
            raise JackettError("Jackett no está configurado.")

        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = client.get(
                    "/api/v2.0/indexers/all/results/torznab/api",
                    params={"apikey": self._api_key, **params},
                )
                response.raise_for_status()
                return ET.fromstring(response.content)
        except httpx.HTTPError:
            raise JackettError("Error de comunicación con Jackett.") from None
        except ET.ParseError:
            raise JackettError(
                "Jackett devolvió una respuesta XML no válida."
            ) from None
        except ValueError:
            raise JackettError(
                "Jackett devolvió una respuesta no válida."
            ) from None

    def search(
        self,
        query: str,
        search_type: Literal["search", "tvsearch", "movie"] = "search",
        categories: list[str] | None = None,
    ) -> list[JackettResult]:
        if not query.strip():
            raise ValueError("La búsqueda no puede estar vacía.")

        params = {"t": search_type, "q": query.strip()}
        if categories:
            params["cat"] = ",".join(categories)

        root = self._request(params)
        results: list[JackettResult] = []

        for item in root.iter():
            if _local_name(item.tag) != "item":
                continue

            title = item.findtext("title")
            if not title:
                continue

            attributes = _torznab_attributes(item)
            enclosure = next(
                (
                    element
                    for element in item
                    if _local_name(element.tag) == "enclosure"
                ),
                None,
            )

            download_url = (
                enclosure.attrib.get("url") if enclosure is not None else None
            )
            size_bytes = _optional_int(attributes.get("size"))
            if size_bytes is None and enclosure is not None:
                size_bytes = _optional_int(enclosure.attrib.get("length"))

            categories_found = tuple(
                element.text.strip()
                for element in item
                if _local_name(element.tag) == "category"
                and element.text
                and element.text.strip()
            )

            results.append(
                JackettResult(
                    title=title.strip(),
                    download_url=download_url,
                    magnet_url=attributes.get("magneturl"),
                    info_hash=attributes.get("infohash"),
                    seeders=_optional_int(attributes.get("seeders")),
                    peers=_optional_int(attributes.get("peers")),
                    size_bytes=size_bytes,
                    categories=categories_found,
                    indexer=(
                        item.findtext("jackettindexer")
                        or item.findtext("source")
                    ),
                    published_at=item.findtext("pubDate"),
                )
            )

        return results

    def get_indexers(self) -> list[JackettIndexer]:
        root = self._request({"t": "indexers"})
        indexers: list[JackettIndexer] = []

        for element in root.iter():
            if _local_name(element.tag).lower() != "indexer":
                continue

            indexer_id = element.attrib.get("id")
            if not indexer_id:
                continue

            configured_value = element.attrib.get("configured")
            configured = (
                configured_value.lower() == "true"
                if configured_value is not None
                else None
            )
            indexers.append(
                JackettIndexer(id=indexer_id, configured=configured)
            )

        return indexers
