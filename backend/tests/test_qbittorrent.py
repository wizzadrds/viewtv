from urllib.parse import parse_qs

import httpx
import pytest

from app.config import get_settings
from app.qbittorrent import QBittorrentClient, QBittorrentError


def _settings(monkeypatch):
    monkeypatch.setenv("QBITTORRENT_BASE_URL", "http://qbittorrent.test:8080")
    monkeypatch.setenv("QBITTORRENT_API_KEY", "qbt_test_secret")
    get_settings.cache_clear()
    return get_settings()


def test_version_returns_server_version(monkeypatch):
    settings = _settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/app/version"
        assert request.headers["Authorization"] == "Bearer qbt_test_secret"
        return httpx.Response(200, text="5.3.0")

    client = QBittorrentClient(
        settings,
        transport=httpx.MockTransport(handler),
    )

    assert client.version() == "5.3.0"


def test_torrents_info_filters_by_hashes(monkeypatch):
    settings = _settings(monkeypatch)
    expected_hash = "0123456789abcdef"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/torrents/info"
        assert request.url.params["hashes"] == expected_hash
        return httpx.Response(
            200,
            json=[{"hash": expected_hash, "progress": 0.5}],
        )

    client = QBittorrentClient(
        settings,
        transport=httpx.MockTransport(handler),
    )

    assert client.torrents_info([expected_hash]) == [
        {"hash": expected_hash, "progress": 0.5}
    ]


def test_torrents_info_without_hashes(monkeypatch):
    settings = _settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "hashes" not in request.url.params
        return httpx.Response(200, json=[])

    client = QBittorrentClient(
        settings,
        transport=httpx.MockTransport(handler),
    )

    assert client.torrents_info() == []


def test_add_torrent_sends_form_fields(monkeypatch):
    settings = _settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v2/torrents/add"
        assert request.headers["Authorization"] == "Bearer qbt_test_secret"

        fields = parse_qs(request.content.decode())
        assert fields["urls"] == ["magnet:?xt=urn:btih:abc123"]
        assert fields["savepath"] == ["/downloads"]
        assert fields["category"] == ["viewtv"]
        assert fields["tags"] == ["viewtv,solicitud-123"]
        assert fields["paused"] == ["false"]
        return httpx.Response(200, text="Ok.")

    client = QBittorrentClient(
        settings,
        transport=httpx.MockTransport(handler),
    )

    client.add_torrent(
        "magnet:?xt=urn:btih:abc123",
        save_path="/downloads",
        category="viewtv",
        tags=["viewtv", "solicitud-123"],
    )


def test_add_torrent_rejects_empty_url(monkeypatch):
    client = QBittorrentClient(_settings(monkeypatch))

    with pytest.raises(ValueError, match="vacía"):
        client.add_torrent("  ")


def test_add_torrent_requires_success_confirmation(monkeypatch):
    settings = _settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="Fails.")

    client = QBittorrentClient(
        settings,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(QBittorrentError, match="no confirmó"):
        client.add_torrent("magnet:?xt=urn:btih:abc123")


def test_http_errors_do_not_expose_api_key(monkeypatch):
    settings = _settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request)

    client = QBittorrentClient(
        settings,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(QBittorrentError) as error:
        client.version()

    assert "qbt_test_secret" not in str(error.value)


def test_missing_configuration_is_reported(monkeypatch):
    monkeypatch.setenv("QBITTORRENT_BASE_URL", "")
    monkeypatch.setenv("QBITTORRENT_API_KEY", "")
    get_settings.cache_clear()

    client = QBittorrentClient(get_settings())

    with pytest.raises(QBittorrentError, match="no está configurado"):
        client.version()
