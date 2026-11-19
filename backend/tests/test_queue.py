import multiprocessing
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Descarga, Perfil, ResultadoBusqueda, Solicitud
from app.queue import (
    claim_next_download,
    claim_next_request,
    complete_request,
    fail_download,
    fail_request,
    finish_search_request,
    get_queue_counts,
    mark_download_submitted,
    record_download_attempt,
    renew_download_lease,
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
def test_finish_search_request_saves_results_and_releases_lease():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        request = add_request(session)
        claimed = claim_next_request(session, "worker-a", now=now)
        assert claimed is not None

        result = ResultadoBusqueda(
            solicitud_id=request.id,
            clave="resultado-1",
            titulo="Película 1080p",
            indexador="Jackett",
            download_url="https://example.com/download/1",
        )

        assert finish_search_request(
            session, request.id, "worker-a", [result], now=now
        )

        saved = session.get(Solicitud, request.id)
        assert saved is not None
        assert saved.estado == "esperando_seleccion"
        assert saved.locked_by is None
        assert saved.locked_until is None
        assert saved.heartbeat is None

        results = session.exec(
            select(ResultadoBusqueda).where(
                ResultadoBusqueda.solicitud_id == request.id
            )
        ).all()
        assert len(results) == 1
        assert results[0].titulo == "Película 1080p"


def test_finish_search_request_without_results():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        request = add_request(session)
        assert claim_next_request(session, "worker-a", now=now) is not None

        assert finish_search_request(
            session, request.id, "worker-a", [], now=now
        )

        saved = session.get(Solicitud, request.id)
        assert saved is not None
        assert saved.estado == "sin_resultados"
        assert saved.locked_by is None
        assert saved.locked_until is None
        assert saved.heartbeat is None


def test_finish_search_request_rejects_another_worker():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        request = add_request(session)
        assert claim_next_request(session, "worker-a", now=now) is not None

        assert not finish_search_request(
            session, request.id, "worker-b", [], now=now
        )

        saved = session.get(Solicitud, request.id)
        assert saved is not None
        assert saved.estado == "procesando"
        assert saved.locked_by == "worker-a"


def test_finish_search_request_rejects_expired_lease():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        request = add_request(session)
        assert claim_next_request(
            session, "worker-a", lease_seconds=10, now=now
        ) is not None

        expired_at = now + timedelta(seconds=11)

        assert not finish_search_request(
            session, request.id, "worker-a", [], now=expired_at
        )

        saved = session.get(Solicitud, request.id)
        assert saved is not None
        assert saved.estado == "procesando"
        assert saved.locked_by == "worker-a"

def test_failure_backoff_respects_maximum_delay():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        request = add_request(session, max_attempts=5)

        first = claim_next_request(session, "worker-a", now=now)
        assert first is not None

        assert fail_request(
            session,
            request.id,
            "worker-a",
            "primer fallo",
            retry_base_seconds=30,
            retry_max_seconds=45,
            now=now,
        )

        second_time = now + timedelta(seconds=30)
        second = claim_next_request(
            session,
            "worker-a",
            now=second_time,
        )
        assert second is not None

        assert fail_request(
            session,
            request.id,
            "worker-a",
            "segundo fallo",
            retry_base_seconds=30,
            retry_max_seconds=45,
            now=second_time,
        )

        saved = session.get(Solicitud, request.id)
        assert saved is not None
        assert saved.estado == "pendiente"
        assert saved.disponible_desde == second_time + timedelta(seconds=45)

def test_old_worker_cannot_fail_request_after_reclaim():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        request = add_request(session)

        first = claim_next_request(
            session,
            "worker-a",
            lease_seconds=10,
            now=now,
        )
        assert first is not None

        reclaimed_time = now + timedelta(seconds=11)
        second = claim_next_request(
            session,
            "worker-b",
            now=reclaimed_time,
        )
        assert second is not None
        assert second.locked_by == "worker-b"

        assert not fail_request(
            session,
            request.id,
            "worker-a",
            "fallo tardío",
            now=reclaimed_time,
        )

        saved = session.get(Solicitud, request.id)
        assert saved is not None
        assert saved.estado == "procesando"
        assert saved.locked_by == "worker-b"
        assert saved.intentos == 2
        assert saved.ultimo_error == "Lease caducado; trabajo recuperado"

def add_download(session: Session, *, max_attempts: int = 5) -> Descarga:
    request = add_request(session)
    download = Descarga(
        solicitud_id=request.id,
        titulo="Descarga de prueba",
        info_hash="a" * 40,
        max_intentos_envio=max_attempts,
        disponible_desde=datetime(2026, 11, 2, 19, 0, tzinfo=UTC),
    )
    session.add(download)
    session.commit()
    session.refresh(download)
    return download


def test_download_claim_does_not_consume_send_attempts():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        download = add_download(session)

        claimed = claim_next_download(session, "worker-a", now=now)

        assert claimed is not None
        assert claimed.id == download.id
        assert claimed.locked_by == "worker-a"
        assert claimed.locked_until == now + timedelta(seconds=120)
        assert claimed.intentos_envio == 0
        assert claim_next_download(session, "worker-b", now=now) is None


def test_download_attempt_requires_valid_lease():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        download = add_download(session)
        assert claim_next_download(session, "worker-a", now=now)

        assert not record_download_attempt(
            session, download.id, "worker-b", now=now
        )
        assert record_download_attempt(
            session, download.id, "worker-a", now=now
        )

        saved = session.get(Descarga, download.id)
        assert saved is not None
        assert saved.intentos_envio == 1


def test_download_submission_releases_lease():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        download = add_download(session)
        assert claim_next_download(session, "worker-a", now=now)

        assert mark_download_submitted(
            session,
            download.id,
            "worker-a",
            "a" * 40,
            now=now,
        )

        saved = session.get(Descarga, download.id)
        assert saved is not None
        assert saved.estado == "enviada"
        assert saved.qbittorrent_hash == "a" * 40
        assert saved.locked_by is None
        assert saved.locked_until is None


def test_download_failure_uses_exponential_backoff():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        download = add_download(session, max_attempts=2)
        assert claim_next_download(session, "worker-a", now=now)
        assert record_download_attempt(
            session, download.id, "worker-a", now=now
        )

        assert fail_download(
            session,
            download.id,
            "worker-a",
            "fallo temporal",
            retry_base_seconds=30,
            now=now,
        )

        saved = session.get(Descarga, download.id)
        assert saved is not None
        assert saved.estado == "seleccionada"
        assert saved.intentos_envio == 1
        assert saved.disponible_desde == now + timedelta(seconds=30)
        assert saved.locked_by is None

        retry_time = now + timedelta(seconds=30)
        assert claim_next_download(
            session, "worker-a", now=retry_time
        )
        assert record_download_attempt(
            session, download.id, "worker-a", now=retry_time
        )
        assert fail_download(
            session,
            download.id,
            "worker-a",
            "fallo definitivo",
            now=retry_time,
        )

        saved = session.get(Descarga, download.id)
        assert saved is not None
        assert saved.estado == "fallida"


def test_expired_download_lease_is_recovered_without_consuming_attempt():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        download = add_download(session)
        assert claim_next_download(
            session, "worker-a", lease_seconds=10, now=now
        )

        recovered = claim_next_download(
            session,
            "worker-b",
            now=now + timedelta(seconds=11),
        )

        assert recovered is not None
        assert recovered.id == download.id
        assert recovered.locked_by == "worker-b"
        assert recovered.intentos_envio == 0

def test_download_lease_renewal_checks_worker_ownership():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        download = add_download(session)
        assert claim_next_download(
            session, "worker-a", lease_seconds=10, now=now
        )

        assert not renew_download_lease(
            session, download.id, "worker-b", now=now
        )
        assert renew_download_lease(
            session,
            download.id,
            "worker-a",
            lease_seconds=30,
            now=now,
        )

        saved = session.get(Descarga, download.id)
        assert saved is not None
        assert saved.locked_until == now + timedelta(seconds=30)
        assert saved.heartbeat == now

def test_terminal_download_failure_reopens_request_for_selection():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        download = add_download(session, max_attempts=1)
        request = session.get(Solicitud, download.solicitud_id)
        assert request is not None

        request.estado = "completada"
        session.add(request)
        session.commit()

        assert claim_next_download(session, "worker-a", now=now)
        assert record_download_attempt(
            session, download.id, "worker-a", now=now
        )
        assert fail_download(
            session,
            download.id,
            "worker-a",
            "No se pudo enviar",
            now=now,
        )

        saved_download = session.get(Descarga, download.id)
        saved_request = session.get(Solicitud, download.solicitud_id)

        assert saved_download is not None
        assert saved_request is not None
        assert saved_download.estado == "fallida"
        assert saved_download.locked_by is None
        assert saved_download.locked_until is None
        assert saved_request.estado == "esperando_seleccion"
        assert saved_request.ultimo_error == "No se pudo enviar"


def test_non_terminal_download_failure_does_not_reopen_request():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        download = add_download(session, max_attempts=3)
        request = session.get(Solicitud, download.solicitud_id)
        assert request is not None

        request.estado = "completada"
        session.add(request)
        session.commit()

        assert claim_next_download(session, "worker-a", now=now)
        assert record_download_attempt(
            session, download.id, "worker-a", now=now
        )
        assert fail_download(
            session,
            download.id,
            "worker-a",
            "Fallo temporal",
            now=now,
        )

        saved_download = session.get(Descarga, download.id)
        saved_request = session.get(Solicitud, download.solicitud_id)

        assert saved_download is not None
        assert saved_request is not None
        assert saved_download.estado == "seleccionada"
        assert saved_request.estado == "completada"

def test_permanent_download_failure_does_not_consume_attempt():
    now = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)

    with make_session() as session:
        download = add_download(session, max_attempts=5)
        request = session.get(Solicitud, download.solicitud_id)
        assert request is not None

        request.estado = "completada"
        session.add(request)
        session.commit()

        assert claim_next_download(session, "worker-a", now=now)

        assert fail_download(
            session,
            download.id,
            "worker-a",
            "El resultado seleccionado no tiene un enlace válido",
            permanent=True,
            now=now,
        )

        saved_download = session.get(Descarga, download.id)
        saved_request = session.get(Solicitud, download.solicitud_id)

        assert saved_download is not None
        assert saved_request is not None
        assert saved_download.estado == "fallida"
        assert saved_download.intentos_envio == 0
        assert saved_request.estado == "esperando_seleccion"


