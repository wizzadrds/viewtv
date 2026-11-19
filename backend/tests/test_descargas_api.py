"""API de lectura de descargas: autorización, privacidad y paginación."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Descarga, Perfil, Solicitud


@pytest.fixture
def contexto() -> Generator[tuple[TestClient, object, dict[str, int]], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        propio = Perfil(nombre="Propio", pin_hash="hash-prueba")
        ajeno = Perfil(nombre="Ajeno", pin_hash="hash-ajeno")
        session.add_all([propio, ajeno])
        session.commit()
        session.refresh(propio)
        session.refresh(ajeno)

        solicitudes = [
            Solicitud(perfil_id=propio.id, titulo="Mía"),
            Solicitud(perfil_id=ajeno.id, titulo="Otra"),
        ]
        session.add_all(solicitudes)
        session.commit()
        for solicitud in solicitudes:
            session.refresh(solicitud)

        registros = [
            Descarga(
                solicitud_id=solicitudes[0].id,
                titulo="Película propia",
                estado="enviada",
                inicio_estado="requiere_revision",
                estado_verificacion="pendiente",
                progreso=0.25,
                qbittorrent_hash="a" * 40,
                ultimo_error="Ruta interna confidencial",
            ),
            Descarga(
                solicitud_id=solicitudes[0].id,
                titulo="Serie propia",
                estado="descargando",
                inicio_estado="iniciada",
                progreso=0.5,
            ),
            Descarga(
                solicitud_id=solicitudes[1].id,
                titulo="Contenido ajeno",
                info_hash="b" * 40,
            ),
        ]
        session.add_all(registros)
        session.commit()
        for registro in registros:
            session.refresh(registro)
        ids = {
            "propio": propio.id,
            "ajeno": ajeno.id,
            "descarga_ajena": registros[2].id,
        }

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def override_profile() -> Perfil:
        with Session(engine) as session:
            return session.get(Perfil, ids["propio"])

    anteriores = {
        get_session: app.dependency_overrides.get(get_session),
        get_current_profile: app.dependency_overrides.get(get_current_profile),
    }
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_profile] = override_profile

    try:
        with TestClient(app) as client:
            yield client, engine, ids
    finally:
        for dependency, previous in anteriores.items():
            if previous is None:
                app.dependency_overrides.pop(dependency, None)
            else:
                app.dependency_overrides[dependency] = previous
        engine.dispose()


def test_descargas_solo_perfil_propietario(contexto) -> None:
    client, _, ids = contexto
    response = client.get("/solicitudes/descargas")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["limit"] == 25
    assert payload["offset"] == 0
    assert len(payload["elementos"]) == 2
    assert ids["descarga_ajena"] not in [
        item["id"] for item in payload["elementos"]
    ]
    assert {item["titulo"] for item in payload["elementos"]} == {
        "Película propia", "Serie propia",
    }


def test_descargas_estado_revision_y_sin_informacion_privada(contexto) -> None:
    client, _, _ = contexto
    response = client.get("/solicitudes/descargas")
    assert response.status_code == 200
    data = response.json()
    item = next(
        row for row in data["elementos"]
        if row["titulo"] == "Película propia"
    )
    assert item["inicio_estado"] == "requiere_revision"
    assert item["estado_verificacion"] == "pendiente"
    assert item["progreso"] == 0.25
    for prohibited in (
        "qbittorrent_hash", "info_hash", "download_url",
        "magnet_url", "ultimo_error", "error_verificacion",
        "inicio_locked_by", "verificacion_locked_by",
    ):
        assert prohibited not in response.text


def test_descargas_paginacion(contexto) -> None:
    client, _, _ = contexto
    first = client.get("/solicitudes/descargas?limit=1&offset=0")
    second = client.get("/solicitudes/descargas?limit=1&offset=1")
    assert first.status_code == second.status_code == 200
    assert first.json()["total"] == second.json()["total"] == 2
    assert len(first.json()["elementos"]) == 1
    assert len(second.json()["elementos"]) == 1
    assert first.json()["elementos"][0]["id"] != second.json()["elementos"][0]["id"]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=abc"])
def test_descargas_rechaza_paginacion_invalida(contexto, query: str) -> None:
    client, _, _ = contexto
    assert client.get(f"/solicitudes/descargas?{query}").status_code == 422


def test_descargas_requiere_autenticacion() -> None:
    # La dependencia del perfil debe comprobar la cookie cuando no hay override.
    previous = app.dependency_overrides.pop(get_current_profile, None)
    try:
        with TestClient(app) as client:
            assert client.get("/solicitudes/descargas").status_code == 401
    finally:
        if previous is not None:
            app.dependency_overrides[get_current_profile] = previous


def test_descargas_cambia_de_perfil_no_muestra_anteriores(contexto) -> None:
    client, engine, ids = contexto

    def otro_perfil() -> Perfil:
        with Session(engine) as session:
            return session.get(Perfil, ids["ajeno"])

    app.dependency_overrides[get_current_profile] = otro_perfil
    response = client.get("/solicitudes/descargas")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["elementos"][0]["id"] == ids["descarga_ajena"]
    assert "Película propia" not in response.text
