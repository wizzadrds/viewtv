"""Pruebas del validador de archivos de qBittorrent."""

import pytest
from worker.file_validator import (
    InvalidTorrentFiles,
    validate_torrent_files,
)

SAVE_PATH = r"C:\VIEWTV\media\descargas_temporales"


def torrent(**changes):
    result = {"save_path": SAVE_PATH, "progress": 1.0}
    result.update(changes)
    return result


def entry(name="pelicula.mkv", size=4, progress=1.0):
    return {"name": name, "size": size, "progress": progress}


def test_accepts_complete_file(tmp_path):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")

    result = validate_torrent_files(
        torrent(), [entry()], tmp_path
    )

    assert result == [(tmp_path / "pelicula.mkv").resolve()]


@pytest.mark.parametrize("progress", [0, 0.5, -1, 2, None, True])
def test_rejects_incomplete_torrent(tmp_path, progress):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")

    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(progress=progress), [entry()], tmp_path
        )


@pytest.mark.parametrize(
    "name",
    [
        "../fuera.mkv",
        r"..\\fuera.mkv",
        "/etc/passwd",
        r"C:\\Windows\\archivo.mkv",
        r"\\\\servidor\\archivo.mkv",
        "subcarpeta/../../fuera.mkv",
        "archivo:alternativo",
        "",
    ],
)
def test_rejects_unsafe_names(tmp_path, name):
    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(), [entry(name=name)], tmp_path
        )


def test_rejects_wrong_save_path(tmp_path):
    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(save_path=r"C:\OTRA_CARPETA"),
            [entry()],
            tmp_path,
        )


def test_rejects_missing_file(tmp_path):
    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(), [entry()], tmp_path
        )


def test_rejects_wrong_size(tmp_path):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")

    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(), [entry(size=100)], tmp_path
        )


def test_rejects_incomplete_file(tmp_path):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")

    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(), [entry(progress=0.5)], tmp_path
        )


def test_rejects_symlink_outside_root(tmp_path):
    root = tmp_path / "descargas"
    root.mkdir()

    outside = tmp_path / "fuera.mkv"
    outside.write_bytes(b"test")
    (root / "pelicula.mkv").symlink_to(outside)

    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(), [entry()], root
        )


def test_rejects_duplicate_names(tmp_path):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")

    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(),
            [entry(), entry(name="PELICULA.mkv")],
            tmp_path,
        )


def test_rejects_empty_file_list(tmp_path):
    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(torrent(), [], tmp_path)

def test_accepts_file_inside_subdirectory(tmp_path):
    carpeta = tmp_path / "Pelicula"
    carpeta.mkdir()
    (carpeta / "video.mkv").write_bytes(b"test")

    result = validate_torrent_files(
        torrent(),
        [entry(name="Pelicula/video.mkv")],
        tmp_path,
    )

    assert result == [(carpeta / "video.mkv").resolve()]


def test_rejects_symlink_in_intermediate_directory(tmp_path):
    root = tmp_path / "descargas"
    root.mkdir()

    outside = tmp_path / "externo"
    outside.mkdir()
    (outside / "video.mkv").write_bytes(b"test")

    (root / "Pelicula").symlink_to(
        outside,
        target_is_directory=True,
    )

    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(),
            [entry(name="Pelicula/video.mkv")],
            root,
        )

def test_rejects_symlink_inside_authorized_root(tmp_path):
    real = tmp_path / "Real"
    real.mkdir()
    (real / "video.mkv").write_bytes(b"test")

    (tmp_path / "Enlace").symlink_to(
        real,
        target_is_directory=True,
    )

    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(),
            [entry(name="Enlace/video.mkv")],
            tmp_path,
        )

def test_rejects_excluded_file(tmp_path):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")

    archivo = entry()
    archivo["priority"] = 0

    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(),
            [archivo],
            tmp_path,
        )


def test_rejects_inconsistent_total_size(tmp_path):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")

    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(total_size=100),
            [entry(size=4)],
            tmp_path,
        )


def test_accepts_consistent_total_size(tmp_path):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")

    result = validate_torrent_files(
        torrent(total_size=4),
        [entry(size=4)],
        tmp_path,
    )

    assert result == [(tmp_path / "pelicula.mkv").resolve()]

@pytest.mark.parametrize("priority", [-1, True, "1", 1.5])
def test_rejects_invalid_priority(tmp_path, priority):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")
    archivo = entry()
    archivo["priority"] = priority

    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(), [archivo], tmp_path
        )


@pytest.mark.parametrize("total_size", [-1, None])
def test_accepts_unknown_total_size(tmp_path, total_size):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")

    result = validate_torrent_files(
        torrent(total_size=total_size),
        [entry()],
        tmp_path,
    )

    assert result == [(tmp_path / "pelicula.mkv").resolve()]


@pytest.mark.parametrize("total_size", [-2, True, "4", 4.5])
def test_rejects_invalid_total_size(tmp_path, total_size):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")

    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(total_size=total_size),
            [entry()],
            tmp_path,
        )


def test_rejects_negative_file_size(tmp_path):
    (tmp_path / "pelicula.mkv").write_bytes(b"test")

    with pytest.raises(InvalidTorrentFiles):
        validate_torrent_files(
            torrent(), [entry(size=-1)], tmp_path
        )
