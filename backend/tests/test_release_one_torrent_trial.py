"""Ensayo seguro de UNA descarga con qBittorrent simulado y SQLite en memoria.

No permite torrents reales. Ninguna ruta productiva recibe POST.
"""

from urllib.parse import parse_qs

import httpx
import pytest
import worker.download_processor as processor
import worker.main as worker_main
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from worker.download_processor import STAGING_PATH

from app.config import Settings
from app.models import Descarga, Perfil, ResultadoBusqueda, Solicitud
from app.qbittorrent import QBittorrentClient
from app.queue import claim_next_download


class FakeQbit:
    def __init__(self, replies):
        self.replies = list(replies)
        self.queries = []
        self.added = []

    def torrents_info(self, hashes=None, *, tag=None):
        self.queries.append((hashes, tag))
        return self.replies.pop(0) if self.replies else []

    def add_torrent(self, url, **kwargs):
        self.added.append((url, kwargs))


def torrent(download_id, *, path=STAGING_PATH, state="stoppedDL", tag=None):
    return {
        "hash": "a" * 40,
        "save_path": path,
        "state": state,
        "tags": tag if tag is not None else f"viewtv-descarga-{download_id}",
    }


@pytest.fixture
def lab(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(processor, "engine", engine)
    with Session(engine) as session:
        profile = Perfil(nombre="Prueba controlada", pin_hash="ficticio")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        ids = []
        for suffix in ("uno", "dos"):
            request = Solicitud(
                perfil_id=profile.id,
                titulo=f"Contenido ficticio {suffix}",
                tipo_medio="pelicula",
                estado="completada",
            )
            session.add(request)
            session.commit()
            session.refresh(request)
            result = ResultadoBusqueda(
                solicitud_id=request.id,
                clave=suffix,
                info_hash=("b" if suffix == "uno" else "c") * 40,
                titulo=f"Contenido de ensayo {suffix}",
                indexador="ficticio",
                magnet_url=f"magnet:?xt=urn:btih:{'b' * 40}",
            )
            session.add(result)
            session.commit()
            session.refresh(result)
            download = Descarga(
                solicitud_id=request.id,
                resultado_busqueda_id=result.id,
                titulo=result.titulo,
                info_hash=result.info_hash,
                estado="seleccionada",
            )
            session.add(download)
            session.commit()
            session.refresh(download)
            ids.append(download.id)
    yield engine, ids
    engine.dispose()


def _saved(engine, download_id):
    with Session(engine) as session:
        return session.get(Descarga, download_id)


def test_only_authorized_id_is_submitted_stopped_in_staging(lab):
    engine, (first, second) = lab
    qbit = FakeQbit([[], [torrent(second)]])
    assert processor.process_one_download(
        "worker-prueba", qbit, allowed_download_id=second, save_path=STAGING_PATH
    )
    assert len(qbit.added) == 1
    url, kwargs = qbit.added[0]
    assert url.startswith("magnet:")
    assert kwargs == {
        "save_path": STAGING_PATH,
        "tags": [f"viewtv-descarga-{second}"],
        "stopped": True,
    }
    assert all(tag == f"viewtv-descarga-{second}" for _, tag in qbit.queries)
    assert _saved(engine, first).estado == "seleccionada"
    assert _saved(engine, first).intentos_envio == 0
    done = _saved(engine, second)
    assert done.estado == "enviada"
    assert done.inicio_estado == "pendiente"
    assert done.qbittorrent_hash == "a" * 40
    assert done.intentos_envio == 1


def test_one_trial_over_real_qbittorrent_http_client_with_fake_transport(lab):
    """Prueba el formulario POST sin acceso a ninguna red ni qBittorrent real."""
    engine, (first, second) = lab
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == "qbittorrent-falso.invalid"
        if request.url.path == "/api/v2/torrents/info":
            assert request.url.params["tag"] == f"viewtv-descarga-{second}"
            if len([r for r in requests if r.url.path.endswith("/info")]) == 1:
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[torrent(second)])
        assert request.method == "POST"
        assert request.url.path == "/api/v2/torrents/add"
        fields = parse_qs(request.content.decode())
        assert fields["urls"][0].startswith("magnet:")
        assert fields["tags"] == [f"viewtv-descarga-{second}"]
        assert fields["savepath"] == [STAGING_PATH]
        assert fields["stopped"] == ["true"]
        assert "paused" not in fields
        return httpx.Response(200, text="Ok.")

    settings = Settings(
        _env_file=None,
        qbittorrent_base_url="http://qbittorrent-falso.invalid:8080",
        qbittorrent_api_key="clave-exclusivamente-ficticia",
    )
    client = QBittorrentClient(
        settings=settings,
        transport=httpx.MockTransport(handler),
    )
    assert processor.process_one_download(
        "worker-prueba", client, allowed_download_id=second, save_path=STAGING_PATH
    )
    assert [r.method for r in requests] == ["GET", "POST", "GET"]
    assert _saved(engine, first).estado == "seleccionada"
    assert _saved(engine, second).estado == "enviada"


