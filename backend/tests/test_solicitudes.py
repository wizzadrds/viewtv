"""Pruebas del endpoint autenticado de creación de solicitudes."""

from collections.abc import Generator

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


def test_list_results_preserves_and_orders_different_qualities(
    solicitudes_context: tuple[TestClient, Engine],
) -> None:
    client, engine = solicitudes_context

    created = client.post("/solicitudes", json={"medio_id": 1})
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
