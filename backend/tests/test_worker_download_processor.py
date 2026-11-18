
from datetime import UTC, datetime

import worker.download_processor as processor
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models import Descarga, Perfil, ResultadoBusqueda, Solicitud
from app.qbittorrent import QBittorrentError


def make_engine():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    return test_engine


def add_selected_download(session: Session, *, with_result=True):
    profile = Perfil(nombre="Pruebas", pin_hash="hash-de-prueba")
    session.add(profile)
    session.commit()
    session.refresh(profile)

    request = Solicitud(
        perfil_id=profile.id,
        jellyfin_item_id="jf-download-test",
        titulo="Película de prueba",
        tipo_medio="pelicula",
        anio=2020,
        estado="completada",
    )
    session.add(request)
    session.commit()
    session.refresh(request)

    result = None
    if with_result:
        result = ResultadoBusqueda(
            solicitud_id=request.id,
            clave="a" * 64,
            info_hash="b" * 40,
            titulo="Película de prueba 1080p",
            indexador="Indexador de prueba",
            download_url="https://jackett.test/download/1",
            magnet_url="magnet:?xt=urn:btih:" + "b" * 40,
        )
        session.add(result)
        session.commit()
        session.refresh(result)

    download = Descarga(
        solicitud_id=request.id,
        resultado_busqueda_id=result.id if result else None,
        info_hash=result.info_hash if result else None,
        titulo="Película de prueba 1080p",
        indexador="Indexador de prueba",
        estado="seleccionada",
    )
    session.add(download)
    session.commit()
    session.refresh(download)

    return request.id, download.id


class FakeQBittorrent:
    def __init__(self, responses=None, add_error=None):
        self.responses = list(responses or [])
        self.add_error = add_error
        self.info_calls = []
        self.add_calls = []

    def torrents_info(self, hashes=None, *, tag=None):
        self.info_calls.append({"hashes": hashes, "tag": tag})
        if self.responses:
            return self.responses.pop(0)
        return []

    def add_torrent(self, url, **kwargs):
        self.add_calls.append({"url": url, **kwargs})
        if self.add_error:
            raise self.add_error


def test_existing_torrent_is_reconciled_without_duplicate_submission(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    with Session(test_engine) as session:
        _, download_id = add_selected_download(session)

    qbittorrent = FakeQBittorrent(
        responses=[[{"hash": "c" * 40}]]
    )

    assert processor.process_one_download("worker-test", qbittorrent)

    with Session(test_engine) as session:
        saved = session.get(Descarga, download_id)

        assert saved is not None
        assert saved.estado == "enviada"
        assert saved.qbittorrent_hash == "c" * 40
        assert saved.intentos_envio == 0
        assert saved.locked_by is None

    assert qbittorrent.add_calls == []
    assert qbittorrent.info_calls[0]["tag"] == (
        f"viewtv-descarga-{download_id}"
    )


def test_new_download_uses_magnet_and_unique_tag(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    with Session(test_engine) as session:
        _, download_id = add_selected_download(session)

    qbittorrent = FakeQBittorrent(
        responses=[
            [],
            [{"hash": "b" * 40}],
        ]
    )

    assert processor.process_one_download("worker-test", qbittorrent)

    with Session(test_engine) as session:
        saved = session.get(Descarga, download_id)

        assert saved is not None
        assert saved.estado == "enviada"
        assert saved.qbittorrent_hash == "b" * 40
        assert saved.intentos_envio == 1
        assert saved.locked_by is None

    assert len(qbittorrent.add_calls) == 1
    assert qbittorrent.add_calls[0]["url"].startswith("magnet:")
    assert qbittorrent.add_calls[0]["tags"] == [
        f"viewtv-descarga-{download_id}"
    ]
    assert qbittorrent.add_calls[0]["stopped"] is True


def test_download_failure_releases_lease_and_schedules_retry(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    with Session(test_engine) as session:
        _, download_id = add_selected_download(session)

    qbittorrent = FakeQBittorrent(
        responses=[[]],
        add_error=QBittorrentError("qBittorrent no disponible"),
    )

    assert processor.process_one_download("worker-test", qbittorrent)

    with Session(test_engine) as session:
        saved = session.get(Descarga, download_id)

        assert saved is not None
        assert saved.estado == "seleccionada"
        assert saved.intentos_envio == 1
        assert saved.ultimo_error == "qBittorrent no disponible"
        assert saved.locked_by is None
        assert saved.locked_until is None
        assert saved.disponible_desde > datetime.now(UTC)


def test_missing_selected_result_is_permanent_failure(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    with Session(test_engine) as session:
        request_id, download_id = add_selected_download(
            session,
            with_result=False,
        )

    qbittorrent = FakeQBittorrent()

    assert processor.process_one_download("worker-test", qbittorrent)

    with Session(test_engine) as session:
        saved = session.get(Descarga, download_id)
        request = session.get(Solicitud, request_id)

        assert saved is not None
        assert request is not None
        assert saved.estado == "fallida"
        assert saved.intentos_envio == 0
        assert saved.locked_by is None
        assert request.estado == "esperando_seleccion"

    assert qbittorrent.info_calls == []
    assert qbittorrent.add_calls == []


def test_empty_download_queue_does_not_call_qbittorrent(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    qbittorrent = FakeQBittorrent()

    assert not processor.process_one_download("worker-test", qbittorrent)
    assert qbittorrent.info_calls == []
    assert qbittorrent.add_calls == []


def test_ambiguous_add_response_reconciles_registered_torrent(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    with Session(test_engine) as session:
        _, download_id = add_selected_download(session)

    qbittorrent = FakeQBittorrent(
        responses=[
            [],
            [{"hash": "d" * 40}],
        ],
        add_error=QBittorrentError(
            "qBittorrent no confirmó el alta del torrent."
        ),
    )

    assert processor.process_one_download("worker-test", qbittorrent)

    with Session(test_engine) as session:
        saved = session.get(Descarga, download_id)

        assert saved is not None
        assert saved.estado == "enviada"
        assert saved.qbittorrent_hash == "d" * 40
        assert saved.intentos_envio == 1
        assert saved.locked_by is None

    assert len(qbittorrent.add_calls) == 1
    assert qbittorrent.add_calls[0]["stopped"] is True
    assert len(qbittorrent.info_calls) == 2
    assert all(
        call["tag"] == f"viewtv-descarga-{download_id}"
        for call in qbittorrent.info_calls
    )
