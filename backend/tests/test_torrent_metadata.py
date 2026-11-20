"""Validación segura de tamaños e infohash contra metainfo bencoded."""
from hashlib import sha1

import httpx
import pytest

from worker.torrent_metadata import (
    TorrentMetadataError,
    es_url_jackett_dl,
    interpretar_torrent,
    obtener_metadatos_jackett,
    tamano_incoherente,
)

BASE = "http://host.docker.internal:9117"
URL = BASE + "/dl/release-ficticia?token=prueba"


def _bencode(item):
    if isinstance(item, int):
        return b"i" + str(item).encode("ascii") + b"e"
    if isinstance(item, bytes):
        return str(len(item)).encode("ascii") + b":" + item
    if isinstance(item, list):
        return b"l" + b"".join(_bencode(x) for x in item) + b"e"
    if isinstance(item, dict):
        return b"d" + b"".join(
            _bencode(key) + _bencode(item[key]) for key in sorted(item)
        ) + b"e"
    raise TypeError(type(item))


def _torrent(total):
    info = {b"name": b"Peliculaficticia.mkv", b"length": total}
    return _bencode({b"announce": b"http://tracker.invalid/announce", b"info": info}), _bencode(info)


def test_parse_single_file_exact_bytes_and_digest():
    raw, info_raw = _torrent(17_686_540_911)
    result = interpretar_torrent(raw)
    assert result.size_bytes == 17_686_540_911
    assert result.info_hash == sha1(info_raw).hexdigest()
    assert tamano_incoherente(1_503_238_554, result.size_bytes)


def test_parse_multi_file_total_and_rounding():
    info = {
        b"name": b"Peliculaficticia",
        b"files": [
            {b"length": 1_000_000_000, b"path": [b"video.mkv"]},
            {b"length": 300, b"path": [b"readme.txt"]},
        ],
    }
    result = interpretar_torrent(_bencode({b"info": info}))
    assert result.size_bytes == 1_000_000_300
    assert not tamano_incoherente(970_000_000, result.size_bytes)


@pytest.mark.parametrize("raw", [
    b"", b"hello", b"d4:infoi4ee",
    b"d4:infod6:lengthi-8eee",
    b"d4:infod6:lengthi0eee",
    b"d4:infod6:lengthi4eeeextra",
    b"d4:infod5:fileslee",
])
def test_refuse_bad_metainfo(raw):
    with pytest.raises(TorrentMetadataError):
        interpretar_torrent(raw)


@pytest.mark.parametrize("bad", [
    "http://evil.invalid/dl/x",
    "http://host.docker.internal:9118/dl/x",
    "https://host.docker.internal:9117/dl/x",
    "http://host.docker.internal:9117/api/x",
    "http://user:pass@host.docker.internal:9117/dl/x",
    "magnet:?xt=urn:btih:abcdef",
    "http://127.0.0.1:9117/dl/x",
])
def test_jackett_origin_whitelist(bad):
    assert not es_url_jackett_dl(bad, BASE)
    with pytest.raises(TorrentMetadataError):
        obtener_metadatos_jackett(bad, BASE)


def test_stream_jackett_metainfo_without_redirect():
    raw, _ = _torrent(100_000_000)
    seen = []
    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(200, headers={"content-type": "application/x-bittorrent"}, content=raw)
    meta = obtener_metadatos_jackett(URL, BASE, transport=httpx.MockTransport(handler))
    assert meta.size_bytes == 100_000_000
    assert seen == ["/dl/release-ficticia"]


def test_refuse_redirect_or_error_without_second_request():
    seen = []
    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(302, headers={"location": "http://evil.invalid/"})
    with pytest.raises(TorrentMetadataError):
        obtener_metadatos_jackett(URL, BASE, transport=httpx.MockTransport(handler))
    assert seen == ["/dl/release-ficticia"]


def test_refuse_large_torrent_body():
    with pytest.raises(TorrentMetadataError):
        obtener_metadatos_jackett(
            URL, BASE, transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=b"d" + b"x" * 4_000_001)
            ),
        )


def test_tamano_incoherente_limits():
    assert not tamano_incoherente(None, 9999)
    assert not tamano_incoherente(0, 9999)
    assert tamano_incoherente(100_000_000, 200_000_000)
    assert not tamano_incoherente(1_000_000_000, 1_040_000_000)