def test_update_download_progress_lifecycle():
    from app.queue import update_download_progress

    with make_session() as session:
        solicitud = add_request(session)
        descarga = Descarga(
            solicitud_id=solicitud.id,
            titulo="Descarga de prueba",
            estado="enviada",
            qbittorrent_hash="a" * 40,
        )
        session.add(descarga)
        session.commit()
        session.refresh(descarga)
        download_id = descarga.id

        assert update_download_progress(
            session, download_id, "a" * 40, "pausada", 0
        )
        assert update_download_progress(
            session, download_id, "a" * 40, "descargando", 0.45, 1000
        )
        assert update_download_progress(
            session, download_id, "a" * 40, "descargando", 0.6
        )

        saved = session.get(Descarga, download_id)
        assert saved.estado == "descargando"
        assert saved.progreso == 0.6
        assert saved.tamano_bytes == 1000

        assert update_download_progress(
            session, download_id, "a" * 40, "completada", 1
        )
        assert not update_download_progress(
            session, download_id, "a" * 40, "pausada", 0.5
        )

        session.expire_all()
        saved = session.get(Descarga, download_id)
        assert saved.estado == "completada"
        assert saved.progreso == 1


def test_update_download_progress_rejects_wrong_hash():
    from app.queue import update_download_progress

    with make_session() as session:
        solicitud = add_request(session)
        descarga = Descarga(
            solicitud_id=solicitud.id,
            titulo="Descarga protegida",
            estado="enviada",
            qbittorrent_hash="a" * 40,
        )
        session.add(descarga)
        session.commit()
        session.refresh(descarga)

        assert not update_download_progress(
            session, descarga.id, "b" * 40, "descargando", 0.5
        )
        session.expire_all()
        assert session.get(Descarga, descarga.id).estado == "enviada"


