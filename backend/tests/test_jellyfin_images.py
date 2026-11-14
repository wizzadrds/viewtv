from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import jellyfin as jellyfin_module
from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Medio, Perfil


@pytest.fixture
def image_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def override_profile() -> Perfil:
        return Perfil(id=1, nombre="Adultos", pin_hash="test-hash")

    class FakeJellyfinClient:
        def get_image(self, jellyfin_id: str, image_kind: str) -> tuple[bytes, str]:
            assert jellyfin_id == "jf-movie-1"
            assert image_kind == "primary"
            return b"fake-jpeg", "image/jpeg"

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_profile] = override_profile
    monkeypatch.setattr(jellyfin_module, "JellyfinClient", FakeJellyfinClient)

    with Session(engine) as session:
        session.add(
            Medio(
                jellyfin_id="jf-movie-1",
                tipo="pelicula",
                titulo="Película de prueba",
                imagen_portada="/Items/jf-movie-1/Images/Primary",
            )
        )
        session.commit()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    engine.dispose()


def test_image_endpoint_returns_image_without_upstream_credentials(
    image_client: TestClient,
) -> None:
    response = image_client.get("/jellyfin/media/1/images/primary")

    assert response.status_code == 200
    assert response.content == b"fake-jpeg"
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "private, max-age=3600"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "authorization" not in response.headers


def test_image_endpoint_requires_viewtv_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/jellyfin/media/1/images/primary")

    assert response.status_code == 401


def test_image_endpoint_returns_404_when_media_has_no_image(
    image_client: TestClient,
) -> None:
    response = image_client.get("/jellyfin/media/1/images/backdrop")

    assert response.status_code == 404

