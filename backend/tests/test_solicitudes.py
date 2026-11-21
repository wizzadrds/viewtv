"""Pruebas del endpoint autenticado de creación de solicitudes."""

from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Descarga, Medio, Perfil, ResultadoBusqueda, Solicitud


@pytest.fixture
def solicitudes_context() -> Generator[tuple[TestClient, Engine], None, None]:
    """Prepara una base de datos aislada y un cliente autenticado."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        perfil = Perfil(nombre="Adultos", pin_hash="hash-de-prueba")
        medio = Medio(
            jellyfin_id="jellyfin-123",
            tipo="pelicula",
            titulo="Película de prueba",
        )
        session.add_all([perfil, medio])
        session.commit()
        session.refresh(perfil)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def override_profile() -> Perfil:
        return perfil

    previous_overrides = {
        get_session: app.dependency_overrides.get(get_session),
        get_current_profile: app.dependency_overrides.get(get_current_profile),
    }
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_profile] = override_profile

    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        for dependency, previous in previous_overrides.items():
            if previous is None:
                app.dependency_overrides.pop(dependency, None)
            else:
                app.dependency_overrides[dependency] = previous
        engine.dispose()


def test_create_request_persists_authenticated_profile_and_media(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    response = client.post(
        "/solicitudes",
        json={"medio_id": 1},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["medio_id"] == 1
    assert data["titulo"] == "Película de prueba"
    assert data["estado"] == "pendiente"
    assert "jellyfin_item_id" not in data

    with Session(engine) as session:
        saved = session.get(Solicitud, 1)
        assert saved is not None
        assert saved.perfil_id == 1
        assert saved.jellyfin_item_id == "jellyfin-123"
        assert saved.prioridad == 50
        assert saved.intentos == 0
        assert saved.max_intentos == 5


def test_create_request_rejects_unknown_media(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, _ = solicitudes_context

    response = client.post(
        "/solicitudes",
        json={"medio_id": 999},
    )

    assert response.status_code == 404


def test_create_request_rejects_unavailable_media(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    with Session(engine) as session:
        medio = session.get(Medio, 1)
        assert medio is not None
        medio.disponible_en_jellyfin = False
        session.add(medio)
        session.commit()

    response = client.post(
        "/solicitudes",
        json={"medio_id": 1},
    )

    assert response.status_code == 404


def test_create_request_rejects_active_duplicate(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    first = client.post("/solicitudes", json={"medio_id": 1})
    second = client.post("/solicitudes", json={"medio_id": 1})

    assert first.status_code == 201
    assert second.status_code == 409

    with Session(engine) as session:
        requests = session.exec(
            select(Solicitud).where(Solicitud.perfil_id == 1)
        ).all()
        assert len(requests) == 1


def test_create_request_allows_retry_after_failed_request(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    first = client.post("/solicitudes", json={"medio_id": 1})
    assert first.status_code == 201

    with Session(engine) as session:
        solicitud = session.get(Solicitud, first.json()["id"])
        assert solicitud is not None
        solicitud.estado = "fallida"
        session.add(solicitud)
        session.commit()

    second = client.post("/solicitudes", json={"medio_id": 1})

    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]


def test_create_request_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/solicitudes",
            json={"medio_id": 1},
        )

    assert response.status_code == 401


@pytest.mark.parametrize("medio_id", [0, -1, "no-es-un-id"])
def test_create_request_validates_media_id(
    solicitudes_context: tuple[TestClient, Engine],
    medio_id: int | str,
) -> None:
    client, _ = solicitudes_context

    response = client.post(
        "/solicitudes",
        json={"medio_id": medio_id},
    )

    assert response.status_code == 422

def _prepare_search_results(
    engine: Engine,
    solicitud_id: int,
) -> int:
    """Prepara una solicitud esperando selección y un resultado de prueba."""
    with Session(engine) as session:
        solicitud = session.get(Solicitud, solicitud_id)
        assert solicitud is not None

        solicitud.estado = "esperando_seleccion"
        resultado = ResultadoBusqueda(
            solicitud_id=solicitud_id,
            clave=f"resultado-{solicitud_id}",
            info_hash=f"hash-{solicitud_id}",
            titulo="Película de prueba 1080p",
            indexador="Jackett",
            download_url="https://ejemplo.invalid/descarga",
            magnet_url="magnet:?xt=urn:btih:hash",
            seeders=25,
            peers=5,
            tamano_bytes=2_000_000_000,
            categorias=["peliculas"],
        )
        session.add_all([solicitud, resultado])
        session.commit()
        session.refresh(resultado)

        assert resultado.id is not None
        return resultado.id


def test_list_requests_only_returns_authenticated_profile_requests(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    own_request = client.post("/solicitudes", json={"medio_id": 1})
    assert own_request.status_code == 201

    with Session(engine) as session:
        other_profile = Perfil(nombre="Invitados", pin_hash="otro-hash")
        session.add(other_profile)
        session.commit()
        session.refresh(other_profile)

        session.add(
            Solicitud(
                perfil_id=other_profile.id,
                jellyfin_item_id="jellyfin-otro",
                titulo="Solicitud ajena",
            )
        )
        session.commit()

    response = client.get("/solicitudes")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == own_request.json()["id"]
    assert data[0]["titulo"] == "Película de prueba"


def test_list_results_does_not_expose_download_urls(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    created = client.post("/solicitudes", json={"medio_id": 1})
    assert created.status_code == 201

    solicitud_id = created.json()["id"]
    _prepare_search_results(engine, solicitud_id)

    response = client.get(f"/solicitudes/{solicitud_id}/resultados")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["titulo"] == "Película de prueba 1080p"
    assert data[0]["seeders"] == 25

    forbidden_fields = {"download_url", "magnet_url", "info_hash", "clave"}
    assert forbidden_fields.isdisjoint(data[0])


def test_list_results_serializes_publication_datetime_without_500(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    """Fechas de Jackett pobladas no deben provocar ResponseValidationError."""
    client, engine = solicitudes_context
    created = client.post("/solicitudes", json={"medio_id": 1})
    assert created.status_code == 201
    solicitud_id = created.json()["id"]
    resultado_id = _prepare_search_results(engine, solicitud_id)

    with Session(engine) as session:
        resultado = session.get(ResultadoBusqueda, resultado_id)
        assert resultado is not None
        resultado.publicado_en = datetime(2025, 8, 15, 17, 30, tzinfo=timezone.utc)
        session.add(resultado)
        session.commit()

    response = client.get(f"/solicitudes/{solicitud_id}/resultados")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["publicado_en"].startswith("2025-08-15T17:30:00")
    assert isinstance(data[0]["publicado_en"], str)
    assert {"download_url", "magnet_url", "info_hash", "clave"}.isdisjoint(data[0])


def test_list_results_preserves_and_orders_different_qualities(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    created = client.post(
        "/solicitudes",
        json={"titulo": "Nadie 2", "tipo_medio": "pelicula", "anio": 2025},
    )
    assert created.status_code == 201
    solicitud_id = created.json()["id"]

    with Session(engine) as session:
        solicitud = session.get(Solicitud, solicitud_id)
        assert solicitud is not None
        solicitud.estado = "esperando_seleccion"

        session.add_all(
            [
                ResultadoBusqueda(
                    solicitud_id=solicitud_id,
                    clave="resultado-1080p",
                    info_hash="hash-1080p",
                    titulo="Nadie.2.2025.1080p.WEB-DL.x264.SPANISH",
                    indexador="Jackett",
                    download_url="https://ejemplo.invalid/1080p",
                    magnet_url="magnet:?xt=urn:btih:hash1080p",
                    seeders=80,
                    peers=10,
                    tamano_bytes=2_000_000_000,
                    categorias=["peliculas"],
                ),
                ResultadoBusqueda(
                    solicitud_id=solicitud_id,
                    clave="resultado-4k",
                    info_hash="hash-4k",
                    titulo="Nadie.2.2025.2160p.BluRay.HEVC.SPANISH",
                    indexador="Jackett",
                    download_url="https://ejemplo.invalid/4k",
                    magnet_url="magnet:?xt=urn:btih:hash4k",
                    seeders=15,
                    peers=3,
                    tamano_bytes=8_000_000_000,
                    categorias=["peliculas"],
                ),
            ]
        )
        session.add(solicitud)
        session.commit()

    response = client.get(f"/solicitudes/{solicitud_id}/resultados")

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert [item["resolucion"] for item in data] == ["2160p", "1080p"]
    assert [item["calidad"] for item in data] == ["4K", "Full HD"]
    assert data[0]["seeders"] == 15
    assert data[1]["seeders"] == 80

    forbidden_fields = {"download_url", "magnet_url", "info_hash", "clave"}
    for item in data:
        assert forbidden_fields.isdisjoint(item)


def test_select_result_creates_download_without_sending_it(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    created = client.post("/solicitudes", json={"medio_id": 1})
    assert created.status_code == 201

    solicitud_id = created.json()["id"]
    resultado_id = _prepare_search_results(engine, solicitud_id)

    response = client.post(
        f"/solicitudes/{solicitud_id}/seleccion",
        json={"resultado_id": resultado_id},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["solicitud_id"] == solicitud_id
    assert data["resultado_id"] == resultado_id
    assert data["estado"] == "seleccionada"
    assert "download_url" not in data
    assert "magnet_url" not in data

    with Session(engine) as session:
        solicitud = session.get(Solicitud, solicitud_id)
        assert solicitud is not None
        assert solicitud.estado == "completada"

        descargas = session.exec(
            select(Descarga).where(Descarga.solicitud_id == solicitud_id)
        ).all()
        assert len(descargas) == 1
        assert descargas[0].estado == "seleccionada"
        assert descargas[0].qbittorrent_hash is None


def test_select_result_rejects_result_from_another_request(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    created = client.post("/solicitudes", json={"medio_id": 1})
    assert created.status_code == 201
    solicitud_id = created.json()["id"]

    with Session(engine) as session:
        own_request = session.get(Solicitud, solicitud_id)
        assert own_request is not None
        own_request.estado = "esperando_seleccion"

        other_request = Solicitud(
            perfil_id=1,
            jellyfin_item_id="jellyfin-otro",
            titulo="Otra película",
            estado="esperando_seleccion",
        )
        session.add_all([own_request, other_request])
        session.commit()
        session.refresh(other_request)
        assert other_request.id is not None
        other_solicitud_id = other_request.id

    resultado_id = _prepare_search_results(engine, other_solicitud_id)

    response = client.post(
        f"/solicitudes/{solicitud_id}/seleccion",
        json={"resultado_id": resultado_id},
    )

    assert response.status_code == 404

    with Session(engine) as session:
        assert session.exec(select(Descarga)).all() == []


def test_select_result_rejects_second_selection(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    created = client.post("/solicitudes", json={"medio_id": 1})
    assert created.status_code == 201

    solicitud_id = created.json()["id"]
    resultado_id = _prepare_search_results(engine, solicitud_id)

    first = client.post(
        f"/solicitudes/{solicitud_id}/seleccion",
        json={"resultado_id": resultado_id},
    )
    second = client.post(
        f"/solicitudes/{solicitud_id}/seleccion",
        json={"resultado_id": resultado_id},
    )

    assert first.status_code == 201
    assert second.status_code == 409

    with Session(engine) as session:
        descargas = session.exec(
            select(Descarga).where(Descarga.solicitud_id == solicitud_id)
        ).all()
        assert len(descargas) == 1

def test_create_manual_request_without_jellyfin(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    response = client.post(
        "/solicitudes",
        json={
            "titulo": "Nadie 2",
            "tipo_medio": "pelicula",
            "anio": 2025,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["titulo"] == "Nadie 2"
    assert data["medio_id"] is None
    assert data["estado"] == "pendiente"

    with Session(engine) as session:
        saved = session.get(Solicitud, data["id"])
        assert saved is not None
        assert saved.jellyfin_item_id is None
        assert saved.titulo == "Nadie 2"
        assert saved.tipo_medio == "pelicula"
        assert saved.anio == 2025
        assert saved.perfil_id == 1


def test_create_manual_request_rejects_active_duplicate(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context
    payload = {
        "titulo": "Nadie 2",
        "tipo_medio": "pelicula",
        "anio": 2025,
    }

    first = client.post("/solicitudes", json=payload)
    second = client.post(
        "/solicitudes",
        json={**payload, "titulo": "  NADIE 2  "},
    )

    assert first.status_code == 201
    assert second.status_code == 409

    with Session(engine) as session:
        requests = session.exec(
            select(Solicitud).where(Solicitud.jellyfin_item_id.is_(None))
        ).all()
        assert len(requests) == 1


def test_create_manual_request_is_scoped_to_profile(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    first = client.post(
        "/solicitudes",
        json={
            "titulo": "Nadie 2",
            "tipo_medio": "pelicula",
            "anio": 2025,
        },
    )
    assert first.status_code == 201

    with Session(engine) as session:
        other_profile = Perfil(nombre="Invitados", pin_hash="otro-hash")
        session.add(other_profile)
        session.commit()
        session.refresh(other_profile)

        other_request = Solicitud(
            perfil_id=other_profile.id,
            jellyfin_item_id=None,
            titulo="Nadie 2",
            tipo_medio="pelicula",
            anio=2025,
        )
        session.add(other_request)
        session.commit()

        assert other_request.id is not None


def test_create_manual_request_allows_retry_after_failure(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context
    payload = {
        "titulo": "Nadie 2",
        "tipo_medio": "pelicula",
        "anio": 2025,
    }

    first = client.post("/solicitudes", json=payload)
    assert first.status_code == 201

    with Session(engine) as session:
        solicitud = session.get(Solicitud, first.json()["id"])
        assert solicitud is not None
        solicitud.estado = "fallida"
        session.add(solicitud)
        session.commit()

    second = client.post("/solicitudes", json=payload)

    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"titulo": "Nadie 2"},
        {"tipo_medio": "pelicula", "anio": 2025},
        {"titulo": "   ", "tipo_medio": "pelicula"},
        {"titulo": "Nadie 2", "tipo_medio": "documental"},
        {"titulo": "Nadie 2", "tipo_medio": "pelicula", "anio": 1800},
        {"medio_id": 1, "titulo": "Nadie 2", "tipo_medio": "pelicula"},
    ],
)
def test_create_manual_request_validates_payload(
    solicitudes_context: tuple[TestClient, Engine],
    payload: dict[str, object],
) -> None:
    client, _ = solicitudes_context

    response = client.post("/solicitudes", json=payload)

    assert response.status_code == 422

def test_list_activas_hides_terminal_history_without_deleting(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context
    created = client.post("/solicitudes", json={"medio_id": 1})
    assert created.status_code == 201
    rid = created.json()["id"]
    with Session(engine) as session:
        item = session.get(Solicitud, rid)
        assert item is not None
        item.estado = "completada"
        session.add(item)
        session.commit()
    assert client.get("/solicitudes?solo_activas=true").json() == []
    all_items = client.get("/solicitudes").json()
    assert len(all_items) == 1
    assert all_items[0]["estado"] == "completada"


def test_unrelated_episode_cannot_be_shown_or_selected(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context
    created = client.post(
        "/solicitudes",
        json={"titulo": "Nadie 2", "tipo_medio": "pelicula"},
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    with Session(engine) as session:
        item = session.get(Solicitud, rid)
        assert item is not None
        item.estado = "esperando_seleccion"
        session.add(item)
        wrong = ResultadoBusqueda(
            solicitud_id=rid,
            clave="serie-erronea",
            titulo="Cuando.nadie.nos.ve.S01E01.HDTV.720p.SPANISH",
            indexador="indexador-ficticio",
            download_url="https://example.invalid/not-relevant",
        )
        good = ResultadoBusqueda(
            solicitud_id=rid,
            clave="coincidencia-buena",
            titulo="Nadie.2.2025.1080p.WEB.SPANISH",
            indexador="indexador-ficticio",
            download_url="https://example.invalid/match",
        )
        session.add_all([wrong, good])
        session.commit()
        session.refresh(wrong)
        session.refresh(good)
        wrong_id, good_id = wrong.id, good.id

    response = client.get(f"/solicitudes/{rid}/resultados")
    assert response.status_code == 200
    assert [x["id"] for x in response.json()] == [good_id]

    rejected = client.post(
        f"/solicitudes/{rid}/seleccion",
        json={"resultado_id": wrong_id},
    )
    assert rejected.status_code == 409
    with Session(engine) as session:
        assert session.exec(select(Descarga)).all() == []
    accepted = client.post(
        f"/solicitudes/{rid}/seleccion",
        json={"resultado_id": good_id},
    )
    assert accepted.status_code == 201


def test_undo_selected_is_safe_and_idempotent(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context
    created = client.post("/solicitudes", json={"medio_id": 1})
    rid = created.json()["id"]
    result_id = _prepare_search_results(engine, rid)
    selected = client.post(
        f"/solicitudes/{rid}/seleccion", json={"resultado_id": result_id},
    )
    assert selected.status_code == 201
    did = selected.json()["id"]
    undone = client.post(f"/solicitudes/descargas/{did}/deshacer-seleccion")
    assert undone.status_code == 200
    assert undone.json()["solicitud_id"] == rid
    assert client.get("/solicitudes/descargas").json()["total"] == 0
    assert client.get("/solicitudes?solo_activas=true").json()[0]["estado"] == "esperando_seleccion"
    assert client.post(f"/solicitudes/descargas/{did}/deshacer-seleccion").status_code == 404
    assert client.get(f"/solicitudes/{rid}/resultados").json()[0]["id"] == result_id


def test_undo_refuses_download_with_attempt(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context
    rid = client.post("/solicitudes", json={"medio_id": 1}).json()["id"]
    result_id = _prepare_search_results(engine, rid)
    did = client.post(
        f"/solicitudes/{rid}/seleccion", json={"resultado_id": result_id},
    ).json()["id"]
    with Session(engine) as session:
        download = session.get(Descarga, did)
        assert download is not None
        download.intentos_envio = 1
        session.add(download)
        session.commit()
    assert client.post(f"/solicitudes/descargas/{did}/deshacer-seleccion").status_code == 409
    with Session(engine) as session:
        assert session.get(Descarga, did) is not None


def test_undo_requires_correct_profile(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context
    rid = client.post("/solicitudes", json={"medio_id": 1}).json()["id"]
    result_id = _prepare_search_results(engine, rid)
    did = client.post(
        f"/solicitudes/{rid}/seleccion", json={"resultado_id": result_id},
    ).json()["id"]
    with Session(engine) as session:
        session.add(Perfil(nombre="Otro", pin_hash="ficticio"))
        session.commit()
    original = app.dependency_overrides[get_current_profile]
    def other_profile():
        with Session(engine) as session:
            return session.get(Perfil, 2)
    app.dependency_overrides[get_current_profile] = other_profile
    try:
        assert client.post(f"/solicitudes/descargas/{did}/deshacer-seleccion").status_code == 404
    finally:
        app.dependency_overrides[get_current_profile] = original
    with Session(engine) as session:
        assert session.get(Descarga, did) is not None


def _prepare_discardable_download(client: TestClient, engine: Engine) -> int:
    rid = client.post("/solicitudes", json={"medio_id": 1}).json()["id"]
    with Session(engine) as session:
        request = session.get(Solicitud, rid)
        assert request is not None
        request.estado = "completada"
        session.add(request)
        download = Descarga(
            solicitud_id=rid,
            titulo="Archivo que el usuario descartó",
            estado="enviada",
            inicio_estado="pendiente",
            qbittorrent_hash="a" * 40,
            progreso=0,
        )
        session.add(download)
        session.commit()
        session.refresh(download)
        return download.id


class _FakeQbitForDiscard:
    def __init__(self, *, matches_hash=None, matches_tag=None, error=None):
        self.matches_hash = matches_hash or []
        self.matches_tag = matches_tag or []
        self.error = error
        self.calls = []

    def torrents_info(self, hashes=None, *, tag=None):
        self.calls.append(("hash" if hashes is not None else "tag", tag))
        if self.error:
            raise self.error
        return self.matches_hash if hashes is not None else self.matches_tag


def test_discard_wrong_selection_preserves_history_and_hides_download(
    solicitudes_context: tuple[TestClient, Engine], monkeypatch,
) -> None:
    import app.solicitudes as routes

    client, engine = solicitudes_context
    did = _prepare_discardable_download(client, engine)
    qbit = _FakeQbitForDiscard()
    monkeypatch.setattr(routes, "QBittorrentClient", lambda: qbit)

    assert client.get("/solicitudes/descargas").json()["total"] == 1
    response = client.post(f"/solicitudes/descargas/{did}/descartar-incorrecta")
    assert response.status_code == 200
    assert response.json() == {"id": did, "estado": "descartada"}
    assert qbit.calls == [("hash", None), ("tag", f"viewtv-descarga-{did}")]

    assert client.get("/solicitudes/descargas").json()["total"] == 0
    history = client.get("/solicitudes/descargas?incluir_descartadas=true").json()
    assert history["total"] == 1
    assert history["elementos"][0]["estado"] == "fallida"
    assert client.get("/solicitudes?solo_activas=true").json() == []

    with Session(engine) as session:
        download = session.get(Descarga, did)
        request = session.get(Solicitud, download.solicitud_id)
        assert download.inicio_estado == "requiere_revision"
        assert download.qbittorrent_hash == "a" * 40
        assert request.estado == "cancelada"

    assert client.post(f"/solicitudes/descargas/{did}/descartar-incorrecta").status_code == 409


@pytest.mark.parametrize("where", ["hash", "tag"])
def test_discard_refuses_existing_qbit_torrent(
    solicitudes_context: tuple[TestClient, Engine], monkeypatch, where,
) -> None:
    import app.solicitudes as routes

    client, engine = solicitudes_context
    did = _prepare_discardable_download(client, engine)
    qbit = _FakeQbitForDiscard(
        matches_hash=[{"hash": "a" * 40}] if where == "hash" else [],
        matches_tag=[{"hash": "a" * 40}] if where == "tag" else [],
    )
    monkeypatch.setattr(routes, "QBittorrentClient", lambda: qbit)
    response = client.post(f"/solicitudes/descargas/{did}/descartar-incorrecta")
    assert response.status_code == 409
    assert client.get("/solicitudes/descargas").json()["total"] == 1


def test_discard_refuses_qbit_connection_error(
    solicitudes_context: tuple[TestClient, Engine], monkeypatch,
) -> None:
    import app.solicitudes as routes
    from app.qbittorrent import QBittorrentError

    client, engine = solicitudes_context
    did = _prepare_discardable_download(client, engine)
    monkeypatch.setattr(routes, "QBittorrentClient", lambda: _FakeQbitForDiscard(
        error=QBittorrentError("Simulación sin conexión")
    ))
    response = client.post(f"/solicitudes/descargas/{did}/descartar-incorrecta")
    assert response.status_code == 503
    assert client.get("/solicitudes/descargas").json()["total"] == 1


@pytest.mark.parametrize("field,value", [
    ("progreso", 0.1),
    ("inicio_intentos", 1),
    ("inicio_estado", "iniciada"),
    ("estado", "descargando"),
])
def test_discard_refuses_download_with_activity(
    solicitudes_context: tuple[TestClient, Engine], monkeypatch, field, value,
) -> None:
    import app.solicitudes as routes

    client, engine = solicitudes_context
    did = _prepare_discardable_download(client, engine)
    with Session(engine) as session:
        item = session.get(Descarga, did)
        setattr(item, field, value)
        session.add(item)
        session.commit()
    qbit = _FakeQbitForDiscard()
    monkeypatch.setattr(routes, "QBittorrentClient", lambda: qbit)
    response = client.post(f"/solicitudes/descargas/{did}/descartar-incorrecta")
    assert response.status_code == 409
    assert qbit.calls == []


def test_discard_requires_owner_profile(
    solicitudes_context: tuple[TestClient, Engine], monkeypatch,
) -> None:
    import app.solicitudes as routes

    client, engine = solicitudes_context
    did = _prepare_discardable_download(client, engine)
    with Session(engine) as session:
        session.add(Perfil(nombre="Segundo", pin_hash="ficticio"))
        session.commit()
    original = app.dependency_overrides[get_current_profile]

    def other_profile():
        with Session(engine) as session:
            return session.get(Perfil, 2)

    app.dependency_overrides[get_current_profile] = other_profile
    qbit = _FakeQbitForDiscard()
    monkeypatch.setattr(routes, "QBittorrentClient", lambda: qbit)
    try:
        assert client.post(f"/solicitudes/descargas/{did}/descartar-incorrecta").status_code == 404
        assert qbit.calls == []
    finally:
        app.dependency_overrides[get_current_profile] = original


def _preparar_resultado_jackett_verificable(client, engine):
    import app.solicitudes as routes
    from types import SimpleNamespace

    created = client.post("/solicitudes", json={"medio_id": 1})
    assert created.status_code == 201
    solicitud_id = created.json()["id"]
    resultado_id = _prepare_search_results(engine, solicitud_id)
    with Session(engine) as session:
        result = session.get(ResultadoBusqueda, resultado_id)
        result.download_url = "http://host.docker.internal:9117/dl/fixture?key=ficticia"
        result.magnet_url = None
        result.tamano_bytes = 20 * 1024**3
        session.add(result)
        session.commit()
    return solicitud_id, resultado_id


def test_preselection_uses_real_size_even_when_jackett_is_wrong(
    solicitudes_context, monkeypatch
):
    import app.solicitudes as routes
    from types import SimpleNamespace
    from worker.torrent_metadata import TorrentMetadata

    client, engine = solicitudes_context
    sid, rid = _preparar_resultado_jackett_verificable(client, engine)
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(
        jackett_base_url="http://host.docker.internal:9117"
    ))
    lookups = []
    def fake_metadata(url, base):
        lookups.append((url, base))
        return TorrentMetadata(33_260_748_236, "b" * 40)
    monkeypatch.setattr(routes, "obtener_metadatos_jackett", fake_metadata)

    preview = client.get(f"/solicitudes/{sid}/resultados/{rid}/verificacion")
    assert preview.status_code == 200
    data = preview.json()
    assert data["estado"] == "apto"
    assert data["puede_seleccionar"] is True
    assert data["tamano_anunciado_bytes"] == 20 * 1024**3
    assert data["tamano_real_bytes"] == 33_260_748_236
    assert any("Jackett" in message for message in data["advertencias"])
    assert all(x not in data for x in ("info_hash", "download_url", "magnet_url", "clave"))
    assert "http" not in str(data)
    response = client.post(f"/solicitudes/{sid}/seleccion", json={"resultado_id": rid})
    assert response.status_code == 201
    assert len(lookups) == 2
    with Session(engine) as session:
        assert session.get(Solicitud, sid).estado == "completada"
        d = session.exec(select(Descarga).where(Descarga.solicitud_id == sid)).one()
        assert d.estado == "seleccionada"
        assert d.tamano_bytes == 33_260_748_236
        assert d.info_hash == "b" * 40
        assert d.qbittorrent_hash is None
        assert d.intentos_envio == 0


def test_preselection_blocks_previous_discard_by_same_profile(
    solicitudes_context, monkeypatch
):
    import app.solicitudes as routes
    from types import SimpleNamespace
    from worker.torrent_metadata import TorrentMetadata

    client, engine = solicitudes_context
    sid, rid = _preparar_resultado_jackett_verificable(client, engine)
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(
        jackett_base_url="http://host.docker.internal:9117"
    ))
    monkeypatch.setattr(
        routes, "obtener_metadatos_jackett",
        lambda u, b: TorrentMetadata(20 * 1024**3, "c" * 40),
    )
    with Session(engine) as session:
        historic = Solicitud(perfil_id=1, titulo="Antigua prueba", estado="cancelada")
        session.add(historic)
        session.flush()
        session.add(Descarga(
            solicitud_id=historic.id,
            titulo="Archivo descartado",
            estado="fallida",
            qbittorrent_hash="c" * 40,
        ))
        session.commit()

    response = client.get(f"/solicitudes/{sid}/resultados/{rid}/verificacion")
    assert response.status_code == 200
    assert response.json()["estado"] == "bloqueado"
    assert response.json()["tamano_real_bytes"] == 20 * 1024**3
    assert any("descartaste" in m for m in response.json()["advertencias"])
    assert client.post(f"/solicitudes/{sid}/seleccion", json={"resultado_id": rid}).status_code == 409


def test_preselection_allows_matching_size_only_after_own_verification(
    solicitudes_context, monkeypatch
):
    import app.solicitudes as routes
    from types import SimpleNamespace
    from worker.torrent_metadata import TorrentMetadata

    client, engine = solicitudes_context
    sid, rid = _preparar_resultado_jackett_verificable(client, engine)
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(
        jackett_base_url="http://host.docker.internal:9117"
    ))
    calls = []
    def fake_metadata(url, base):
        calls.append("GET")
        return TorrentMetadata(20 * 1024**3, "d" * 40)
    monkeypatch.setattr(routes, "obtener_metadatos_jackett", fake_metadata)
    preview = client.get(f"/solicitudes/{sid}/resultados/{rid}/verificacion")
    assert preview.status_code == 200
    assert preview.json()["estado"] == "apto"
    assert preview.json()["advertencias"] == []
    assert preview.json()["puede_seleccionar"] is True
    chosen = client.post(f"/solicitudes/{sid}/seleccion", json={"resultado_id": rid})
    assert chosen.status_code == 201
    assert calls == ["GET", "GET"]
    with Session(engine) as session:
        d = session.exec(select(Descarga).where(Descarga.solicitud_id == sid)).one()
        assert d.estado == "seleccionada"
        assert d.tamano_bytes == 20 * 1024**3
        assert d.info_hash == "d" * 40
        assert d.qbittorrent_hash is None
        assert d.intentos_envio == 0


def test_preselection_unknown_source_never_fetches_foreign_urls(
    solicitudes_context, monkeypatch
):
    import app.solicitudes as routes
    client, engine = solicitudes_context
    sid = client.post("/solicitudes", json={"medio_id": 1}).json()["id"]
    rid = _prepare_search_results(engine, sid)
    def forbidden(*a, **kw):
        raise AssertionError("URL no autorizada no debe consultarse")
    monkeypatch.setattr(routes, "obtener_metadatos_jackett", forbidden)
    data = client.get(f"/solicitudes/{sid}/resultados/{rid}/verificacion").json()
    assert data["estado"] == "no_verificable"
    assert data["puede_seleccionar"] is False
    assert data["tamano_real_bytes"] is None


def test_preselection_jackett_temporarily_unavailable_is_fail_closed(
    solicitudes_context, monkeypatch
):
    import app.solicitudes as routes
    from types import SimpleNamespace
    from worker.torrent_metadata import TorrentMetadataError

    client, engine = solicitudes_context
    sid, rid = _preparar_resultado_jackett_verificable(client, engine)
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(
        jackett_base_url="http://host.docker.internal:9117"
    ))
    def offline(*args):
        raise TorrentMetadataError("offline")
    monkeypatch.setattr(routes, "obtener_metadatos_jackett", offline)
    preview = client.get(f"/solicitudes/{sid}/resultados/{rid}/verificacion")
    assert preview.status_code == 200
    assert preview.json()["estado"] == "no_verificable"
    assert client.post(f"/solicitudes/{sid}/seleccion", json={"resultado_id": rid}).status_code == 409


def test_preselection_is_private_and_only_for_waiting_selection(
    solicitudes_context, monkeypatch
):
    import app.solicitudes as routes
    client, engine = solicitudes_context
    sid, rid = _preparar_resultado_jackett_verificable(client, engine)
    preview_url = f"/solicitudes/{sid}/resultados/{rid}/verificacion"
    assert client.get(f"/solicitudes/{sid}/resultados/99999/verificacion").status_code == 404
    with Session(engine) as session:
        other = Perfil(nombre="Otro perfil", pin_hash="ficticio")
        session.add(other)
        session.commit()
        session.refresh(other)
        other_id = other.id
    original = app.dependency_overrides[get_current_profile]
    def other_profile():
        with Session(engine) as session:
            return session.get(Perfil, other_id)
    app.dependency_overrides[get_current_profile] = other_profile
    try:
        assert client.get(preview_url).status_code == 404
    finally:
        app.dependency_overrides[get_current_profile] = original

    with Session(engine) as session:
        req = session.get(Solicitud, sid)
        req.estado = "completada"
        session.add(req)
        session.commit()
    assert client.get(preview_url).status_code == 409
