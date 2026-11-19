"""Pruebas del ejecutor conservador de inicios."""

import worker.download_starter as starter
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models import Descarga, Perfil, Solicitud
from app.qbittorrent import QBittorrentError


class FakeQBittorrent:
    def __init__(self, torrents):
        self.torrents = torrents
        self.tags = []
        self.started = []
        self.error = None

    def torrents_info(self, hashes=None, *, tag=None):
        self.tags.append(tag)
        return self.torrents

    def start_torrent(self, torrent_hash):
        self.started.append(torrent_hash)
        if self.error:
            raise self.error


def setup_download(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(starter, "engine", engine)

    with Session(engine) as session:
        profile = Perfil(
            nombre="Pruebas inicio",
            pin_hash="hash-de-prueba",
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)

        request = Solicitud(
            perfil_id=profile.id,
            titulo="Prueba",
            tipo_medio="pelicula",
            estado="completada",
        )
        session.add(request)
        session.commit()
        session.refresh(request)

        download = Descarga(
            solicitud_id=request.id,
            titulo="Prueba",
            estado="enviada",
            qbittorrent_hash="a" * 40,
            inicio_estado="pendiente",
        )
        session.add(download)
        session.commit()
        session.refresh(download)
        return engine, download.id


def test_first_start_uses_only_own_torrent(monkeypatch):
    engine, download_id = setup_download(monkeypatch)
    client = FakeQBittorrent([
        {
            "hash": "a" * 40,
            "state": "stoppedDL",
            "save_path": r"C:\VIEWTV\media\descargas_temporales",
        },
    ])

    assert starter.process_one_start("starter-a", client)

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_estado == "iniciada"

    assert client.tags == [f"viewtv-descarga-{download_id}"]
    assert client.started == ["a" * 40]
    engine.dispose()


def test_foreign_torrent_is_never_started(monkeypatch):
    engine, download_id = setup_download(monkeypatch)
    client = FakeQBittorrent([
        {
            "hash": "b" * 40,
            "state": "stoppedDL",
            "save_path": r"C:\VIEWTV\media\descargas_temporales",
        },
    ])

    assert starter.process_one_start("starter-a", client)

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_estado == "pendiente"

    assert client.started == []
    engine.dispose()


def test_already_running_is_reconciled_without_post(monkeypatch):
    engine, download_id = setup_download(monkeypatch)
    client = FakeQBittorrent([
        {
            "hash": "a" * 40,
            "state": "downloading",
            "save_path": r"C:\VIEWTV\media\descargas_temporales",
        },
    ])

    assert starter.process_one_start("starter-a", client)

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_estado == "iniciada"

    assert client.started == []
    engine.dispose()


def test_ambiguous_start_is_not_repeated(monkeypatch):
    engine, download_id = setup_download(monkeypatch)
    client = FakeQBittorrent([
        {
            "hash": "a" * 40,
            "state": "stoppedDL",
            "save_path": r"C:\VIEWTV\media\descargas_temporales",
        },
    ])
    client.error = QBittorrentError("Respuesta perdida")

    assert starter.process_one_start("starter-a", client)
    assert client.started == ["a" * 40]

    # Simula que ya pasó el plazo de reintento.
    from datetime import UTC, datetime, timedelta

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        download.inicio_disponible_desde = (
            datetime.now(UTC) - timedelta(seconds=1)
        )
        session.add(download)
        session.commit()

    client.error = None
    assert starter.process_one_start("starter-b", client)

    # Nunca se envía una segunda orden de inicio.
    assert client.started == ["a" * 40]

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_estado == "requiere_revision"
        assert download.inicio_intentos == 2
        assert download.inicio_estado == "requiere_revision"

    engine.dispose()


def test_empty_start_queue_does_not_call_qbittorrent(monkeypatch):
    engine, download_id = setup_download(monkeypatch)

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        download.inicio_estado = "no_requerido"
        session.add(download)
        session.commit()

    client = FakeQBittorrent([])
    assert not starter.process_one_start("starter-a", client)
    assert client.tags == []
    assert client.started == []
    engine.dispose()


def test_torrent_outside_authorized_folder_is_not_started(monkeypatch):
    engine, download_id = setup_download(monkeypatch)

    client = FakeQBittorrent([
        {
            "hash": "a" * 40,
            "state": "stoppedDL",
            "save_path": r"D:\NoAutorizado",
        }
    ])

    assert starter.process_one_start("starter-a", client)

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_estado == "pendiente"
        assert download.inicio_intentos == 1

    assert client.started == []
    engine.dispose()


def test_ambiguous_start_recovers_when_torrent_is_running(
    monkeypatch
):
    """Una respuesta perdida no provoca dos órdenes de inicio."""
    from datetime import UTC, datetime, timedelta

    engine, download_id = setup_download(monkeypatch)

    client = FakeQBittorrent([
        {
            "hash": "a" * 40,
            "state": "stoppedDL",
            "save_path": (
                r"C:\VIEWTV\media\descargas_temporales"
            ),
        }
    ])
    client.error = QBittorrentError("Respuesta perdida")

    assert starter.process_one_start("starter-a", client)
    assert client.started == ["a" * 40]

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_estado == "pendiente"
        assert download.inicio_intentos == 1

        download.inicio_disponible_desde = (
            datetime.now(UTC) - timedelta(seconds=1)
        )
        session.add(download)
        session.commit()

    # qBittorrent sí recibió la primera orden.
    client.error = None
    client.torrents = [
        {
            "hash": "a" * 40,
            "state": "downloading",
            "save_path": (
                r"C:\VIEWTV\media\descargas_temporales"
            ),
        }
    ]

    assert starter.process_one_start("starter-b", client)

    with Session(engine) as session:
        download = session.get(Descarga, download_id)

        assert download.inicio_estado == "iniciada"
        assert download.inicio_intentos == 2
        assert download.inicio_locked_by is None

    # Solo se envió la orden inicial.
    assert client.started == ["a" * 40]

    engine.dispose()
