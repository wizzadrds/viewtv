"""Cola de organización aislada: exclusión, lease y revisión; sin archivos reales."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import Descarga, Perfil, Solicitud
from app.organization_queue import (
    LEASE_SECONDS,
    claim_next_organization,
    confirm_organization,
    defer_organization,
    mark_organization_review,
    renew_organization_lease,
)
from app.queue import record_download_verification


@pytest.fixture
def fixture(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'organization.sqlite3'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        person = Perfil(nombre="Perfil prueba", pin_hash="hash-ficticio")
        session.add(person)
        session.flush()
        request = Solicitud(
            perfil_id=person.id,
            titulo="Corto ficticio",
            tipo_medio="pelicula",
            estado="completada",
        )
        session.add(request)
        session.flush()
        download = Descarga(
            solicitud_id=request.id,
            titulo="Corto ficticio",
            estado="completada",
            progreso=1,
            estado_verificacion="verificada",
            qbittorrent_hash="a" * 40,
            organizacion_estado="pendiente",
        )
        session.add(download)
        session.commit()
        session.refresh(download)
        download_id = download.id

    yield engine, download_id
    engine.dispose()


def test_claim_is_exclusive_and_expired_lease_can_be_reclaimed(fixture):
    engine, did = fixture
    now = datetime.now(UTC)
    with Session(engine) as session:
        claim = claim_next_organization(session, "worker-a", now=now)
        assert claim is not None and claim.id == did
        assert claim.organizacion_intentos == 1
        assert claim.organizacion_locked_by == "worker-a"
    with Session(engine) as session:
        assert claim_next_organization(session, "worker-b", now=now) is None
    with Session(engine) as session:
        claim = claim_next_organization(
            session, "worker-b", now=now + timedelta(seconds=LEASE_SECONDS + 1)
        )
        assert claim is not None and claim.organizacion_intentos == 2
        assert claim.organizacion_locked_by == "worker-b"


def test_confirmation_requires_current_owner(fixture):
    engine, did = fixture
    now = datetime.now(UTC)
    with Session(engine) as session:
        assert claim_next_organization(session, "worker-a", now=now)
    with Session(engine) as session:
        assert not confirm_organization(session, did, "worker-b", now=now)
        assert confirm_organization(session, did, "worker-a", now=now)
        assert not confirm_organization(session, did, "worker-a", now=now)
    with Session(engine) as session:
        assert claim_next_organization(session, "worker-b", now=now) is None
        row = session.get(Descarga, did)
        assert row.organizacion_estado == "organizada"
        assert row.organizacion_locked_by is None


def test_old_owner_cannot_confirm_or_defer_after_reclaim(fixture):
    engine, did = fixture
    now = datetime.now(UTC)
    later = now + timedelta(seconds=LEASE_SECONDS + 1)
    with Session(engine) as session:
        assert claim_next_organization(session, "old", now=now)
    with Session(engine) as session:
        assert claim_next_organization(session, "new", now=later)
    with Session(engine) as session:
        assert not confirm_organization(session, did, "old", now=later)
        assert not defer_organization(session, did, "old", "otro", now=later)
        assert confirm_organization(session, did, "new", now=later)


def test_expired_lease_cannot_confirm_or_review(fixture):
    engine, did = fixture
    now = datetime.now(UTC)
    with Session(engine) as session:
        assert claim_next_organization(session, "old", now=now)
    later = now + timedelta(seconds=LEASE_SECONDS + 1)
    with Session(engine) as session:
        assert not confirm_organization(session, did, "old", now=later)
        assert not mark_organization_review(
            session, did, "old", "origen_cambio", now=later
        )


def test_defer_has_capped_retries_then_manual_review(fixture):
    engine, did = fixture
    now = datetime.now(UTC)
    with Session(engine) as session:
        assert claim_next_organization(session, "a", now=now)
        assert defer_organization(session, did, "a", "comunicacion", now=now)

    with Session(engine) as session:
        row = session.get(Descarga, did)
        assert row.organizacion_estado == "pendiente"
        assert row.organizacion_ultimo_error == "comunicacion"
        assert row.organizacion_disponible_desde.replace(tzinfo=UTC) == (
            now + timedelta(seconds=60)
        )
        assert claim_next_organization(session, "b", now=now) is None
    later = now + timedelta(seconds=61)
    with Session(engine) as session:
        assert claim_next_organization(session, "b", now=later)
        assert defer_organization(session, did, "b", "espacio_insuficiente", now=later)
    later += timedelta(seconds=121)
    with Session(engine) as session:
        assert claim_next_organization(session, "c", now=later)
        assert defer_organization(session, did, "c", "otro", now=later)
    with Session(engine) as session:
        row = session.get(Descarga, did)
        assert row.organizacion_intentos == 3
        assert row.organizacion_estado == "requiere_revision"
        assert row.organizacion_disponible_desde is None
        assert claim_next_organization(session, "d", now=later) is None


def test_third_lease_crash_becomes_review_without_fourth_claim(fixture):
    engine, did = fixture
    now = datetime.now(UTC)
    for i in range(3):
        with Session(engine) as session:
            assert claim_next_organization(
                session, f"worker-{i}", now=now + timedelta(seconds=i * (LEASE_SECONDS + 1))
            )
    late = now + timedelta(seconds=3 * (LEASE_SECONDS + 1))
    with Session(engine) as session:
        assert claim_next_organization(session, "worker-4", now=late) is None
        row = session.get(Descarga, did)
        assert row.organizacion_estado == "requiere_revision"
        assert row.organizacion_intentos == 3
        assert row.organizacion_ultimo_error == "lease_agotado"


def test_mark_review_stops_claims(fixture):
    engine, did = fixture
    now = datetime.now(UTC)
    with Session(engine) as session:
        assert claim_next_organization(session, "owner", now=now)
    with Session(engine) as session:
        assert not mark_organization_review(
            session, did, "not-owner", "archivo_invalido", now=now
        )
        assert mark_organization_review(
            session, did, "owner", "archivo_invalido", now=now
        )
    with Session(engine) as session:
        assert session.get(Descarga, did).organizacion_ultimo_error == "archivo_invalido"
        assert claim_next_organization(session, "other", now=now) is None


@pytest.mark.parametrize(
    "state,progress,verification,organization",
    [
        ("enviada", 1.0, "verificada", "pendiente"),
        ("completada", 0.7, "verificada", "pendiente"),
        ("completada", 1.0, "pendiente", "pendiente"),
        ("completada", 1.0, "fallida", "pendiente"),
        ("completada", 1.0, "verificada", "no_requerida"),
        ("completada", 1.0, "verificada", "requiere_revision"),
        ("completada", 1.0, "verificada", "organizada"),
    ],
)
def test_ineligible_jobs_are_never_claimed(
    fixture, state, progress, verification, organization
):
    engine, did = fixture
    with Session(engine) as session:
        row = session.get(Descarga, did)
        row.estado = state
        row.progreso = progress
        row.estado_verificacion = verification
        row.organizacion_estado = organization
        session.add(row)
        session.commit()
    with Session(engine) as session:
        assert claim_next_organization(session, "worker") is None


def test_inconsistent_lock_is_not_stolen(fixture):
    engine, did = fixture
    with Session(engine) as session:
        row = session.get(Descarga, did)
        row.organizacion_locked_by = "old"
        row.organizacion_locked_until = None
        session.add(row)
        session.commit()
    with Session(engine) as session:
        assert claim_next_organization(session, "worker") is None


@pytest.mark.parametrize("bad", ["", " ", "x" * 129, None, 123])
def test_rejects_invalid_worker_identity(fixture, bad):
    engine, _ = fixture
    with Session(engine) as session, pytest.raises(ValueError):
        claim_next_organization(session, bad)


@pytest.mark.parametrize("bad", ["ruta=/media/secretos", "texto", "", None])
def test_rejects_freeform_error_messages(fixture, bad):
    engine, did = fixture
    now = datetime.now(UTC)
    with Session(engine) as session:
        assert claim_next_organization(session, "owner", now=now)
    with Session(engine) as session, pytest.raises(ValueError):
        defer_organization(session, did, "owner", bad, now=now)


def test_failed_verification_does_not_queue_organization(fixture):
    engine, did = fixture
    with Session(engine) as session:
        row = session.get(Descarga, did)
        row.estado_verificacion = "pendiente"
        row.organizacion_estado = "no_requerida"
        session.add(row)
        session.commit()
    with Session(engine) as session:
        assert record_download_verification(
            session, did, "a" * 40, verified=False, error="fallo de prueba"
        )
    with Session(engine) as session:
        row = session.get(Descarga, did)
        assert row.estado_verificacion == "fallida"
        assert row.organizacion_estado == "no_requerida"
        assert claim_next_organization(session, "w") is None


def test_verified_download_is_enqueued_atomically(fixture):
    engine, did = fixture
    with Session(engine) as session:
        row = session.get(Descarga, did)
        row.estado_verificacion = "pendiente"
        row.organizacion_estado = "no_requerida"
        session.add(row)
        session.commit()
    with Session(engine) as session:
        assert record_download_verification(session, did, "a" * 40, verified=True)
    with Session(engine) as session:
        row = session.get(Descarga, did)
        assert row.estado_verificacion == "verificada"
        assert row.organizacion_estado == "pendiente"
        assert claim_next_organization(session, "w") is not None


def test_verified_with_lease_enqueues_organization(fixture):
    from app.queue import claim_next_verification, finish_claimed_verification

    engine, did = fixture
    now = datetime.now(UTC)
    with Session(engine) as session:
        row = session.get(Descarga, did)
        row.estado_verificacion = "pendiente"
        row.organizacion_estado = "no_requerida"
        session.add(row)
        session.commit()

    with Session(engine) as session:
        assert claim_next_verification(
            session, "verifier", now=now, lease_seconds=60
        ) is not None

    with Session(engine) as session:
        assert finish_claimed_verification(
            session, did, "a" * 40, "verifier",
            verified=True, now=now + timedelta(seconds=10),
        )

    with Session(engine) as session:
        row = session.get(Descarga, did)
        assert row.organizacion_estado == "pendiente"
        assert claim_next_organization(
            session, "organizer", now=now + timedelta(seconds=11)
        ) is not None


def test_failed_verification_with_lease_does_not_enqueue(fixture):
    from app.queue import claim_next_verification, finish_claimed_verification

    engine, did = fixture
    now = datetime.now(UTC)
    with Session(engine) as session:
        row = session.get(Descarga, did)
        row.estado_verificacion = "pendiente"
        row.organizacion_estado = "no_requerida"
        session.add(row)
        session.commit()

    with Session(engine) as session:
        assert claim_next_verification(
            session, "verifier", now=now, lease_seconds=60
        ) is not None

    with Session(engine) as session:
        assert finish_claimed_verification(
            session, did, "a" * 40, "verifier",
            verified=False, error="archivos inválidos",
            now=now + timedelta(seconds=10),
        )

    with Session(engine) as session:
        row = session.get(Descarga, did)
        assert row.organizacion_estado == "no_requerida"
        assert claim_next_organization(
            session, "organizer", now=now + timedelta(seconds=11)
        ) is None


def test_renew_lease_extends_and_never_shortens(fixture):
    engine, did = fixture
    now = datetime.now(UTC)
    with Session(engine) as session:
        assert claim_next_organization(session, "a", now=now)

    later = now + timedelta(seconds=80)
    with Session(engine) as session:
        assert renew_organization_lease(
            session, did, "a", lease_seconds=300, now=later
        )
        row = session.get(Descarga, did)
        expiration = row.organizacion_locked_until.replace(tzinfo=UTC)
        assert expiration == later + timedelta(seconds=300)

        assert renew_organization_lease(
            session, did, "a", lease_seconds=1, now=later
        )
        session.refresh(row)
        assert row.organizacion_locked_until.replace(tzinfo=UTC) == expiration

    with Session(engine) as session:
        assert claim_next_organization(
            session, "b", now=now + timedelta(seconds=LEASE_SECONDS + 1)
        ) is None
        assert confirm_organization(
            session, did, "a", now=now + timedelta(seconds=250)
        )


def test_renew_lease_requires_owner_and_nonexpired_lease(fixture):
    engine, did = fixture
    now = datetime.now(UTC)
    with Session(engine) as session:
        assert claim_next_organization(session, "a", now=now)

    with Session(engine) as session:
        assert not renew_organization_lease(session, did, "b", now=now)
        assert not renew_organization_lease(
            session, did, "a", now=now + timedelta(seconds=LEASE_SECONDS)
        )

    with Session(engine) as session:
        row = session.get(Descarga, did)
        assert row.organizacion_locked_by == "a"
        assert row.organizacion_locked_until.replace(tzinfo=UTC) == (
            now + timedelta(seconds=LEASE_SECONDS)
        )


def test_stale_worker_cannot_renew_after_reclaim(fixture):
    engine, did = fixture
    now = datetime.now(UTC)
    later = now + timedelta(seconds=LEASE_SECONDS + 1)
    with Session(engine) as session:
        assert claim_next_organization(session, "old", now=now)
    with Session(engine) as session:
        assert claim_next_organization(session, "new", now=later)
    with Session(engine) as session:
        assert not renew_organization_lease(session, did, "old", now=later)
        assert renew_organization_lease(session, did, "new", now=later)


@pytest.mark.parametrize("invalid", [0, -1, 901, True, None, "180", 2.5])
def test_renew_rejects_invalid_durations(fixture, invalid):
    engine, did = fixture
    now = datetime.now(UTC)
    with Session(engine) as session:
        assert claim_next_organization(session, "a", now=now)
    with Session(engine) as session, pytest.raises(ValueError):
        renew_organization_lease(
            session, did, "a", lease_seconds=invalid, now=now
        )


def test_renew_fails_if_verification_was_revoked(fixture):
    engine, did = fixture
    now = datetime.now(UTC)
    with Session(engine) as session:
        assert claim_next_organization(session, "a", now=now)
    with Session(engine) as session:
        row = session.get(Descarga, did)
        row.estado_verificacion = "fallida"
        session.add(row)
        session.commit()
    with Session(engine) as session:
        assert not renew_organization_lease(session, did, "a", now=now)
        assert not confirm_organization(session, did, "a", now=now)