def test_update_download_progress_rejects_invalid_values():
    import pytest

    from app.queue import update_download_progress

    with make_session() as session:
        for estado, progreso, tamano in (
            ("descargando", -0.1, None),
            ("descargando", 1.1, None),
            ("completada", 0.5, None),
            ("descargando", 0.5, -1),
            ("estado_desconocido", 0.5, None),
        ):
            with pytest.raises(ValueError):
                update_download_progress(
                    session, 1, "a" * 40, estado, progreso, tamano
                )


def test_update_download_progress_never_goes_backwards():
    from app.queue import update_download_progress

    with make_session() as session:
        solicitud = add_request(session)
        descarga = Descarga(
            solicitud_id=solicitud.id,
            titulo="Prueba de progreso",
            estado="descargando",
            qbittorrent_hash="c" * 40,
            progreso=0.60,
            tamano_bytes=2000,
        )
        session.add(descarga)
        session.commit()
        session.refresh(descarga)

        assert not update_download_progress(
            session,
            descarga.id,
            "c" * 40,
            "descargando",
            0.45,
            1000,
        )

        session.expire_all()
        guardada = session.get(Descarga, descarga.id)
        assert guardada.estado == "descargando"
        assert guardada.progreso == 0.60
        assert guardada.tamano_bytes == 2000


def test_update_download_progress_rejects_invalid_types():
    import math

    import pytest

    from app.queue import update_download_progress

    invalidos = (
        (True, None),
        (False, None),
        (math.nan, None),
        (math.inf, None),
        (-math.inf, None),
        ("0.5", None),
        (0.5, True),
        (0.5, 1.5),
    )

    with make_session() as session:
        for progreso, tamano in invalidos:
            with pytest.raises(ValueError):
                update_download_progress(
                    session,
                    1,
                    "c" * 40,
                    "descargando",
                    progreso,
                    tamano,
                )


