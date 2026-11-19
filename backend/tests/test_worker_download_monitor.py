"""Pruebas del intérprete de qBittorrent."""

from worker.download_monitor import interpret_torrent


def test_stopped_without_metadata():
    result = interpret_torrent({
        "state": "stoppedDL",
        "progress": 0,
        "total_size": -1,
    })
    assert result is not None
    assert result.estado == "pausada"
    assert result.progreso == 0
    assert result.tamano_bytes is None


def test_downloading():
    result = interpret_torrent({
        "state": "downloading",
        "progress": 0.45,
        "total_size": 1000,
    })
    assert result is not None
    assert result.estado == "descargando"
    assert result.progreso == 0.45
    assert result.tamano_bytes == 1000


def test_completed():
    result = interpret_torrent({
        "state": "stoppedUP",
        "progress": 1,
        "total_size": 1000,
    })
    assert result is not None
    assert result.estado == "completada"


def test_unknown_state():
    assert interpret_torrent({
        "state": "unknown",
        "progress": 0.5,
    }) is None


def test_invalid_progress():
    assert interpret_torrent({
        "state": "downloading",
        "progress": 1.5,
    }) is None


def test_missing_files():
    assert interpret_torrent({
        "state": "missingFiles",
        "progress": 1,
    }) is None



def make_monitor_database(monkeypatch):
    import worker.download_monitor as monitor
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine

    from app.models import Descarga, Perfil, Solicitud

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(monitor, "engine", engine)

    with Session(engine) as session:
        perfil = Perfil(
            nombre="Monitor prueba",
            pin_hash="hash-de-prueba",
        )
        session.add(perfil)
        session.commit()
        session.refresh(perfil)

        solicitud = Solicitud(
            perfil_id=perfil.id,
            jellyfin_item_id="jf-monitor-test",
            titulo="Contenido de prueba",
        )
        session.add(solicitud)
        session.commit()
        session.refresh(solicitud)

        descarga = Descarga(
            solicitud_id=solicitud.id,
            titulo="Torrent de prueba",
            qbittorrent_hash="a" * 40,
            estado="enviada",
        )
        session.add(descarga)
        session.commit()
        session.refresh(descarga)
        download_id = descarga.id

    return engine, download_id


class FakeMonitorClient:
    def __init__(self, torrents=None, error=None):
        self.torrents = torrents or []
        self.error = error
        self.calls = []

    def torrents_info(self, hashes=None, *, tag=None):
        self.calls.append(hashes)
        if self.error is not None:
            raise self.error
        return self.torrents


