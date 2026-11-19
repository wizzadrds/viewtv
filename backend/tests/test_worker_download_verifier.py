"""Pruebas del coordinador de verificaciones de descargas."""

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel
from worker import download_verifier

from app.models import Descarga, Perfil, Solicitud
from app.qbittorrent import QBittorrentError


@pytest.fixture
def verification_engine(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'verification.db'}"
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(download_verifier, "engine", engine)

    yield engine

    engine.dispose()


def create_completed_download(engine, *, verification="pendiente"):
    with Session(engine) as session:
        perfil = Perfil(nombre="Test", pin_hash="hash")
        session.add(perfil)
        session.flush()

        solicitud = Solicitud(
            perfil_id=perfil.id,
            jellyfin_item_id="jf-test",
            titulo="Película de prueba",
        )
        session.add(solicitud)
        session.flush()

        descarga = Descarga(
            solicitud_id=solicitud.id,
            titulo="Película de prueba",
            qbittorrent_hash="a" * 40,
            estado="completada",
            progreso=1.0,
            estado_verificacion=verification,
        )
        session.add(descarga)
        session.commit()

        return descarga.id


def test_verifies_pending_download(
    verification_engine, monkeypatch, tmp_path
):
    download_id = create_completed_download(verification_engine)

    calls = []

    def fake_verify(client, torrent_hash, media_root):
        calls.append(torrent_hash)
        return [tmp_path / "pelicula.mkv"]

    monkeypatch.setattr(
        download_verifier, "verify_completed_files", fake_verify
    )

    updated = download_verifier.verify_pending_downloads_once(
        client=object(), media_root=tmp_path
    )

    assert updated == 1
    assert calls == ["a" * 40]

    with Session(verification_engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado_verificacion == "verificada"
        assert descarga.verificada_en is not None


def test_skips_already_verified_download(
    verification_engine, monkeypatch, tmp_path
):
    create_completed_download(
        verification_engine, verification="verificada"
    )

    calls = []

    def fake_verify(client, torrent_hash, media_root):
        calls.append(torrent_hash)

    monkeypatch.setattr(
        download_verifier, "verify_completed_files", fake_verify
    )

    updated = download_verifier.verify_pending_downloads_once(
        client=object(), media_root=tmp_path
    )

    assert updated == 0
    assert calls == []


def test_communication_error_keeps_pending(
    verification_engine, monkeypatch, tmp_path
):
    download_id = create_completed_download(verification_engine)

    def fake_verify(client, torrent_hash, media_root):
        raise QBittorrentError("Error simulado")

    monkeypatch.setattr(
        download_verifier, "verify_completed_files", fake_verify
    )

    updated = download_verifier.verify_pending_downloads_once(
        client=object(), media_root=tmp_path
    )

    assert updated == 0

    with Session(verification_engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado_verificacion == "pendiente"

def test_invalid_files_are_recorded_as_failed(
    verification_engine, monkeypatch, tmp_path
):
    from worker.file_validator import InvalidTorrentFiles

    download_id = create_completed_download(verification_engine)

    def fake_verify(client, torrent_hash, media_root):
        raise InvalidTorrentFiles("Archivo incompleto")

    monkeypatch.setattr(
        download_verifier, "verify_completed_files", fake_verify
    )

    assert download_verifier.verify_pending_downloads_once(
        client=object(), media_root=tmp_path
    ) == 1

    with Session(verification_engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado_verificacion == "fallida"
        assert descarga.error_verificacion == "Archivo incompleto"
        assert descarga.verificada_en is None


def test_failed_verification_is_not_reprocessed(
    verification_engine, monkeypatch, tmp_path
):
    create_completed_download(
        verification_engine, verification="fallida"
    )

    calls = []

    def fake_verify(client, torrent_hash, media_root):
        calls.append(torrent_hash)

    monkeypatch.setattr(
        download_verifier, "verify_completed_files", fake_verify
    )

    assert download_verifier.verify_pending_downloads_once(
        client=object(), media_root=tmp_path
    ) == 0

    assert calls == []


def test_incomplete_download_is_not_verified(
    verification_engine, monkeypatch, tmp_path
):
    download_id = create_completed_download(verification_engine)

    with Session(verification_engine) as session:
        descarga = session.get(Descarga, download_id)
        descarga.estado = "descargando"
        descarga.progreso = 0.5
        session.add(descarga)
        session.commit()

    calls = []

    def fake_verify(client, torrent_hash, media_root):
        calls.append(torrent_hash)

    monkeypatch.setattr(
        download_verifier, "verify_completed_files", fake_verify
    )

    assert download_verifier.verify_pending_downloads_once(
        client=object(), media_root=tmp_path
    ) == 0

    assert calls == []

def test_process_one_verification_success(
    verification_engine, monkeypatch, tmp_path
):
    download_id = create_completed_download(verification_engine)
    calls = []

    def fake_verify(client, torrent_hash, media_root):
        calls.append(torrent_hash)
        return [tmp_path / "pelicula.mkv"]

    monkeypatch.setattr(
        download_verifier, "verify_completed_files", fake_verify
    )

    assert download_verifier.process_one_verification(
        "worker-test-1", client=object(), media_root=tmp_path
    )
    assert calls == ["a" * 40]

    with Session(verification_engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado_verificacion == "verificada"
        assert descarga.verificada_en is not None
        assert descarga.verificacion_locked_by is None
        assert descarga.verificacion_locked_until is None


def test_process_one_verification_defers_qbittorrent_error(
    verification_engine, monkeypatch, tmp_path
):
    download_id = create_completed_download(verification_engine)

    def fake_verify(client, torrent_hash, media_root):
        raise QBittorrentError("Sin comunicación")

    monkeypatch.setattr(
        download_verifier, "verify_completed_files", fake_verify
    )

    assert download_verifier.process_one_verification(
        "worker-test-2", client=object(), media_root=tmp_path
    )

    with Session(verification_engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado_verificacion == "pendiente"
        assert descarga.verificacion_locked_by is None
        assert descarga.verificacion_locked_until is None
        assert descarga.verificacion_disponible_desde is not None

    assert not download_verifier.process_one_verification(
        "worker-test-3", client=object(), media_root=tmp_path
    )


def test_process_one_verification_records_invalid_files(
    verification_engine, monkeypatch, tmp_path
):
    from worker.file_validator import InvalidTorrentFiles

    download_id = create_completed_download(verification_engine)

    def fake_verify(client, torrent_hash, media_root):
        raise InvalidTorrentFiles("Archivo incompleto")

    monkeypatch.setattr(
        download_verifier, "verify_completed_files", fake_verify
    )

    assert download_verifier.process_one_verification(
        "worker-test-4", client=object(), media_root=tmp_path
    )

    with Session(verification_engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado_verificacion == "fallida"
        assert descarga.error_verificacion == "Archivo incompleto"
        assert descarga.verificacion_locked_by is None


def test_process_one_verification_skips_verified(
    verification_engine, monkeypatch, tmp_path
):
    create_completed_download(
        verification_engine, verification="verificada"
    )

    calls = []

    def fake_verify(client, torrent_hash, media_root):
        calls.append(torrent_hash)

    monkeypatch.setattr(
        download_verifier, "verify_completed_files", fake_verify
    )

    assert not download_verifier.process_one_verification(
        "worker-test-5", client=object(), media_root=tmp_path
    )
    assert calls == []


def test_verification_worker_ids_are_unique():
    first = download_verifier.new_verification_worker_id()
    second = download_verifier.new_verification_worker_id()

    assert first != second
    assert first.startswith("verification-")
    assert second.startswith("verification-")
    assert len(first) <= 128
    assert len(second) <= 128

@pytest.mark.parametrize(
    "outcome",
    ["success", "invalid", "communication"],
)
def test_process_one_verification_lost_lease(
    verification_engine, monkeypatch, tmp_path, outcome
):
    from worker.file_validator import InvalidTorrentFiles

    download_id = create_completed_download(verification_engine)

    class LostHeartbeat:
        def __init__(self, engine, download_id, worker_id):
            self.lease_lost = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    def fake_verify(client, torrent_hash, media_root):
        if outcome == "invalid":
            raise InvalidTorrentFiles("Archivo incompleto")
        if outcome == "communication":
            raise QBittorrentError("Sin comunicación")
        return [tmp_path / "pelicula.mkv"]

    monkeypatch.setattr(
        download_verifier,
        "VerificationHeartbeat",
        LostHeartbeat,
    )
    monkeypatch.setattr(
        download_verifier,
        "verify_completed_files",
        fake_verify,
    )

    assert download_verifier.process_one_verification(
        "worker-lost-lease",
        client=object(),
        media_root=tmp_path,
    )

    with Session(verification_engine) as session:
        descarga = session.get(Descarga, download_id)

        assert descarga.estado_verificacion == "pendiente"
        assert descarga.verificada_en is None
        assert descarga.error_verificacion is None

        # La reclamación no se altera desde el worker
        # que ha detectado la pérdida de autorización.
        assert (
            descarga.verificacion_locked_by
            == "worker-lost-lease"
        )
        assert descarga.verificacion_locked_until is not None
        assert descarga.verificacion_disponible_desde is None

def test_verification_heartbeat_renews_real_sqlite(
    verification_engine, monkeypatch
):
    from datetime import UTC
    from threading import Event

    from worker import verification_heartbeat

    from app.queue import (
        claim_next_verification,
        renew_verification_lease,
    )

    download_id = create_completed_download(verification_engine)

    with Session(verification_engine) as session:
        claimed = claim_next_verification(
            session,
            "worker-heartbeat-real",
            lease_seconds=3,
        )
        assert claimed is not None
        original_expiration = claimed.verificacion_locked_until

    renewed = Event()
    original_renew = renew_verification_lease

    def tracked_renew(session, *args, **kwargs):
        result = original_renew(session, *args, **kwargs)
        if result:
            renewed.set()
        return result

    monkeypatch.setattr(
        verification_heartbeat,
        "renew_verification_lease",
        tracked_renew,
    )

    with verification_heartbeat.VerificationHeartbeat(
        verification_engine,
        download_id,
        "worker-heartbeat-real",
        lease_seconds=3,
        interval_seconds=0.02,
    ) as heartbeat:
        assert renewed.wait(timeout=2)

    assert not heartbeat.lease_lost
    assert not heartbeat._thread.is_alive()

    with Session(verification_engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.verificacion_locked_by == "worker-heartbeat-real"
        assert descarga.verificacion_heartbeat is not None

        actual = descarga.verificacion_locked_until.replace(tzinfo=UTC)
        anterior = original_expiration.replace(tzinfo=UTC)
        assert actual > anterior

def test_process_one_verification_unexpected_error(
    verification_engine, monkeypatch, tmp_path
):
    download_id = create_completed_download(verification_engine)

    def fake_verify(client, torrent_hash, media_root):
        raise RuntimeError("Error inesperado de prueba")

    monkeypatch.setattr(
        download_verifier, "verify_completed_files", fake_verify
    )

    assert download_verifier.process_one_verification(
        "worker-unexpected-error",
        client=object(),
        media_root=tmp_path,
    )

    with Session(verification_engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado_verificacion == "pendiente"
        assert descarga.verificacion_locked_by is None
        assert descarga.verificacion_locked_until is None
        assert descarga.verificacion_disponible_desde is not None
        assert descarga.verificada_en is None


def test_process_one_verification_stops_heartbeat_before_finish(
    verification_engine, monkeypatch, tmp_path
):
    from app import queue

    download_id = create_completed_download(verification_engine)
    events = []

    class TrackingHeartbeat:
        def __init__(self, engine, download_id, worker_id):
            self.lease_lost = False

        def __enter__(self):
            events.append("heartbeat_started")
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            events.append("heartbeat_stopped")
            return False

    original_finish = queue.finish_claimed_verification

    def tracked_finish(*args, **kwargs):
        events.append("finish")
        return original_finish(*args, **kwargs)

    def fake_verify(client, torrent_hash, media_root):
        events.append("verify")
        return [tmp_path / "pelicula.mkv"]

    monkeypatch.setattr(
        download_verifier,
        "VerificationHeartbeat",
        TrackingHeartbeat,
    )
    monkeypatch.setattr(
        download_verifier, "verify_completed_files", fake_verify
    )
    monkeypatch.setattr(
        queue, "finish_claimed_verification", tracked_finish
    )

    assert download_verifier.process_one_verification(
        "worker-heartbeat-order",
        client=object(),
        media_root=tmp_path,
    )

    assert events == [
        "heartbeat_started",
        "verify",
        "heartbeat_stopped",
        "finish",
    ]

    with Session(verification_engine) as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado_verificacion == "verificada"
        assert descarga.verificacion_locked_by is None
