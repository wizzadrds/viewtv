from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.auth import hash_pin
from app.config import get_settings
from app.database import get_session
from app.main import app
from app.models import Perfil


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("JWT_SECRET", "test-secret-that-is-at-least-32-bytes-long")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with Session(engine) as session:
        session.add(Perfil(nombre="Adultos", pin_hash=hash_pin("1234")))
        session.commit()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def test_profiles_endpoint_only_exposes_active_profile_names(client: TestClient) -> None:
    response = client.get("/auth/profiles")

    assert response.status_code == 200
    assert response.json() == {"perfiles": [{"id": 1, "nombre": "Adultos"}]}
    assert "pin_hash" not in response.text


def test_profiles_endpoint_only_exposes_active_profile_names(client: TestClient) -> None:
    response = client.get("/auth/profiles")

    assert response.status_code == 200
    assert response.json() == {"perfiles": [{"id": 1, "nombre": "Adultos"}]}
    assert "pin_hash" not in response.text


def test_login_sets_http_only_cookie_and_me_returns_profile(client: TestClient) -> None:
    response = client.post("/auth/login", json={"nombre": "Adultos", "pin": "1234"})

    assert response.status_code == 200
    assert response.json()["perfil"]["nombre"] == "Adultos"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert client.get("/auth/me").json() == {"id": 1, "nombre": "Adultos"}


def test_wrong_pin_and_unknown_profile_have_same_error(client: TestClient) -> None:
    wrong_pin = client.post("/auth/login", json={"nombre": "Adultos", "pin": "9999"})
    unknown_profile = client.post("/auth/login", json={"nombre": "No existe", "pin": "9999"})

    assert wrong_pin.status_code == unknown_profile.status_code == 401
    assert wrong_pin.json() == unknown_profile.json()


def test_logout_removes_session_cookie(client: TestClient) -> None:
    client.post("/auth/login", json={"nombre": "Adultos", "pin": "1234"})

    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401


def test_pin_hash_is_not_plain_text() -> None:
    hashed = hash_pin("4321")

    assert hashed != "4321"
    assert hashed.startswith("$argon2")



def test_settings_read_documented_environment_variable_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIEWTV_ENV", "test")
    monkeypatch.setenv("VIEWTV_TIMEZONE", "Atlantic/Canary")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.environment == "test"
    assert settings.timezone == "Atlantic/Canary"
    get_settings.cache_clear()
