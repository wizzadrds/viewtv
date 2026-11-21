"""Preflight del publicador: consulta sin reclamar descargas ni editar SQLite."""

from worker import organization_windows_cli as cli
from worker.organization_windows_authority import WindowsPublicationPolicy


def test_status_matches_single_download_policy(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli,
        "publication_policy",
        lambda env: WindowsPublicationPolicy("single", 2, 5),
    )
    monkeypatch.setattr(cli, "_schema_0013", lambda: calls.append("schema"))
    assert cli.run("status") == {
        "estado": "listo", "modo": "single",
        "after_id": 2, "allowed_download_id": 5,
    }
    assert calls == ["schema"]


def test_status_disabled_does_not_touch_schema(monkeypatch):
    monkeypatch.setattr(
        cli,
        "publication_policy",
        lambda env: WindowsPublicationPolicy("disabled", 0),
    )
    monkeypatch.setattr(
        cli, "_schema_0013",
        lambda: (_ for _ in ()).throw(AssertionError("No consultar SQLite")),
    )
    assert cli.run("status") == {"estado": "deshabilitado"}


def test_status_general_never_authorizes_historical_id(monkeypatch):
    monkeypatch.setattr(
        cli,
        "publication_policy",
        lambda env: WindowsPublicationPolicy("general", 2),
    )
    monkeypatch.setattr(cli, "_schema_0013", lambda: None)
    assert cli.run("status") == {
        "estado": "listo", "modo": "general",
        "after_id": 2, "allowed_download_id": None,
    }


def test_general_sync_uses_existing_transactional_catalog_function(monkeypatch):
    calls = []

    class SessionStub:
        def __enter__(self):
            calls.append("session_open")
            return self

        def __exit__(self, *unused):
            calls.append("session_close")

    monkeypatch.setattr(
        cli, "publication_policy",
        lambda env: WindowsPublicationPolicy("general", 3),
    )
    monkeypatch.setattr(cli, "_schema_0013", lambda: calls.append("schema"))
    monkeypatch.setattr(cli, "Session", lambda engine: SessionStub())

    class JellyfinStub:
        def get_items(self, start, limit):
            calls.append(("preflight", start, limit))
            return {"Items": [{"Id": "a"}, {"Id": "b"}]}

    client = JellyfinStub()
    monkeypatch.setattr(cli, "JellyfinClient", lambda: client)
    monkeypatch.setattr(
        cli, "synchronize_catalog",
        lambda session, value: calls.append(("sync", value)) or 4,
    )

    assert cli.run("sync") == {
        "estado": "catalogo_sincronizado", "elementos_procesados": 4,
    }
    assert calls == [
        "schema", ("preflight", 0, 100), "session_open", ("sync", client),
        "session_close",
    ]


def test_single_mode_refuses_automatic_catalog_sync(monkeypatch):
    monkeypatch.setattr(
        cli, "publication_policy",
        lambda env: WindowsPublicationPolicy("single", 2, 3),
    )
    monkeypatch.setattr(cli, "_schema_0013", lambda: None)
    monkeypatch.setattr(
        cli, "JellyfinClient",
        lambda: (_ for _ in ()).throw(AssertionError("No contactar Jellyfin")),
    )
    import pytest
    with pytest.raises(ValueError, match="no autorizada"):
        cli.run("sync")


def test_disabled_mode_sync_remains_read_only(monkeypatch):
    monkeypatch.setattr(
        cli, "publication_policy",
        lambda env: WindowsPublicationPolicy("disabled", 0),
    )
    monkeypatch.setattr(
        cli, "_schema_0013",
        lambda: (_ for _ in ()).throw(AssertionError("No consultar SQLite")),
    )
    assert cli.run("sync") == {"estado": "deshabilitado"}


def test_general_sync_refuses_empty_jellyfin_before_sqlite_write(monkeypatch):
    import pytest

    monkeypatch.setattr(
        cli, "publication_policy",
        lambda env: WindowsPublicationPolicy("general", 3),
    )
    monkeypatch.setattr(cli, "_schema_0013", lambda: None)
    monkeypatch.setattr(
        cli, "JellyfinClient",
        lambda: type("JellyfinStub", (), {"get_items": lambda self, a, b: {"Items": []}})(),
    )
    monkeypatch.setattr(
        cli, "Session",
        lambda engine: (_ for _ in ()).throw(AssertionError("No abrir SQLite")),
    )
    with pytest.raises(ValueError, match="biblioteca mínima"):
        cli.run("sync")
