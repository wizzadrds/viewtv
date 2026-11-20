"""Inicio de una sola descarga autorizada con SQLite y qBittorrent ficticios.

Solo se emplea SQLite en memoria y httpx.MockTransport sin acceso a red.
"""

from urllib.parse import parse_qs

import httpx
import pytest
import worker.download_starter as starter
import worker.main as worker_main
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from worker.download_processor import STAGING_PATH

from app.config import Settings
from app.download_start_queue import claim_next_start
from app.models import Descarga, Perfil, Solicitud
from app.qbittorrent import QBittorrentClient


class FakeQbit:
    def __init__(self, info):
        self.info = info
        self.lookups = []
        self.started = []

    def torrents_info(self, hashes=None, *, tag=None):
        self.lookups.append(tag)
        return self.info

    def start_torrent(self, torrent_hash):
        self.started.append(torrent_hash)


def torrent(
    download_id, *, torrent_hash="b" * 40, state="stoppedDL", save_path=STAGING_PATH, tags=None
):
    return {
        "hash": torrent_hash,
        "state": state,
        "save_path": save_path,
        "tags": f"viewtv-descarga-{download_id}" if tags is None else tags,
    }


@pytest.fixture
def lab(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(starter, "engine", engine)
    with Session(engine) as session:
        profile = Perfil(nombre="Inicio ficticio", pin_hash="hash-ficticio")
        session.add(profile)
        session.commit()
        session.refresh(profile)
        ids = []
        for name, letter in (("primera", "a"), ("segunda", "b")):
            request = Solicitud(
                perfil_id=profile.id,
                titulo=f"Prueba {name}",
                tipo_medio="pelicula",
                estado="completada",
            )
            session.add(request)
            session.commit()
            session.refresh(request)
            download = Descarga(
                solicitud_id=request.id,
                titulo=f"Prueba {name}",
                estado="enviada",
                qbittorrent_hash=letter * 40,
                inicio_estado="pendiente",
            )
            session.add(download)
            session.commit()
            session.refresh(download)
            ids.append(download.id)
    yield engine, ids
    engine.dispose()


def saved(engine, download_id):
    with Session(engine) as session:
        return session.get(Descarga, download_id)


def test_starts_only_specifically_allowed_download(lab):
    engine, (first, second) = lab
    qbit = FakeQbit([torrent(second)])
    assert starter.process_one_start(
        "worker-prueba",
        qbit,
        allowed_download_id=second,
        expected_save_path=STAGING_PATH,
    )
    assert qbit.started == ["b" * 40]
    assert qbit.lookups == [f"viewtv-descarga-{second}"]
    assert saved(engine, first).inicio_estado == "pendiente"
    assert saved(engine, first).inicio_intentos == 0
    assert saved(engine, first).inicio_locked_by is None
    assert saved(engine, second).inicio_estado == "iniciada"
    assert saved(engine, second).inicio_intentos == 1


def test_wrong_target_id_does_not_reclaim_another_start(lab):
    engine, (first, second) = lab
    qbit = FakeQbit([])
    assert not starter.process_one_start(
        "worker-prueba",
        qbit,
        allowed_download_id=second + 999,
        expected_save_path=STAGING_PATH,
    )
    assert qbit.lookups == qbit.started == []
    assert saved(engine, first).inicio_intentos == 0
    assert saved(engine, second).inicio_intentos == 0


@pytest.mark.parametrize("bad_path", [None, "", "/downloads", r"C:\VIEWTV\media\otra"])
def test_wrong_staging_denied_before_start_claim(lab, bad_path):
    engine, (first, second) = lab
    with pytest.raises(ValueError, match="ruta"):
        starter.process_one_start(
            "worker-prueba",
            FakeQbit([]),
            allowed_download_id=second,
            expected_save_path=bad_path,
        )
    assert saved(engine, first).inicio_intentos == 0
    assert saved(engine, second).inicio_intentos == 0


@pytest.mark.parametrize("bad_id", [0, True, -1, "2", 2**63])
def test_start_queue_rejects_invalid_target_without_claim(lab, bad_id):
    engine, (first, second) = lab
    with Session(engine) as session:
        with pytest.raises(ValueError, match="ID"):
            claim_next_start(session, "worker-prueba", allowed_download_id=bad_id)
    assert saved(engine, first).inicio_intentos == 0
    assert saved(engine, second).inicio_intentos == 0


@pytest.mark.parametrize(
    "bad_info",
    [
        lambda did: [torrent(did, tags="otra-etiqueta")],
        lambda did: [torrent(did, save_path=r"D:\NoAutorizado")],
        lambda did: [torrent(did, save_path=r"C:\VIEWTV\media\..\descargas_temporales")],
        lambda did: [torrent(did, torrent_hash="c" * 40)],
        lambda did: [torrent(did), torrent(did)],
        lambda did: [torrent(did, state="stoppedUnknown")],
    ],
)
def test_start_rejects_unexpected_identity_path_or_state(lab, bad_info):
    engine, (first, second) = lab
    qbit = FakeQbit(bad_info(second))
    assert starter.process_one_start(
        "worker-prueba",
        qbit,
        allowed_download_id=second,
        expected_save_path=STAGING_PATH,
    )
    assert qbit.started == []
    assert saved(engine, first).inicio_intentos == 0
    assert saved(engine, second).inicio_estado == "pendiente"


def test_already_running_exactly_identified_start_is_reconciled(lab):
    engine, (first, second) = lab
    qbit = FakeQbit([torrent(second, state="downloading")])
    assert starter.process_one_start(
        "worker-prueba",
        qbit,
        allowed_download_id=second,
        expected_save_path=STAGING_PATH,
    )
    assert qbit.started == []
    assert saved(engine, first).inicio_estado == "pendiente"
    assert saved(engine, second).inicio_estado == "iniciada"


def test_http_mock_sends_only_target_hash_start_command(lab):
    engine, (first, second) = lab
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == "qbit-simulado.invalid"
        if request.method == "GET":
            assert request.url.path == "/api/v2/torrents/info"
            assert request.url.params["tag"] == f"viewtv-descarga-{second}"
            return httpx.Response(200, json=[torrent(second)])
        assert request.method == "POST"
        assert request.url.path == "/api/v2/torrents/start"
        fields = parse_qs(request.content.decode())
        assert fields == {"hashes": ["b" * 40]}
        return httpx.Response(200, text="Ok.")

    settings = Settings(
        _env_file=None,
        qbittorrent_base_url="http://qbit-simulado.invalid:8080",
        qbittorrent_api_key="clave-ficticia",
    )
    client = QBittorrentClient(
        settings=settings,
        transport=httpx.MockTransport(handler),
    )
    assert starter.process_one_start(
        "worker-prueba",
        client,
        allowed_download_id=second,
        expected_save_path=STAGING_PATH,
    )
    assert [r.method for r in requests] == ["GET", "POST"]
    assert saved(engine, first).inicio_estado == "pendiente"
    assert saved(engine, second).inicio_estado == "iniciada"


def test_worker_with_start_flag_but_no_target_does_not_start(monkeypatch):
    calls = []

    def forbidden_start(*args, **kwargs):
        raise AssertionError("Orden de inicio sin ID individual")

    monkeypatch.setattr(worker_main, "SUBMISSION_ENABLED", False)
    monkeypatch.setattr(worker_main, "START_ENABLED", True)
    monkeypatch.setattr(worker_main, "SUBMISSION_TARGET_ID", None)
    monkeypatch.setattr(worker_main, "VERIFICATION_ENABLED", False)
    monkeypatch.setattr(worker_main, "process_one_start", forbidden_start)
    monkeypatch.setattr(
        worker_main, "process_one_request", lambda wid: calls.append("busca") or False
    )
    monkeypatch.setattr(
        worker_main, "monitor_downloads_once", lambda: calls.append("supervisa") or 0
    )
    monkeypatch.setattr(worker_main, "report_worker_status", lambda: calls.append("estado"))

    def end(_duration):
        raise KeyboardInterrupt

    monkeypatch.setattr(worker_main.time, "sleep", end)
    worker_main.main()
    assert calls == ["busca", "supervisa", "estado"]
