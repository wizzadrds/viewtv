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
