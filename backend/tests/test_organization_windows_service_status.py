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
