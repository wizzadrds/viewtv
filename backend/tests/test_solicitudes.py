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
from app.models import Medio, Perfil, Solicitud


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
