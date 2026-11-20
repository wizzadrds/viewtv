"""Heartbeat 0013 en otro hilo: solo /tmp y datos multimedia sintéticos."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import update
from sqlmodel import Session, SQLModel, create_engine
from worker.organization_lease_heartbeat_sandbox import (
    IndependentOrganizationHeartbeat,
    SandboxLeaseLost,
)

from app.models import Descarga, Perfil, Solicitud
from app.organization_queue import (
    claim_next_organization,
    confirm_organization,
    renew_organization_lease,
)

_MARKER = "VIEWTV_LEASE_GATE_SANDBOX_V1\n"


@pytest.fixture
def fake_job():
    root = Path("/tmp") / ("viewtv-lease-gate-" + uuid4().hex)
    root.mkdir(mode=0o700, exist_ok=False)
    marker = root / ".viewtv-lease-gate-sandbox-only"
    marker.write_text(_MARKER, encoding="utf-8")
    db = root / "organization.sqlite3"
    engine = create_engine(f"sqlite:///{db}")
    now = datetime.now(UTC)
    try:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            profile = Perfil(nombre="Perfil inventado", pin_hash="hash-ficticio")
            session.add(profile)
            session.flush()
            request = Solicitud(
                perfil_id=profile.id,
                titulo="Vídeo de prueba",
                tipo_medio="pelicula",
                estado="completada",
            )
            session.add(request)
            session.flush()
            download = Descarga(
                solicitud_id=request.id,
                titulo="Vídeo de prueba",
                estado="completada",
                progreso=1,
                estado_verificacion="verificada",
                verificada_en=now,
                qbittorrent_hash="a" * 40,
                organizacion_estado="pendiente",
            )
            session.add(download)
            session.commit()
            session.refresh(download)
            download_id = download.id
            assert download_id is not None
            claimed = claim_next_organization(session, "ficticio", now=now)
            assert claimed is not None and claimed.organizacion_intentos == 1
        yield engine, download_id, root
    finally:
        engine.dispose()
        # Borrar exclusivamente archivos propios, nunca rutas inesperadas.
        if (
            root.parent == Path("/tmp")
            and root.name.startswith("viewtv-lease-gate-")
            and not root.is_symlink()
            and marker.is_file()
            and marker.read_text(encoding="utf-8") == _MARKER
        ):
            authorized = {
                "organization.sqlite3", ".viewtv-lease-gate-sandbox-only",
                "video-ficticio.bin", "copia-ficticia.bin",
            }
            if {p.name for p in root.iterdir()} <= authorized:
                for name in authorized:
                    (root / name).unlink(missing_ok=True)
                root.rmdir()


def make_heartbeat(fake_job, **kwargs):
    engine, download_id, _ = fake_job
    settings = dict(interval_seconds=0.02, lease_seconds=180)
    settings.update(kwargs)
    return IndependentOrganizationHeartbeat(
        engine, download_id, "ficticio", attempt=1, **settings
    )


def until(condition, seconds=2):
    deadline = monotonic() + seconds
    while monotonic() < deadline:
        if condition():
            return True
        sleep(0.01)
    return condition()


def test_heartbeat_runs_during_independent_blocking_io(fake_job):
    """Copia real de 128 MiB ficticios; el contador crece sin callbacks."""
    _, _, root = fake_job
    source = root / "video-ficticio.bin"
    target = root / "copia-ficticia.bin"
    block = b"V" * 1_048_576
    with source.open("wb") as stream:
        for _ in range(128):
            stream.write(block)
    with make_heartbeat(fake_job) as heartbeat:
        initial = heartbeat.renewals
        source_hash = sha256()
        destination_hash = sha256()
        with source.open("rb") as reader, target.open("wb") as writer:
            while data := reader.read(1_048_576):
                source_hash.update(data)
                writer.write(data)
                destination_hash.update(data)
                sleep(0.004)
            writer.flush()
        assert target.stat().st_size == 128 * 1_048_576
        assert source_hash.hexdigest() == destination_hash.hexdigest()
        assert heartbeat.renewals >= initial + 3
        heartbeat.require_active()
    assert heartbeat.renewals >= 4
    assert not heartbeat.lost


def test_background_detects_owner_lost_even_when_caller_is_blocked(fake_job):
    engine, did, _ = fake_job
    with make_heartbeat(fake_job) as heartbeat:
        with Session(engine) as session:
            session.exec(
                update(Descarga).where(Descarga.id == did).values(
                    organizacion_locked_by="otra-identidad"
                )
            )
            session.commit()
        sleep(0.1)  # La copia simulada está bloqueada, sin llamar heartbeat.
        assert until(lambda: heartbeat.lost)
        with pytest.raises(SandboxLeaseLost):
            heartbeat.require_active()
    with Session(engine) as session:
        row = session.get(Descarga, did)
        assert row is not None and row.organizacion_estado == "pendiente"


def test_same_worker_new_attempt_cannot_be_renewed_by_old_heartbeat(fake_job):
    engine, did, _ = fake_job
    with make_heartbeat(fake_job) as heartbeat:
        with Session(engine) as session:
            session.exec(
                update(Descarga).where(Descarga.id == did).values(
                    organizacion_locked_until=datetime.now(UTC) - timedelta(seconds=1)
                )
            )
            session.commit()
        with Session(engine) as session:
            renewed_claim = claim_next_organization(session, "ficticio")
            assert renewed_claim is not None and renewed_claim.organizacion_intentos == 2
        assert until(lambda: heartbeat.lost)
        with pytest.raises(SandboxLeaseLost):
            heartbeat.require_active()
    with Session(engine) as session:
        assert not renew_organization_lease(
            session, did, "ficticio", expected_attempt=1
        )
        assert not confirm_organization(
            session, did, "ficticio", expected_attempt=1
        )
        assert renew_organization_lease(
            session, did, "ficticio", expected_attempt=2
        )
        assert confirm_organization(
            session, did, "ficticio", expected_attempt=2
        )


def test_corrupted_marker_fails_closed_and_is_restored(fake_job):
    _, _, root = fake_job
    marker = root / ".viewtv-lease-gate-sandbox-only"
    with make_heartbeat(fake_job) as heartbeat:
        try:
            marker.write_text("NO ES UN SANDBOX", encoding="utf-8")
            assert until(lambda: heartbeat.lost)
            with pytest.raises(SandboxLeaseLost):
                heartbeat.require_active()
        finally:
            marker.write_text(_MARKER, encoding="utf-8")


def test_double_start_and_after_stop_fail_closed(fake_job):
    heartbeat = make_heartbeat(fake_job)
    heartbeat.start()
    with pytest.raises(RuntimeError):
        heartbeat.start()
    heartbeat.stop()
    with pytest.raises(SandboxLeaseLost):
        heartbeat.require_active()
    with pytest.raises(RuntimeError):
        heartbeat.start()


@pytest.mark.parametrize(
    "overrides",
    [
        {"attempt": 0},
        {"attempt": 4},
        {"interval_seconds": 0},
        {"interval_seconds": 31},
        {"lease_seconds": 901},
        {"worker_id": ""},
    ],
)
def test_invalid_identity_and_interval_refused(fake_job, overrides):
    engine, did, _ = fake_job
    params = dict(
        engine=engine, download_id=did, worker_id="ficticio", attempt=1,
    )
    params.update(overrides)
    with pytest.raises(ValueError):
        IndependentOrganizationHeartbeat(**params)


def test_outside_sandbox_engine_refused(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'unknown.sqlite3'}")
    try:
        with pytest.raises(ValueError):
            IndependentOrganizationHeartbeat(
                engine, 1, "ficticio", attempt=1,
            )
    finally:
        engine.dispose()


def test_initial_loss_prevents_start(fake_job):
    engine, did, _ = fake_job
    with Session(engine) as session:
        session.exec(
            update(Descarga).where(Descarga.id == did).values(
                organizacion_locked_by="otro"
            )
        )
        session.commit()
    heartbeat = make_heartbeat(fake_job)
    with pytest.raises(SandboxLeaseLost):
        heartbeat.start()
    assert heartbeat.lost and heartbeat.renewals == 0
