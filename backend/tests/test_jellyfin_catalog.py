from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Medio, Perfil


@pytest.fixture
def catalog_client() -> Generator[TestClient, None, None]:
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

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_profile] = override_profile

    with Session(engine) as session:
        session.add_all(
            [
                Medio(
                    jellyfin_id="movie-1",
                    tipo="pelicula",
                    titulo="Aventura",
                    anio=2022,
                    generos=["Aventura"],
                    imagen_portada="/Items/movie-1/Images/Primary",
                ),
                Medio(
                    jellyfin_id="movie-2",
                    tipo="pelicula",
                    titulo="Drama",
                    anio=2024,
                    generos=["Drama"],
                ),
                Medio(
                    jellyfin_id="series-1",
                    tipo="serie",
                    titulo="Misterio",
                    anio=2023,
                    generos=["Misterio"],
                    imagen_fondo="/Items/series-1/Images/Backdrop/0",
                ),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    engine.dispose()


def test_catalog_returns_paged_metadata_and_private_image_routes(
    catalog_client: TestClient,
) -> None:
    response = catalog_client.get("/jellyfin/catalog?limit=1&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["limit"] == 1
    assert data["offset"] == 0
    assert len(data["elementos"]) == 1
    assert data["elementos"][0]["titulo"] == "Aventura"
    assert data["elementos"][0]["imagen_portada"] == (
        f"/jellyfin/media/{data['elementos'][0]['id']}/images/primary"
    )
    assert "jellyfin_id" not in data["elementos"][0]


def test_catalog_filters_by_media_type_and_omits_missing_images(
    catalog_client: TestClient,
) -> None:
    response = catalog_client.get("/jellyfin/catalog?tipo=pelicula")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert [item["titulo"] for item in data["elementos"]] == ["Aventura", "Drama"]
    assert data["elementos"][1]["imagen_portada"] is None
    assert data["elementos"][1]["imagen_fondo"] is None


def test_catalog_rejects_invalid_pagination(catalog_client: TestClient) -> None:
    assert catalog_client.get("/jellyfin/catalog?limit=0").status_code == 422
    assert catalog_client.get("/jellyfin/catalog?limit=101").status_code == 422
    assert catalog_client.get("/jellyfin/catalog?offset=-1").status_code == 422


def test_catalog_requires_viewtv_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/jellyfin/catalog")

    assert response.status_code == 401
