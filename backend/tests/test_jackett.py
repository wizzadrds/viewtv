import httpx
import pytest

from app.config import get_settings
from app.jackett import JackettClient, JackettError

TORZNAB_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:torznab="http://torznab.com/schemas/2015/feed">
  <channel>
    <item>
      <title>Contenido de prueba 1080p</title>
      <link>https://example.test/download/123</link>
      <enclosure url="https://example.test/download/123"
                 length="1500000000" type="application/x-bittorrent"/>
      <category>2000</category>
      <torznab:attr name="seeders" value="25"/>
      <torznab:attr name="peers" value="30"/>
      <torznab:attr name="infohash"
                    value="0123456789abcdef0123456789abcdef01234567"/>
      <torznab:attr name="magneturl"
                    value="magnet:?xt=urn:btih:0123456789abcdef"/>
      <torznab:attr name="size" value="1500000000"/>
      <jackettindexer>indexer-prueba</jackettindexer>
      <pubDate>Sat, 14 Nov 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Resultado incompleto</title>
    </item>
  </channel>
</rss>
"""


def _settings(monkeypatch):
    monkeypatch.setenv("JACKETT_BASE_URL", "http://jackett.test:9117")
    monkeypatch.setenv("JACKETT_API_KEY", "jackett-secret")
    get_settings.cache_clear()
    return get_settings()


def test_search_parses_torznab_results(monkeypatch):
    settings = _settings(monkeypatch)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=TORZNAB_XML)

    client = JackettClient(settings, transport=httpx.MockTransport(handler))
    results = client.search("pelicula de prueba", categories=["2000"])

    assert len(results) == 2
    first = results[0]
    assert first.title == "Contenido de prueba 1080p"
    assert first.download_url == "https://example.test/download/123"
    assert first.magnet_url.startswith("magnet:")
    assert first.info_hash == "0123456789abcdef0123456789abcdef01234567"
    assert first.seeders == 25
    assert first.peers == 30
    assert first.size_bytes == 1_500_000_000
    assert first.categories == ("2000",)
    assert first.indexer == "indexer-prueba"

    assert results[1].title == "Resultado incompleto"
    assert results[1].seeders is None
    assert requests[0].url.params["t"] == "search"
    assert requests[0].url.params["q"] == "pelicula de prueba"
    assert requests[0].url.params["cat"] == "2000"


def test_search_rejects_empty_query(monkeypatch):
    client = JackettClient(_settings(monkeypatch))

    with pytest.raises(ValueError, match="vacía"):
        client.search("   ")


def test_search_sanitizes_http_errors(monkeypatch):
    settings = _settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    client = JackettClient(settings, transport=httpx.MockTransport(handler))

    with pytest.raises(JackettError) as error:
        client.search("prueba")

    assert "jackett-secret" not in str(error.value)


def test_search_rejects_invalid_xml(monkeypatch):
    settings = _settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<rss><channel>")

    client = JackettClient(settings, transport=httpx.MockTransport(handler))

    with pytest.raises(JackettError, match="XML"):
        client.search("prueba")


def test_get_indexers_parses_indexer_list(monkeypatch):
    settings = _settings(monkeypatch)
    xml = b"""<indexers>
      <indexer id="indexer-a" configured="true"/>
      <indexer id="indexer-b" configured="false"/>
    </indexers>"""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["t"] == "indexers"
        return httpx.Response(200, content=xml)

    client = JackettClient(settings, transport=httpx.MockTransport(handler))
    indexers = client.get_indexers()

    assert [(item.id, item.configured) for item in indexers] == [
        ("indexer-a", True),
        ("indexer-b", False),
    ]


def test_missing_configuration_is_reported(monkeypatch):
    monkeypatch.setenv("JACKETT_BASE_URL", "")
    monkeypatch.setenv("JACKETT_API_KEY", "")
    get_settings.cache_clear()

    client = JackettClient(get_settings())

    with pytest.raises(JackettError, match="no está configurado"):
        client.search("prueba")


@pytest.mark.parametrize("http_status", [200, 400])
def test_search_reports_torznab_indexer_error(
    monkeypatch, http_status
):
    settings = _settings(monkeypatch)

    xml = (
        b'<error code="900" '
        b'description="Error interno: jackett-secret" />'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            http_status,
            content=xml,
            request=request,
        )

    client = JackettClient(
        settings,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(JackettError) as error:
        client.search("contenido de prueba")

    message = str(error.value)

    assert "Torznab 900" in message
    assert "jackett-secret" not in message
    assert "Error interno" not in message
