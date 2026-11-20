"""Contratos de privacidad del preflight de proveedores y staging VIEWTV.

Toda la suite usa datos inventados; ninguna prueba consulta la red ni Windows.
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.jackett import JackettError, JackettResult

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_result(*, with_link: bool):
    return JackettResult(
        title="TITULO_INTERNO_PROHIBIDO",
        download_url="https://privado.invalid/SECRETO" if with_link else None,
        magnet_url=None,
        info_hash="a" * 40,
        seeders=3,
        peers=1,
        size_bytes=12345,
        categories=("999",),
        indexer="INDEXADOR_PRIVADO",
        published_at="fecha",
    )


@pytest.mark.parametrize(
    ("path", "valid"),
    [
        (r"C:\VIEWTV\media\descargas_temporales", True),
        (r"c:/viewtv/media/descargas_temporales/", True),
        (r"C:\VIEWTV\media\other", True),
        (r"Z:\otro", True),
        (r"..\descargas_temporales", False),
        (r"C:\VIEWTV\media\otra\..\descargas_temporales", False),
        (r"\\server\share\VIEWTV", False),
        ("", False),
        (None, False),
        (13, False),
    ],
)
def test_windows_path_requires_plain_absolute_drive(path, valid):
    qbit = load_script("viewtv_qbit_staging_probe_readonly")
    assert (qbit.comparable_windows_path(path) is not None) is valid


def test_preferences_summarizes_without_secret_paths():
    qbit = load_script("viewtv_qbit_staging_probe_readonly")
    prefs = {
        "save_path": r"c:/viewtv/media/descargas_temporales",
        "temp_path": r"Z:\PRIVATE\SECRETO",
        "temp_path_enabled": False,
        "password": "NO_MOSTRAR",
        "proxy_password": "NO_MOSTRAR_PROXY",
    }
    summary = qbit.classify_preferences(prefs)
    assert summary == {
        "RUTA_DEFECTO": "IGUAL",
        "RUTA_TEMPORAL": "DISTINTA",
        "USO_CARPETA_TEMPORAL": "NO",
    }
    output = str(summary)
    for private in ("SECRETO", "PRIVATE", "NO_MOSTRAR", "Z:"):
        assert private not in output


def test_noncomparable_preferences_fail_to_claim_match():
    qbit = load_script("viewtv_qbit_staging_probe_readonly")
    assert qbit.classify_preferences(None) == {"PREFERENCIAS_FORMATO": "INVALIDO"}
    assert qbit.classify_preferences({}) == {
        "RUTA_DEFECTO": "NO_COMPARABLE",
        "RUTA_TEMPORAL": "NO_COMPARABLE",
        "USO_CARPETA_TEMPORAL": "NO",
    }


def test_jackett_result_aggregation_never_exposes_titles_or_links():
    jackett = load_script("viewtv_jackett_search_probe_readonly")
    assert jackett.result_summary([])["JACKETT_RESULTADOS_RANGO"] == "0"
    assert jackett.result_summary([fake_result(with_link=False)]) == {
        "JACKETT_RESULTADOS_RANGO": "1_A_5",
        "JACKETT_RESULTADOS_ENLACE": "NO",
    }
    results = [fake_result(with_link=True) for _ in range(21)]
    report = jackett.result_summary(results)
    assert report == {
        "JACKETT_RESULTADOS_RANGO": "MAS_DE_20",
        "JACKETT_RESULTADOS_ENLACE": "SI",
    }
    for forbidden in ("TITULO_INTERNO_PROHIBIDO", "SECRETO", "INDEXADOR_PRIVADO"):
        assert forbidden not in str(report)


def test_qbit_probe_prints_only_safe_flags(monkeypatch, capsys):
    qbit = load_script("viewtv_qbit_staging_probe_readonly")

    class FakeQbit:
        def __init__(self, settings):
            pass

        def _request(self, method, path):
            assert (method, path) == ("GET", "/api/v2/app/preferences")
            return SimpleNamespace(
                json=lambda: {
                    "save_path": r"C:\VIEWTV\media\descargas_temporales",
                    "temp_path": r"D:\PRIVADO\SECRETOS",
                    "temp_path_enabled": False,
                    "pass": "NO_REVELAR",
                }
            )

    monkeypatch.setattr(
        qbit,
        "get_settings",
        lambda: SimpleNamespace(qbittorrent_base_url="fake", qbittorrent_api_key="fake"),
    )
    monkeypatch.setattr(qbit, "QBittorrentClient", FakeQbit)
    qbit.main()
    output = capsys.readouterr().out
    assert "QBIT_PREFERENCIAS=OK" in output
    assert "RUTA_DEFECTO=IGUAL" in output
    for forbidden in ("C:\\", "D:\\", "SECRETOS", "NO_REVELAR"):
        assert forbidden not in output


def test_jackett_probe_uses_get_only_and_keeps_results_private(monkeypatch, capsys):
    jackett = load_script("viewtv_jackett_search_probe_readonly")
    observed = []

    class FakeJackett:
        def __init__(self, settings):
            pass

        def search(self, query, search_type):
            observed.append((query, search_type))
            return [fake_result(with_link=True)]

    monkeypatch.setattr(
        jackett,
        "get_settings",
        lambda: SimpleNamespace(jackett_base_url="fake", jackett_api_key="fake"),
    )
    monkeypatch.setattr(jackett, "JackettClient", FakeJackett)
    jackett.main()
    output = capsys.readouterr().out
    assert observed == [
        ("Big Buck Bunny", "movie"),
        ("ubuntu", "search"),
    ]
    assert "JACKETT_BUSQUEDA_MOVIE=OK" in output
    assert "JACKETT_BUSQUEDA_SEARCH=OK" in output
    for forbidden in ("TITULO_INTERNO_PROHIBIDO", "SECRETO", "INDEXADOR_PRIVADO"):
        assert forbidden not in output


def test_jackett_failure_does_not_log_server_error(monkeypatch, capsys):
    jackett = load_script("viewtv_jackett_search_probe_readonly")

    class FakeJackett:
        def __init__(self, settings):
            pass

        def search(self, query, search_type):
            raise JackettError("token secreto y URL privada")

    monkeypatch.setattr(
        jackett,
        "get_settings",
        lambda: SimpleNamespace(jackett_base_url="fake", jackett_api_key="fake"),
    )
    monkeypatch.setattr(jackett, "JackettClient", FakeJackett)
    jackett.main()
    output = capsys.readouterr().out
    assert "JACKETT_BUSQUEDA_MOVIE=FALLO" in output
    assert "JACKETT_BUSQUEDA_SEARCH=FALLO" in output
    assert "secreto" not in output
    assert "privada" not in output