def test_monitor_syncs_stopped_download(monkeypatch):
    import worker.download_monitor as monitor
    from sqlmodel import Session

    from app.models import Descarga

    engine, download_id = make_monitor_database(monkeypatch)
    client = FakeMonitorClient([{
        "hash": "a" * 40,
        "state": "stoppedDL",
        "progress": 0,
        "total_size": -1,
    }])

    assert monitor.monitor_downloads_once(client) == 1
    assert client.calls == [["a" * 40]]

    with Session(engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado == "pausada"
        assert descarga.progreso == 0
        assert descarga.tamano_bytes is None


def test_monitor_ignores_different_hash(monkeypatch):
    import worker.download_monitor as monitor
    from sqlmodel import Session

    from app.models import Descarga

    engine, download_id = make_monitor_database(monkeypatch)
    client = FakeMonitorClient([{
        "hash": "b" * 40,
        "state": "downloading",
        "progress": 0.8,
        "total_size": 1000,
    }])

    assert monitor.monitor_downloads_once(client) == 0

    with Session(engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado == "enviada"
        assert descarga.progreso == 0


def test_monitor_preserves_state_on_connection_error(monkeypatch):
    import worker.download_monitor as monitor
    from sqlmodel import Session

    from app.models import Descarga
    from app.qbittorrent import QBittorrentError

    engine, download_id = make_monitor_database(monkeypatch)
    client = FakeMonitorClient(
        error=QBittorrentError("Conexion no disponible"),
    )

    assert monitor.monitor_downloads_once(client) == 0

    with Session(engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado == "enviada"
        assert descarga.progreso == 0


def test_monitor_tracks_partial_and_completed_download(monkeypatch):
    import worker.download_monitor as monitor
    from sqlmodel import Session

    from app.models import Descarga

    engine, download_id = make_monitor_database(monkeypatch)

    client = FakeMonitorClient([{
        "hash": "a" * 40,
        "state": "downloading",
        "progress": 0.45,
        "total_size": 1000,
    }])

    assert monitor.monitor_downloads_once(client) == 1

    with Session(engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado == "descargando"
        assert descarga.progreso == 0.45
        assert descarga.tamano_bytes == 1000

    client.torrents = [{
        "hash": "a" * 40,
        "state": "stoppedUP",
        "progress": 1,
        "total_size": 1000,
    }]

    assert monitor.monitor_downloads_once(client) == 1

    with Session(engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado == "completada"
        assert descarga.progreso == 1
        assert descarga.tamano_bytes == 1000

    # No modificar una descarga ya completada.
    client.torrents[0]["state"] = "stoppedDL"
    client.torrents[0]["progress"] = 0.5

    assert monitor.monitor_downloads_once(client) == 0

    with Session(engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado == "completada"
        assert descarga.progreso == 1



def test_inicio_reciente_no_se_confunde_con_pausa(monkeypatch):
    from datetime import UTC, datetime

    import worker.download_monitor as monitor
    from sqlmodel import Session

    from app.models import Descarga

    engine, download_id = make_monitor_database(monkeypatch)
    with Session(engine) as session:
        descarga = session.get(Descarga, download_id)
        descarga.inicio_estado = "iniciada"
        descarga.actualizado_en = datetime.now(UTC)
        session.add(descarga)
        session.commit()

    client = FakeMonitorClient([{
        "hash": "a" * 40,
        "state": "stoppedDL",
        "progress": 0,
        "total_size": 1000,
    }])
    assert monitor.monitor_downloads_once(client) == 0

    with Session(engine) as session:
        assert session.get(Descarga, download_id).estado == "enviada"
    engine.dispose()


def test_inicio_sin_actividad_tras_gracia_muestra_pausa(monkeypatch):
    from datetime import UTC, datetime, timedelta

    import worker.download_monitor as monitor
    from sqlmodel import Session

    from app.models import Descarga

    engine, download_id = make_monitor_database(monkeypatch)
    with Session(engine) as session:
        descarga = session.get(Descarga, download_id)
        descarga.inicio_estado = "iniciada"
        descarga.actualizado_en = datetime.now(UTC) - timedelta(minutes=3)
        session.add(descarga)
        session.commit()

    client = FakeMonitorClient([{
        "hash": "a" * 40,
        "state": "stoppedDL",
        "progress": 0,
        "total_size": 1000,
    }])
    assert monitor.monitor_downloads_once(client) == 1

    with Session(engine) as session:
        assert session.get(Descarga, download_id).estado == "pausada"
    engine.dispose()


def test_pausa_manual_despues_de_actividad_no_se_oculta(monkeypatch):
    from datetime import UTC, datetime

    import worker.download_monitor as monitor
    from sqlmodel import Session

    from app.models import Descarga

    engine, download_id = make_monitor_database(monkeypatch)
    with Session(engine) as session:
        descarga = session.get(Descarga, download_id)
        descarga.inicio_estado = "iniciada"
        descarga.estado = "descargando"
        descarga.progreso = 0.3
        descarga.actualizado_en = datetime.now(UTC)
        session.add(descarga)
        session.commit()

    client = FakeMonitorClient([{
        "hash": "a" * 40,
        "state": "stoppedDL",
        "progress": 0.3,
        "total_size": 1000,
    }])
    assert monitor.monitor_downloads_once(client) == 1

    with Session(engine) as session:
        assert session.get(Descarga, download_id).estado == "pausada"
    engine.dispose()
