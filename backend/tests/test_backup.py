from datetime import UTC, datetime, timedelta
import sqlite3

import pytest

from scripts.backup_db import create_backup, prune_old_backups, sqlite_file_from_url


def make_database(path):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE perfil (id INTEGER PRIMARY KEY, nombre TEXT)")
        connection.execute("INSERT INTO perfil (nombre) VALUES ('Adultos'), ('Infantil')")


def test_create_backup_copies_and_validates_sqlite(tmp_path):
    source = tmp_path / "source.db"
    destination = tmp_path / "backups"
    make_database(source)

    backup = create_backup(f"sqlite:///{source}", destination)

    assert backup.is_file()
    with sqlite3.connect(backup) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM perfil").fetchone()[0] == 2


def test_create_backup_prunes_only_old_viewtv_backups(tmp_path):
    source = tmp_path / "source.db"
    destination = tmp_path / "backups"
    make_database(source)
    destination.mkdir()
    old_backup = destination / "viewtv-20200101-000000.db"
    unrelated = destination / "other.db"
    old_backup.write_bytes(b"old")
    unrelated.write_bytes(b"keep")
    old_time = (datetime.now(UTC) - timedelta(days=40)).timestamp()
    old_backup.touch()
    import os

    os.utime(old_backup, (old_time, old_time))

    create_backup(f"sqlite:///{source}", destination, retention_days=30)

    assert not old_backup.exists()
    assert unrelated.exists()
    assert len(list(destination.glob("viewtv-*.db"))) == 1


def test_invalid_database_url_is_rejected():
    with pytest.raises(ValueError, match="solo admite SQLite"):
        sqlite_file_from_url("postgresql://localhost/viewtv")


def test_missing_database_does_not_prune_existing_backups(tmp_path):
    destination = tmp_path / "backups"
    destination.mkdir()
    old_backup = destination / "viewtv-20200101-000000.db"
    old_backup.write_bytes(b"keep")

    with pytest.raises(FileNotFoundError):
        create_backup("sqlite:////missing/viewtv.db", destination)

    assert old_backup.exists()


def test_prune_requires_positive_retention(tmp_path):
    with pytest.raises(ValueError, match="al menos 1"):
        prune_old_backups(tmp_path, 0)