def test_unauthorized_id_does_not_claim_other_downloads(lab):
    engine, (first, second) = lab
    qbit = FakeQbit([])
    assert not processor.process_one_download(
        "worker-prueba", qbit, allowed_download_id=second + 100, save_path=STAGING_PATH
    )
    assert qbit.queries == qbit.added == []
    for download_id in (first, second):
        saved = _saved(engine, download_id)
        assert saved.estado == "seleccionada"
        assert saved.locked_by is None
        assert saved.intentos_envio == 0


@pytest.mark.parametrize(
    "bad_path",
    ["", None, "/downloads", r"C:\VIEWTV\media\otra_carpeta"],
)
def test_wrong_staging_is_rejected_before_queue_claim(lab, bad_path):
    engine, (first, second) = lab
    qbit = FakeQbit([])
    with pytest.raises(ValueError, match="staging"):
        processor.process_one_download(
            "worker-prueba", qbit, allowed_download_id=first, save_path=bad_path
        )
    assert qbit.queries == qbit.added == []
    assert _saved(engine, first).locked_by is None
    assert _saved(engine, second).locked_by is None


@pytest.mark.parametrize("bad_id", [0, -1, True, "1", 2**63])
def test_invalid_id_is_rejected_by_queue(lab, bad_id):
    engine, (first, _) = lab
    with Session(engine) as session:
        with pytest.raises(ValueError, match="ID autorizada"):
            claim_next_download(session, "worker-prueba", allowed_download_id=bad_id)
    assert _saved(engine, first).locked_by is None


@pytest.mark.parametrize(
    "variant",
    [
        lambda did: [torrent(did, path=r"D:\Torrent\mal_destino")],
        lambda did: [torrent(did, state="downloading")],
        lambda did: [torrent(did, tag="otro-tag")],
        lambda did: [torrent(did), torrent(did)],
        lambda did: [dict(torrent(did), hash="no-es-un-hash")],
        lambda did: [torrent(did, path=r"C:\VIEWTV\media\otra\..\descargas_temporales")],
    ],
)
def test_untrusted_existing_torrent_fails_closed_without_post(lab, variant):
    engine, (first, second) = lab
    qbit = FakeQbit([variant(second)])
    assert processor.process_one_download(
        "worker-prueba", qbit, allowed_download_id=second, save_path=STAGING_PATH
    )
    assert qbit.added == []
    assert _saved(engine, first).estado == "seleccionada"
    failed = _saved(engine, second)
    assert failed.estado == "fallida"
    assert failed.qbittorrent_hash is None
    assert failed.intentos_envio == 0


def test_reconciles_exact_stopped_torrent_without_duplicate_post(lab):
    engine, (_, second) = lab
    qbit = FakeQbit([[torrent(second)]])
    assert processor.process_one_download(
        "worker-prueba", qbit, allowed_download_id=second, save_path=STAGING_PATH
    )
    assert qbit.added == []
    assert _saved(engine, second).estado == "enviada"
    assert _saved(engine, second).intentos_envio == 0


def test_rejects_incorrect_post_add_path_without_retrying(lab):
    engine, (first, second) = lab
    qbit = FakeQbit([[], [torrent(second, path=r"C:\wrong")]])
    assert processor.process_one_download(
        "worker-prueba", qbit, allowed_download_id=second, save_path=STAGING_PATH
    )
    assert len(qbit.added) == 1
    assert _saved(engine, second).estado == "fallida"
    assert _saved(engine, second).intentos_envio == 1
    assert _saved(engine, first).estado == "seleccionada"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("", None),
        ("0", None),
        ("1", 1),
        (" 12 ", 12),
        ("01", None),
        ("12;13", None),
        ("-2", None),
        ("abc", None),
        ("９", None),
        (str(2**63), None),
        ("9" * 30, None),
    ],
)
def test_worker_requires_single_positive_target_id(value, expected):
    assert worker_main.parse_submission_target(value) == expected


def test_globally_enabled_without_target_never_calls_submission(monkeypatch):
    calls = []

    def forbidden_submission(*args, **kwargs):
        raise AssertionError("Envio sin ID")

    monkeypatch.setattr(worker_main, "SUBMISSION_ENABLED", True)
    monkeypatch.setattr(worker_main, "SUBMISSION_TARGET_ID", None)
    monkeypatch.setattr(worker_main, "START_ENABLED", False)
    monkeypatch.setattr(worker_main, "VERIFICATION_ENABLED", False)
    monkeypatch.setattr(worker_main, "process_one_download", forbidden_submission)
    monkeypatch.setattr(
        worker_main, "process_one_request", lambda worker_id: calls.append("search") or False
    )
    monkeypatch.setattr(worker_main, "monitor_downloads_once", lambda: calls.append("monitor") or 0)
    monkeypatch.setattr(worker_main, "report_worker_status", lambda: calls.append("status"))

    def finish_cycle(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(worker_main.time, "sleep", finish_cycle)
    worker_main.main()
    assert calls == ["search", "monitor", "status"]
