"""Pruebas de preflight Jackett: datos inventados, sin red ni secretos."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAPS_XML = b"""<?xml version="1.0"?>
<caps>
  <searching>
    <search available="yes" supportedParams="q"/>
    <tv-search available="yes" supportedParams="q,season,ep"/>
    <movie-search available="yes" supportedParams="q,imdbid"/>
  </searching>
</caps>
"""


def test_canonical_capabilities_do_not_reveal_indexer_data():
    probe = load("viewtv_jackett_capabilities_probe_readonly")
    assert probe.capabilities_summary(CAPS_XML) == {
        "CAPS_ESTADO": "OK",
        "CAPS_GENERAL": "SI",
        "CAPS_MOVIE": "SI",
        "CAPS_TV": "SI",
        "CAPS_GENERAL_Q": "SI",
        "CAPS_MOVIE_Q": "SI",
        "CAPS_TV_Q": "SI",
    }


@pytest.mark.parametrize(
    ("xml", "result"),
    [
        (b"Not XML", {"CAPS_ESTADO": "XML_INVALIDO"}),
        (b"<error code='100'>private</error>", {"CAPS_ESTADO": "NO_CAPS"}),
        (b"<rss><channel/></rss>", {"CAPS_ESTADO": "NO_CAPS"}),
    ],
)
def test_invalid_or_error_caps_not_misreported_as_ok(xml, result):
    probe = load("viewtv_jackett_capabilities_probe_readonly")
    assert probe.capabilities_summary(xml) == result


def test_missing_movie_or_tv_caps_are_not_assumed():
    probe = load("viewtv_jackett_capabilities_probe_readonly")
    summary = probe.capabilities_summary(
        b'<caps><searching><search available="yes" supportedParams="q"/>'
        b'<movie-search available="no" supportedParams="q"/>'
        b"</searching></caps>"
    )
    assert summary["CAPS_GENERAL"] == "SI"
    assert summary["CAPS_MOVIE"] == "NO"
    assert summary["CAPS_TV"] == "NO"
    assert summary["CAPS_MOVIE_Q"] == "NO"


def test_supported_params_without_query_not_reported_as_title_search():
    probe = load("viewtv_jackett_capabilities_probe_readonly")
    summary = probe.capabilities_summary(
        b'<caps><searching><tv-search available="yes" supportedParams="season,ep"/>'
        b"</searching></caps>"
    )
    assert summary["CAPS_TV"] == "SI"
    assert summary["CAPS_TV_Q"] == "NO"


@pytest.mark.parametrize(
    "unsafe_id",
    ["", ".", "../secret", "id/part", "?key=a", "a%2fb", "  ", "x" * 101],
)
def test_capabilities_refuse_unsafe_ids_before_network(unsafe_id, monkeypatch):
    probe = load("viewtv_jackett_capabilities_probe_readonly")

    def forbidden(*args, **kwargs):
        raise AssertionError("La entrada inválida no debe crear cliente HTTP")

    monkeypatch.setattr(probe.httpx, "Client", forbidden)
    summary = probe.configured_indexer_caps(
        SimpleNamespace(_settings=SimpleNamespace()),
        unsafe_id,
    )
    assert summary == {"CAPS_ESTADO": "ID_NO_ADMISIBLE"}


def test_capabilities_only_perform_get_and_never_expose_key(monkeypatch):
    probe = load("viewtv_jackett_capabilities_probe_readonly")
    requests = []

    class FakeHTTP:
        def __init__(self, **kwargs):
            assert kwargs["base_url"] == "http://jackett-ficticio.invalid"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, path, *, params):
            requests.append((path, params))
            return SimpleNamespace(content=CAPS_XML, raise_for_status=lambda: None)

    monkeypatch.setattr(probe.httpx, "Client", FakeHTTP)
    settings = SimpleNamespace(
        jackett_base_url="http://jackett-ficticio.invalid",
        jackett_timeout_seconds=5,
        jackett_api_key="SECRETO_NUNCA_MOSTRAR",
    )
    report = probe.configured_indexer_caps(SimpleNamespace(_settings=settings), "indexer-ficticio")
    assert requests == [
        (
            "/api/v2.0/indexers/indexer-ficticio/results/torznab/api",
            {"apikey": "SECRETO_NUNCA_MOSTRAR", "t": "caps"},
        )
    ]
    assert report["CAPS_ESTADO"] == "OK"
    assert "SECRETO" not in str(report)
    assert "indexer-ficticio" not in str(report)


def test_health_status_absence_not_interpreted_as_healthy():
    health = load("viewtv_jackett_indexer_health_probe_readonly")
    report = health.health_summary({"id": "test"}, "test")
    assert report["ESTADO"] == "NO_INFORMADO"
    assert report["ULTIMO_ERROR"] == "NO_INFORMADO"
    assert report["ACTIVO"] == "NO_INFORMADO"


def test_health_summary_sanitizes_messages_and_tokens():
    health = load("viewtv_jackett_indexer_health_probe_readonly")
    report = health.health_summary(
        {
            "id": "test",
            "configured": True,
            "enabled": False,
            "active": False,
            "status": "error",
            "lastError": "URL SECRETA y contraseñas",
            "api_key": "NO_EXFILTRAR",
        },
        "test",
    )
    assert report == {
        "CONFIGURADO": "SI",
        "HABILITADO": "NO",
        "ACTIVO": "NO",
        "ULTIMO_ERROR": "SI",
        "ESTADO": "FALLO",
    }
    assert "SECRETA" not in str(report)
    assert "EXFILTRAR" not in str(report)


def test_health_list_without_exact_match_is_unverified():
    health = load("viewtv_jackett_indexer_health_probe_readonly")
    assert health.health_summary([{"id": "otro"}], "test") == {
        "INDEXADOR_SALUD": "NO_IDENTIFICABLE"
    }
    assert health.health_summary([{"id": "test"}, {"id": "test"}], "test") == {
        "INDEXADOR_SALUD": "NO_IDENTIFICABLE"
    }
