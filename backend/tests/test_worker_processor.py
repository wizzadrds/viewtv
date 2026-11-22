from datetime import UTC, datetime, timedelta

import worker.processor as processor
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.jackett import JackettError, JackettResult
from app.models import Perfil, ResultadoBusqueda, Solicitud


def make_engine():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    return test_engine


def add_request(session: Session) -> Solicitud:
    profile = Perfil(nombre="Pruebas", pin_hash="hash-de-prueba")
    session.add(profile)
    session.commit()
    session.refresh(profile)

    request = Solicitud(
        perfil_id=profile.id,
        jellyfin_item_id="jf-test",
        titulo="Película de prueba",
        tipo_medio="pelicula",
        anio=2020,
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def make_result(
    *,
    title: str = "Película de prueba 1080p",
    info_hash: str = "abcdef123456",
    download_url: str | None = "https://jackett.test/download/1",
    magnet_url: str | None = None,
    seeders: int | None = 25,
    peers: int | None = 30,
    size_bytes: int | None = 1_000_000,
) -> JackettResult:
    return JackettResult(
        title=title,
        download_url=download_url,
        magnet_url=magnet_url,
        info_hash=info_hash,
        seeders=seeders,
        peers=peers,
        size_bytes=size_bytes,
        categories=("电影",),
        indexer="Indexador de prueba",
        published_at=None,
    )


class FakeJackett:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    def search(self, query, search_type="search", categories=None):
        self.calls.append((query, search_type))
        if self.error:
            raise self.error
        return self.results


def test_conversion_discards_unusable_and_deduplicates_results():
    request_id = 1
    first = make_result()
    duplicate = make_result(
        download_url="https://jackett.test/download/duplicate",
    )
    unusable = make_result(
        info_hash="sin-enlaces",
        download_url=None,
        magnet_url=None,
    )

    converted = processor._to_database_results(
        request_id,
        [first, duplicate, unusable],
    )

    assert len(converted) == 1
    assert converted[0].solicitud_id == request_id
    assert converted[0].titulo == "Película de prueba 1080p"
    assert converted[0].seeders == 25


def test_conversion_normalizes_negative_metadata():
    converted = processor._to_database_results(
        1,
        [
            make_result(
                seeders=-1,
                peers=-2,
                size_bytes=-3,
            )
        ],
    )

    assert len(converted) == 1
    assert converted[0].seeders is None
    assert converted[0].peers is None
    assert converted[0].tamano_bytes is None


def test_process_saves_results_and_releases_lease(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    with Session(test_engine) as session:
        request = add_request(session)
        request_id = request.id

    jackett = FakeJackett(results=[make_result(title="Película de prueba 2020 1080p")])

    assert processor.process_one_request("worker-test", jackett)

    with Session(test_engine) as session:
        request = session.get(Solicitud, request_id)
        results = session.exec(
            select(ResultadoBusqueda).where(
                ResultadoBusqueda.solicitud_id == request_id
            )
        ).all()

        assert request is not None
        assert request.estado == "esperando_seleccion"
        assert request.locked_by is None
        assert request.locked_until is None
        assert len(results) == 1
        assert results[0].titulo == "Película de prueba 2020 1080p"

    assert jackett.calls == [("Película de prueba 2020", "movie"), ("Película de prueba", "movie")]


def test_process_without_results_sets_empty_state(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    with Session(test_engine) as session:
        request = add_request(session)
        request_id = request.id

    jackett = FakeJackett(results=[])

    assert processor.process_one_request("worker-test", jackett)

    with Session(test_engine) as session:
        request = session.get(Solicitud, request_id)

        assert request is not None
        assert request.estado == "sin_resultados"
        assert request.locked_by is None
        assert request.locked_until is None


def test_jackett_error_is_recorded_and_request_released(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    with Session(test_engine) as session:
        request = add_request(session)
        request_id = request.id

    jackett = FakeJackett(error=JackettError("Jackett no disponible"))

    assert processor.process_one_request("worker-test", jackett)

    with Session(test_engine) as session:
        request = session.get(Solicitud, request_id)

        assert request is not None
        assert request.estado == "pendiente"
        assert request.intentos == 1
        assert request.ultimo_error == "Jackett no disponible"
        assert request.locked_by is None
        assert request.locked_until is None


def test_empty_queue_does_not_call_jackett(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    jackett = FakeJackett()

    assert not processor.process_one_request("worker-test", jackett)
    assert jackett.calls == []

def test_jackett_initialization_error_is_recorded(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    with Session(test_engine) as session:
        request = add_request(session)
        request_id = request.id

    def broken_client():
        raise RuntimeError("Error de configuración")

    monkeypatch.setattr(processor, "JackettClient", broken_client)

    assert processor.process_one_request("worker-test")

    with Session(test_engine) as session:
        request = session.get(Solicitud, request_id)

        assert request is not None
        assert request.estado == "pendiente"
        assert request.intentos == 1
        assert request.ultimo_error == "Error interno: RuntimeError"
        assert request.locked_by is None
        assert request.locked_until is None

def test_series_request_uses_tvsearch(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    with Session(test_engine) as session:
        request = add_request(session)
        request.tipo_medio = "serie"
        request.titulo = "Serie de prueba"
        request.anio = None  # Los episodios no llevan año de estreno de la serie.
        session.add(request)
        session.commit()
        request_id = request.id

    jackett = FakeJackett(results=[make_result(title="Serie de prueba S01E01 720p")])

    assert processor.process_one_request("worker-test", jackett)

    assert jackett.calls == [("Serie de prueba", "tvsearch")]

    with Session(test_engine) as session:
        request = session.get(Solicitud, request_id)
        assert request is not None
        assert request.estado == "esperando_seleccion"

def test_lost_lease_does_not_save_search_results(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)

    with Session(test_engine) as session:
        request = add_request(session)
        request_id = request.id

    class ExpiringJackett:
        def search(self, query, search_type="search", categories=None):
            with Session(test_engine) as session:
                request = session.get(Solicitud, request_id)
                assert request is not None
                request.locked_until = datetime.now(UTC) - timedelta(seconds=1)
                session.add(request)
                session.commit()

            return [make_result()]

    assert processor.process_one_request(
        "worker-test",
        ExpiringJackett(),
    )

    with Session(test_engine) as session:
        request = session.get(Solicitud, request_id)
        results = session.exec(
            select(ResultadoBusqueda).where(
                ResultadoBusqueda.solicitud_id == request_id
            )
        ).all()

        assert request is not None
        assert request.estado == "procesando"
        assert request.locked_by == "worker-test"
        assert request.locked_until is not None
        assert request.locked_until <= datetime.now(UTC)
        assert results == []



def test_solicitud_tmdb_multilingue_enlaza_unicamente_publicaciones_correctas(monkeypatch):
    """Vengadores: Doomsday encuentra Avengers: Doomsday sin aceptar otros Doomsday."""
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)
    monkeypatch.setattr(
        processor, "aliases_para_solicitud",
        lambda title, kind, year: ("Vengadores: Doomsday", "Avengers: Doomsday"),
    )

    with Session(test_engine) as session:
        request = add_request(session)
        request.titulo = "Vengadores: Doomsday"
        request.anio = 2026
        request.jellyfin_item_id = None
        session.add(request)
        session.commit()
        request_id = request.id

    class BilingualJackett:
        calls = []

        def search(self, query, search_type="search", categories=None):
            self.calls.append(query)
            if query.startswith("Vengadores"):
                return []
            if query.startswith("Avengers"):
                return [
                    make_result(
                        title="Avengers.Doomsday.2026.1080p.WEB-DL",
                        info_hash="english-title",
                    ),
                ]
            if query.startswith("Doomsday"):
                return [
                    make_result(
                        title="Doomsday.2008.1080p.BluRay",
                        info_hash="unrelated-film",
                        download_url="https://jackett.test/download/other",
                    ),
                ]
            return []

    provider = BilingualJackett()
    assert processor.process_one_request("worker-idiomas", provider)
    with Session(test_engine) as session:
        rows = session.exec(
            select(ResultadoBusqueda).where(ResultadoBusqueda.solicitud_id == request_id)
        ).all()
        assert len(rows) == 1
        assert rows[0].titulo == "Avengers.Doomsday.2026.1080p.WEB-DL"
        assert session.get(Solicitud, request_id).estado == "esperando_seleccion"
    assert any("Avengers: Doomsday" in query for query in provider.calls)
    assert any(query.startswith("Doomsday") for query in provider.calls)
    assert len(provider.calls) <= 6


def test_fallback_sin_tmdb_conserva_consulta_original(monkeypatch):
    test_engine = make_engine()
    monkeypatch.setattr(processor, "engine", test_engine)
    monkeypatch.setattr(processor, "aliases_para_solicitud", lambda *args: ())
    with Session(test_engine) as session:
        request = add_request(session)
        request.titulo = "Título no identificado"
        session.add(request)
        session.commit()
    provider = FakeJackett(results=[make_result(title="Título no identificado 2020 1080p")])
    assert processor.process_one_request("sin-tmdb", provider)
    assert provider.calls == [
        ("Título no identificado 2020", "movie"),
        ("Título no identificado", "movie"),
    ]
