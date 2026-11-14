import multiprocessing
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, SQLModel, create_engine

from app.models import Perfil, Solicitud
from app.queue import (
    claim_next_request,
    complete_request,
    fail_request,
    get_queue_counts,
    renew_lease,
)


def _claim_request_in_process(
    database_url: str,
    worker_id: str,
    barrier,
    results,
) -> None:
    """Intenta reclamar una solicitud desde un proceso independiente."""
    engine = create_engine(
        database_url,
        connect_args={"timeout": 15},
    )
    try:
        with Session(engine) as session:
            barrier.wait(timeout=15)
            claimed = claim_next_request(
                session,
                worker_id,
                now=datetime(2026, 11, 2, 20, 0, tzinfo=UTC),
            )
            results.put((worker_id, claimed.id if claimed else None))
    finally:
        engine.dispose()


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


def test_queue_counts_report_all_states_without_mutating_requests():
    with make_session() as session:
        request = add_request(session)
        counts = get_queue_counts(session)

        assert counts["pendiente"] == 1
        assert counts["procesando"] == 0
        assert counts["completada"] == 0
        assert counts["fallida"] == 0
        assert counts["cancelada"] == 0
        assert counts["vigilando"] == 0

        saved = session.get(Solicitud, request.id)
        assert saved is not None
        assert saved.estado == "pendiente"


def test_expired_lease_at_attempt_limit_becomes_failed():
    start = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)
    with make_session() as session:
        request = add_request(session, max_attempts=1)
        claimed = claim_next_request(
            session,
            "worker-a",
            lease_seconds=10,
            now=start,
        )
        assert claimed is not None
        assert claimed.intentos == 1

        # El siguiente ciclo de reclamación detecta que el lease venció.
        assert (
            claim_next_request(
                session,
                "worker-b",
                now=start + timedelta(seconds=11),
            )
            is None
        )

        saved = session.get(Solicitud, request.id)
        assert saved is not None
        assert saved.estado == "fallida"
        assert saved.locked_by is None
        assert saved.locked_until is None
        assert saved.heartbeat is None
        assert saved.ultimo_error == "Lease caducado; trabajo recuperado"


def test_expired_lease_cannot_be_renewed_or_completed_by_old_worker():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)
    expired_at = now + timedelta(seconds=121)
    with make_session() as session:
        request = add_request(session)
        claimed = claim_next_request(
            session,
            "worker-a",
            lease_seconds=120,
            now=now,
        )
        assert claimed is not None

        assert not renew_lease(
            session,
            request.id,
            "worker-a",
            now=expired_at,
        )
        assert not complete_request(
            session,
            request.id,
            "worker-a",
            now=expired_at,
        )


def test_two_processes_cannot_claim_the_same_request(tmp_path):
    database_file = tmp_path / "queue-concurrency.db"
    database_url = f"sqlite:///{database_file}"
    engine = create_engine(database_url)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        request = add_request(session)
        request_id = request.id

    engine.dispose()

    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    results = context.Queue()
    workers = [
        context.Process(
            target=_claim_request_in_process,
            args=(database_url, worker_id, barrier, results),
        )
        for worker_id in ("worker-a", "worker-b")
    ]

    try:
        for worker in workers:
            worker.start()

        for worker in workers:
            worker.join(timeout=30)

        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join()
                raise AssertionError("Un proceso de reclamación quedó bloqueado")

        assert [worker.exitcode for worker in workers] == [0, 0]

        outcomes = [results.get(timeout=5) for _ in workers]
        claimed_ids = [request_id_result for _, request_id_result in outcomes]

        assert claimed_ids.count(request_id) == 1
        assert claimed_ids.count(None) == 1
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join()
        results.close()
        results.join_thread()
