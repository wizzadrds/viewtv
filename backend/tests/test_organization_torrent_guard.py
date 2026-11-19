"""La futura organización rechaza torrents ajenos; solo respuestas simuladas."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from worker.file_validator import InvalidTorrentFiles
from worker.organization_torrent_guard import (
    EXPECTED_SAVE_PATH,
    verify_organization_torrent_identity,
)

from app.models import Descarga
from app.qbittorrent import QBittorrentError

TORRENT_HASH = "a" * 40
DOWNLOAD_ID = 23
OWNER_TAG = f"viewtv-descarga-{DOWNLOAD_ID}"


def valid_download(**changes):
    params = {
        "id": DOWNLOAD_ID,
        "solicitud_id": 44,
        "titulo": "Vídeo ficticio",
        "estado": "completada",
        "progreso": 1.0,
        "estado_verificacion": "verificada",
        "verificada_en": datetime.now(UTC),
        "organizacion_estado": "pendiente",
        "qbittorrent_hash": TORRENT_HASH,
    }
    params.update(changes)
    return Descarga(**params)


def response_torrent(**changes):
    record = {
        "hash": TORRENT_HASH,
        "tags": OWNER_TAG,
        "state": "stoppedUP",
        "save_path": EXPECTED_SAVE_PATH,
        "progress": 1.0,
        "total_size": 5,
    }
    record.update(changes)
    return record


def fake_client(torrents=None, files=None):
    calls = []

    def torrents_info(*, hashes):
        calls.append(("GET info", hashes))
        return [response_torrent()] if torrents is None else torrents

    def torrent_files(torrent_hash):
        calls.append(("GET files", torrent_hash))
        return (
            [{"name": "video.mkv", "size": 5, "progress": 1.0, "priority": 1}]
            if files is None
            else files
        )

    return SimpleNamespace(
        torrents_info=torrents_info,
        torrent_files=torrent_files,
        calls=calls,
    )


def test_owned_torrent_only_two_read_requests(tmp_path):
    video = tmp_path / "video.mkv"
    video.write_bytes(b"video")
    client = fake_client()
    selected = verify_organization_torrent_identity(
        client, valid_download(), tmp_path
    )
    assert selected == [video.resolve()]
    assert client.calls == [
        ("GET info", [TORRENT_HASH]),
        ("GET files", TORRENT_HASH),
    ]
    assert video.read_bytes() == b"video"


@pytest.mark.parametrize(
    "tags",
    [
        "",
        "viewtv-descarga-24",
        "viewtv-descarga-2",
        "viewtv",
        None,
        [OWNER_TAG],
        f"{OWNER_TAG},{OWNER_TAG}",
        f"{OWNER_TAG},viewtv-descarga-24",
        f"viewtv-descarga-24,{OWNER_TAG}",
    ],
)
def test_tag_must_belong_exclusively_to_download(tmp_path, tags):
    client = fake_client(torrents=[response_torrent(tags=tags)])
    with pytest.raises(InvalidTorrentFiles):
        verify_organization_torrent_identity(client, valid_download(), tmp_path)
    assert client.calls == [("GET info", [TORRENT_HASH])]


def test_unrelated_nonviewtv_tag_does_not_confuse_ownership(tmp_path):
    (tmp_path / "video.mkv").write_bytes(b"video")
    client = fake_client(torrents=[response_torrent(tags="otro," + OWNER_TAG)])
    assert verify_organization_torrent_identity(client, valid_download(), tmp_path)


@pytest.mark.parametrize(
    "torrents",
    [
        [],
        [response_torrent(hash="b" * 40)],
        [response_torrent(), response_torrent()],
        [response_torrent(), response_torrent(hash="b" * 40)],
        "bad response",
        [None],
    ],
)
def test_rejects_missing_mismatched_or_ambiguous_torrent(tmp_path, torrents):
    client = fake_client(torrents=torrents)
    with pytest.raises(InvalidTorrentFiles):
        verify_organization_torrent_identity(client, valid_download(), tmp_path)
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    "state",
    ["stoppedDL", "downloading", "checkingUP", "metaDL", "pausedUP", None],
)
def test_rejects_torrent_not_finished(tmp_path, state):
    client = fake_client(torrents=[response_torrent(state=state)])
    with pytest.raises(InvalidTorrentFiles):
        verify_organization_torrent_identity(client, valid_download(), tmp_path)
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    "save_path",
    [
        r"C:\VIEWTV\media\Peliculas",
        r"D:\VIEWTV\media\descargas_temporales",
        r"C:\VIEWTV\media\descargas_temporales\..\Series",
        "",
        None,
    ],
)
def test_rejects_unauthorized_save_directory(tmp_path, save_path):
    (tmp_path / "video.mkv").write_bytes(b"video")
    client = fake_client(torrents=[response_torrent(save_path=save_path)])
    with pytest.raises(InvalidTorrentFiles):
        verify_organization_torrent_identity(client, valid_download(), tmp_path)


@pytest.mark.parametrize(
    "changes",
    [
        {"estado": "descargando"},
        {"progreso": 0.5},
        {"estado_verificacion": "pendiente"},
        {"estado_verificacion": "fallida"},
        {"organizacion_estado": "no_requerida"},
        {"organizacion_estado": "organizada"},
        {"organizacion_estado": "requiere_revision"},
        {"verificada_en": None},
        {"qbittorrent_hash": "no-es-un-hash"},
        {"qbittorrent_hash": None},
        {"id": None},
    ],
)
def test_rejects_ineligible_database_record_before_network(tmp_path, changes):
    client = fake_client()
    with pytest.raises(InvalidTorrentFiles):
        verify_organization_torrent_identity(
            client, valid_download(**changes), tmp_path
        )
    assert client.calls == []


def test_rejects_file_outside_allowed_download_directory(tmp_path):
    client = fake_client(
        files=[{"name": "../outside.mkv", "size": 5, "progress": 1.0}],
    )
    with pytest.raises(InvalidTorrentFiles):
        verify_organization_torrent_identity(client, valid_download(), tmp_path)
    assert len(client.calls) == 2


def test_rejects_modified_bytes_or_size(tmp_path):
    (tmp_path / "video.mkv").write_bytes(b"alterado")
    client = fake_client()
    with pytest.raises(InvalidTorrentFiles):
        verify_organization_torrent_identity(client, valid_download(), tmp_path)


def test_rejects_symlinked_file(tmp_path):
    outside = tmp_path.parent / "fuera.mkv"
    outside.write_bytes(b"video")
    (tmp_path / "video.mkv").symlink_to(outside)
    client = fake_client()
    with pytest.raises(InvalidTorrentFiles):
        verify_organization_torrent_identity(client, valid_download(), tmp_path)
    assert outside.read_bytes() == b"video"


def test_rejects_incomplete_file_and_wrong_total(tmp_path):
    (tmp_path / "video.mkv").write_bytes(b"video")
    client = fake_client(
        files=[{"name": "video.mkv", "size": 5, "progress": 0.9}],
    )
    with pytest.raises(InvalidTorrentFiles):
        verify_organization_torrent_identity(client, valid_download(), tmp_path)

    client = fake_client(
        torrents=[response_torrent(total_size=6)]
    )
    with pytest.raises(InvalidTorrentFiles):
        verify_organization_torrent_identity(client, valid_download(), tmp_path)


def test_network_error_propagates_for_conservative_retry(tmp_path):
    def network_error(*, hashes):
        raise QBittorrentError("Error simulado")

    client = fake_client()
    client.torrents_info = network_error
    with pytest.raises(QBittorrentError):
        verify_organization_torrent_identity(client, valid_download(), tmp_path)


def test_accepts_v2_hash_and_case_variant(tmp_path):
    video = tmp_path / "video.mkv"
    video.write_bytes(b"video")
    torrent_hash = "ABCDEF" * 10 + "ABCD"
    client = fake_client(
        torrents=[response_torrent(hash=torrent_hash.lower())],
    )
    download = valid_download(qbittorrent_hash=torrent_hash)
    assert verify_organization_torrent_identity(client, download, tmp_path) == [
        video.resolve()
    ]
    assert client.calls == [
        ("GET info", [torrent_hash]),
        ("GET files", torrent_hash),
    ]
