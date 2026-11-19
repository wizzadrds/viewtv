"""Pruebas del inicio controlado de torrents."""

from unittest.mock import Mock

import pytest

from app.qbittorrent import QBittorrentClient


@pytest.mark.parametrize("length", [40, 64])
def test_start_torrent_usa_hash_explicito(length):
    client = object.__new__(QBittorrentClient)
    client._request = Mock()

    torrent_hash = "a" * length
    client.start_torrent(torrent_hash)

    client._request.assert_called_once_with(
        "POST",
        "/api/v2/torrents/start",
        data={"hashes": torrent_hash},
    )


@pytest.mark.parametrize(
    "torrent_hash",
    ["", "all", "abc", "g" * 40, "a" * 39, "a" * 65],
)
def test_start_torrent_rechaza_hash_no_valido(torrent_hash):
    client = object.__new__(QBittorrentClient)
    client._request = Mock()

    with pytest.raises(ValueError):
        client.start_torrent(torrent_hash)

    client._request.assert_not_called()
