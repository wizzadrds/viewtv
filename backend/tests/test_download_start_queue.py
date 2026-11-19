"""Pruebas aisladas de la cola de inicio de torrents."""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, SQLModel, create_engine

from app.download_start_queue import (
    claim_next_start,
    confirm_start_command,
    defer_start_command,
)
from app.models import Descarga, Perfil, Solicitud


def setup_download(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'start-queue.sqlite3'}"
    )
    SQLModel.metadata.create_all(engine)

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


def test_exclusive_claim_and_expired_lease(tmp_path):
    engine, download_id = setup_download(tmp_path)
    now = datetime.now(UTC)

    with Session(engine) as session:
        first = claim_next_start(session, "worker-a", now=now)
        assert first is not None
        assert first.id == download_id
        assert first.inicio_intentos == 1

    with Session(engine) as session:
        assert claim_next_start(
            session, "worker-b", now=now
        ) is None

    with Session(engine) as session:
        reclaimed = claim_next_start(
            session,
            "worker-b",
            now=now + timedelta(seconds=91),
        )
        assert reclaimed is not None
        assert reclaimed.inicio_intentos == 2


def test_confirmation_requires_owner_and_valid_lease(tmp_path):
    engine, download_id = setup_download(tmp_path)
    now = datetime.now(UTC)

    with Session(engine) as session:
        assert claim_next_start(session, "owner", now=now)

    with Session(engine) as session:
        assert not confirm_start_command(
            session, download_id, "other", now=now
        )
        assert confirm_start_command(
            session, download_id, "owner", now=now
        )

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_estado == "iniciada"
        assert download.inicio_locked_by is None
        assert claim_next_start(session, "other", now=now) is None


def test_retry_waits_and_preserves_torrent(tmp_path):
    engine, download_id = setup_download(tmp_path)
    now = datetime.now(UTC)

    with Session(engine) as session:
        assert claim_next_start(session, "owner", now=now)

    with Session(engine) as session:
        assert defer_start_command(
            session, download_id, "owner", now=now
        )

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_estado == "pendiente"
        assert download.qbittorrent_hash == "a" * 40
        assert download.inicio_intentos == 1
        assert download.inicio_locked_by is None
        assert claim_next_start(
            session, "worker-b", now=now
        ) is None

    with Session(engine) as session:
        assert claim_next_start(
            session,
            "worker-b",
            now=now + timedelta(seconds=61),
        )


def test_legacy_download_not_started(tmp_path):
    engine, download_id = setup_download(tmp_path)

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        download.inicio_estado = "no_requerido"
        session.add(download)
        session.commit()

    with Session(engine) as session:
        assert claim_next_start(session, "worker") is None


def test_paused_download_not_started(tmp_path):
    engine, download_id = setup_download(tmp_path)

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        download.estado = "pausada"
        session.add(download)
        session.commit()

    with Session(engine) as session:
        assert claim_next_start(session, "worker") is None


def test_owned_lease_cannot_be_claimed_by_another_worker(tmp_path):
    engine, download_id = setup_download(tmp_path)
    now = datetime.now(UTC)

    with Session(engine) as session:
        claimed = claim_next_start(session, "owner", now=now)
        assert claimed is not None

    with Session(engine) as session:
        blocked = claim_next_start(
            session,
            "different-worker",
            now=now + timedelta(seconds=30),
        )
        assert blocked is None

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_locked_by == "owner"
        assert download.inicio_intentos == 1

    engine.dispose()


def test_inconsistent_lock_is_not_automatically_stolen(tmp_path):
    engine, download_id = setup_download(tmp_path)

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        download.inicio_locked_by = "previous-worker"
        download.inicio_locked_until = None
        session.add(download)
        session.commit()

    with Session(engine) as session:
        assert claim_next_start(session, "new-worker") is None

    engine.dispose()


def test_previous_owner_cannot_confirm_after_reclaim(tmp_path):
    engine, download_id = setup_download(tmp_path)
    now = datetime.now(UTC)

    with Session(engine) as session:
        assert claim_next_start(session, "worker-old", now=now)

    later = now + timedelta(seconds=91)

    with Session(engine) as session:
        claimed = claim_next_start(
            session, "worker-new", now=later
        )
        assert claimed is not None

    with Session(engine) as session:
        assert not confirm_start_command(
            session, download_id, "worker-old", now=later
        )
        assert confirm_start_command(
            session, download_id, "worker-new", now=later
        )

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_estado == "iniciada"
        assert download.inicio_intentos == 2

    engine.dispose()


def test_previous_owner_cannot_defer_after_reclaim(tmp_path):
    engine, download_id = setup_download(tmp_path)
    now = datetime.now(UTC)

    with Session(engine) as session:
        assert claim_next_start(session, "worker-old", now=now)

    later = now + timedelta(seconds=91)

    with Session(engine) as session:
        assert claim_next_start(
            session, "worker-new", now=later
        )

    with Session(engine) as session:
        assert not defer_start_command(
            session, download_id, "worker-old", now=later
        )

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_locked_by == "worker-new"
        assert download.inicio_intentos == 2

    engine.dispose()


def test_expired_owner_cannot_confirm_without_reclaim(tmp_path):
    engine, download_id = setup_download(tmp_path)
    now = datetime.now(UTC)

    with Session(engine) as session:
        assert claim_next_start(session, "worker-a", now=now)

    expired = now + timedelta(seconds=91)

    with Session(engine) as session:
        assert not confirm_start_command(
            session, download_id, "worker-a", now=expired
        )
        assert not defer_start_command(
            session, download_id, "worker-a", now=expired
        )

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_estado == "pendiente"

    engine.dispose()


def test_review_state_stops_future_claims(tmp_path):
    engine, download_id = setup_download(tmp_path)
    now = datetime.now(UTC)

    with Session(engine) as session:
        assert claim_next_start(session, "owner", now=now)

    with Session(engine) as session:
        from app.download_start_queue import mark_start_needs_review

        assert mark_start_needs_review(
            session, download_id, "owner", now=now
        )

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.inicio_estado == "requiere_revision"
        assert download.inicio_locked_by is None
        assert claim_next_start(session, "other", now=now) is None

    engine.dispose()


def test_review_requires_valid_lease_owner(tmp_path):
    engine, download_id = setup_download(tmp_path)
    now = datetime.now(UTC)

    with Session(engine) as session:
        assert claim_next_start(session, "owner", now=now)

    from app.download_start_queue import mark_start_needs_review

    with Session(engine) as session:
        assert not mark_start_needs_review(
            session, download_id, "other", now=now
        )
        assert not mark_start_needs_review(
            session,
            download_id,
            "owner",
            now=now + timedelta(seconds=91),
        )

    engine.dispose()
