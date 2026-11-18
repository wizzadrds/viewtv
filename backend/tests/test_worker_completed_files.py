"""Pruebas de verificación de descargas completadas."""

from types import SimpleNamespace

import pytest
from worker.completed_files import verify_completed_files
from worker.file_validator import InvalidTorrentFiles

HASH = "a" * 40
SAVE_PATH = r"C:\VIEWTV\media\descargas_temporales"


def fake_client(torrents, files):
    calls = []

    def torrents_info(*, hashes):
        calls.append(("torrents", hashes))
        return torrents

    def torrent_files(torrent_hash):
        calls.append(("files", torrent_hash))
        return files

    return SimpleNamespace(
        torrents_info=torrents_info,
        torrent_files=torrent_files,
        calls=calls,
    )


def torrent(**changes):
    result = {
        "hash": HASH,
        "state": "stoppedUP",
        "progress": 1.0,
        "total_size": 4,
        "save_path": SAVE_PATH,
    }
    result.update(changes)
    return result


def test_verifies_completed_torrent(tmp_path):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")
    client = fake_client(
        [torrent()],
        [{"name": "pelicula.mkv", "size": 4, "progress": 1.0}],
    )

    result = verify_completed_files(client, HASH, tmp_path)

    assert result == [(tmp_path / "pelicula.mkv").resolve()]
    assert client.calls == [
        ("torrents", [HASH]),
        ("files", HASH),
    ]


@pytest.mark.parametrize(
    "state",
    ["downloading", "metaDL", "checkingUP", "stoppedDL"],
)
def test_rejects_torrent_not_ready(tmp_path, state):
    client = fake_client([torrent(state=state)], [])

    with pytest.raises(InvalidTorrentFiles):
        verify_completed_files(client, HASH, tmp_path)

    assert client.calls == [("torrents", [HASH])]


def test_rejects_different_hash(tmp_path):
    client = fake_client([torrent(hash="b" * 40)], [])

    with pytest.raises(InvalidTorrentFiles):
        verify_completed_files(client, HASH, tmp_path)


def test_rejects_duplicate_matching_hash(tmp_path):
    client = fake_client([torrent(), torrent()], [])

    with pytest.raises(InvalidTorrentFiles):
        verify_completed_files(client, HASH, tmp_path)


def test_rejects_missing_file(tmp_path):
    client = fake_client(
        [torrent()],
        [{"name": "pelicula.mkv", "size": 4, "progress": 1.0}],
    )

    with pytest.raises(InvalidTorrentFiles):
        verify_completed_files(client, HASH, tmp_path)


def test_rejects_incomplete_file(tmp_path):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")
    client = fake_client(
        [torrent()],
        [{"name": "pelicula.mkv", "size": 4, "progress": 0.5}],
    )

    with pytest.raises(InvalidTorrentFiles):
        verify_completed_files(client, HASH, tmp_path)


def test_rejects_inconsistent_total_size(tmp_path):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")
    client = fake_client(
        [torrent(total_size=100)],
        [{"name": "pelicula.mkv", "size": 4, "progress": 1.0}],
    )

    with pytest.raises(InvalidTorrentFiles):
        verify_completed_files(client, HASH, tmp_path)