def test_update_download_progress_does_not_return_to_sent():
    from app.queue import update_download_progress

    with make_session() as session:
        solicitud = add_request(session)
        descarga = Descarga(
            solicitud_id=solicitud.id,
            titulo="Descarga activa",
            estado="descargando",
            qbittorrent_hash="e" * 40,
            progreso=0.60,
        )
        session.add(descarga)
        session.commit()
        session.refresh(descarga)

        assert not update_download_progress(
            session,
            descarga.id,
            "e" * 40,
            "enviada",
            0.60,
        )

        session.expire_all()
        guardada = session.get(Descarga, descarga.id)
        assert guardada.estado == "descargando"
        assert guardada.progreso == 0.60

@pytest.fixture
def verification_session_factory(tmp_path):
    """Comparte una SQLite temporal entre sesiones de una misma prueba."""
    database = tmp_path / "verification.db"
    engine = create_engine(f"sqlite:///{database}")
    SQLModel.metadata.create_all(engine)

    try:
        yield lambda: Session(engine)
    finally:
        engine.dispose()


def test_record_download_verification_success(verification_session_factory):
    from app.queue import record_download_verification

    with verification_session_factory() as session:
        descarga = add_download(session)
        descarga.estado = "completada"
        descarga.progreso = 1.0
        descarga.qbittorrent_hash = "a" * 40
        session.add(descarga)
        session.commit()
        download_id = descarga.id

    with verification_session_factory() as session:
        assert record_download_verification(
            session, download_id, "a" * 40, verified=True
        )

    with verification_session_factory() as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado == "completada"
        assert descarga.estado_verificacion == "verificada"
        assert descarga.verificada_en is not None
        assert descarga.error_verificacion is None


def test_record_download_verification_rejects_incomplete(verification_session_factory):
    from app.queue import record_download_verification

    with verification_session_factory() as session:
        descarga = add_download(session)
        descarga.estado = "descargando"
        descarga.progreso = 0.5
        descarga.qbittorrent_hash = "a" * 40
        session.add(descarga)
        session.commit()
        download_id = descarga.id

    with verification_session_factory() as session:
        assert not record_download_verification(
            session, download_id, "a" * 40, verified=True
        )


def test_record_download_verification_rejects_wrong_hash(verification_session_factory):
    from app.queue import record_download_verification

    with verification_session_factory() as session:
        descarga = add_download(session)
        descarga.estado = "completada"
        descarga.progreso = 1.0
        descarga.qbittorrent_hash = "a" * 40
        session.add(descarga)
        session.commit()
        download_id = descarga.id

    with verification_session_factory() as session:
        assert not record_download_verification(
            session, download_id, "b" * 40, verified=True
        )


def test_record_download_verification_failure_then_recovery(verification_session_factory):
    from app.queue import record_download_verification

    with verification_session_factory() as session:
        descarga = add_download(session)
        descarga.estado = "completada"
        descarga.progreso = 1.0
        descarga.qbittorrent_hash = "a" * 40
        session.add(descarga)
        session.commit()
        download_id = descarga.id

    with verification_session_factory() as session:
        assert record_download_verification(
            session,
            download_id,
            "a" * 40,
            verified=False,
            error="Archivo no encontrado",
        )

    with verification_session_factory() as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado_verificacion == "fallida"
        assert descarga.error_verificacion == "Archivo no encontrado"

    with verification_session_factory() as session:
        assert record_download_verification(
            session, download_id, "a" * 40, verified=True
        )

    with verification_session_factory() as session:
        descarga = session.get(Descarga, download_id)
        assert descarga.estado_verificacion == "verificada"
        assert descarga.verificada_en is not None
        assert descarga.error_verificacion is None

    with verification_session_factory() as session:
        assert not record_download_verification(
            session,
            download_id,
            "a" * 40,
            verified=False,
            error="Error posterior",
        )


def test_record_download_verification_is_idempotent(verification_session_factory):
    from app.queue import record_download_verification

    with verification_session_factory() as session:
        descarga = add_download(session)
        descarga.estado = "completada"
        descarga.progreso = 1.0
        descarga.qbittorrent_hash = "a" * 40
        session.add(descarga)
        session.commit()
        download_id = descarga.id

    with verification_session_factory() as session:
        assert record_download_verification(
            session, download_id, "a" * 40, verified=True
        )

    with verification_session_factory() as session:
        assert not record_download_verification(
            session, download_id, "a" * 40, verified=True
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"verified": "yes"},
        {"verified": False},
        {"verified": True, "error": "No permitido"},
        {"verified": False, "error": " "},
    ],
)
def test_record_download_verification_rejects_invalid_arguments(
    kwargs, verification_session_factory
):
    from app.queue import record_download_verification

    with verification_session_factory() as session:
        with pytest.raises(ValueError):
            record_download_verification(
                session, 1, "a" * 40, **kwargs
            )
