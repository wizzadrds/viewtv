from datetime import UTC, datetime, timedelta

from sqlmodel import Session, SQLModel, create_engine

from app.models import Perfil, Solicitud
from app.queue import claim_next_request, complete_request, fail_request, renew_lease


def make_session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def add_request(session: Session, *, max_attempts: int = 5) -> Solicitud:
    profile = Perfil(nombre="Pruebas", pin_hash="hash-de-prueba")
    session.add(profile)
    session.commit()
    session.refresh(profile)
    request = Solicitud(
        perfil_id=profile.id,
        jellyfin_item_id="jf-test",
        titulo="Solicitud de prueba",
        max_intentos=max_attempts,
        # Las pruebas usan un reloj fijo; la solicitud debe estar disponible
        # antes de ese instante, no a la hora real de ejecución del test.
        disponible_desde=datetime(2026, 11, 2, 19, 0, tzinfo=UTC),
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def test_claim_is_exclusive_and_increments_attempts():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)
    with make_session() as session:
        request = add_request(session)

        claimed = claim_next_request(session, "worker-a", now=now)
        assert claimed is not None
        assert claimed.id == request.id
        assert claimed.estado == "procesando"
        assert claimed.intentos == 1
        assert claimed.locked_by == "worker-a"
        assert claimed.locked_until == now + timedelta(seconds=120)
        assert claim_next_request(session, "worker-b", now=now) is None


def test_expired_lease_is_recovered_and_reclaimed():
    start = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)
    with make_session() as session:
        request = add_request(session)
        first = claim_next_request(session, "worker-a", lease_seconds=10, now=start)
        assert first is not None

        recovered = claim_next_request(
            session,
            "worker-b",
            now=start + timedelta(seconds=11),
        )

        assert recovered is not None
        assert recovered.id == request.id
        assert recovered.estado == "procesando"
        assert recovered.intentos == 2
        assert recovered.locked_by == "worker-b"
        assert recovered.ultimo_error == "Lease caducado; trabajo recuperado"


def test_lease_renewal_and_completion_require_owner():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)
    with make_session() as session:
        request = add_request(session)
        claimed = claim_next_request(session, "worker-a", now=now)
        assert claimed is not None

        assert not renew_lease(session, request.id, "worker-b", now=now)
        assert renew_lease(session, request.id, "worker-a", now=now)
        assert not complete_request(session, request.id, "worker-b", now=now)
        assert complete_request(session, request.id, "worker-a", now=now)

        saved = session.get(Solicitud, request.id)
        assert saved is not None
        assert saved.estado == "completada"
        assert saved.locked_by is None
        assert saved.locked_until is None


def test_failure_uses_exponential_backoff_and_eventually_stops():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)
    with make_session() as session:
        request = add_request(session, max_attempts=2)
        first = claim_next_request(session, "worker-a", now=now)
        assert first is not None
        assert fail_request(
            session,
            request.id,
            "worker-a",
            "fallo temporal",
            retry_base_seconds=30,
            now=now,
        )

        saved = session.get(Solicitud, request.id)
        assert saved is not None
        assert saved.estado == "pendiente"
        assert saved.disponible_desde == now + timedelta(seconds=30)

        second = claim_next_request(
            session,
            "worker-a",
            now=now + timedelta(seconds=30),
        )
        assert second is not None
        assert second.intentos == 2
        assert fail_request(
            session,
            request.id,
            "worker-a",
            "fallo definitivo",
            retry_base_seconds=30,
            now=now + timedelta(seconds=30),
        )

        saved = session.get(Solicitud, request.id)
        assert saved is not None
        assert saved.estado == "fallida"
        assert saved.locked_by is None
        assert saved.ultimo_error == "fallo definitivo"
