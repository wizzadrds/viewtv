"""0053: misma película para todos; el visionado pertenece a un solo perfil.

Todo en SQLite en memoria: no se toca Jellyfin real, NTFS ni torrents.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Medio, PeliculaVista, Perfil, SolicitudRetirada


@pytest.fixture
def perfiles_0053() -> Generator[tuple[TestClient, object, dict], None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Perfil(nombre="Perfil A", pin_hash="solo-test"),
            Perfil(nombre="Perfil B", pin_hash="solo-test"),
            Medio(jellyfin_id="pelicula-compartida", tipo="pelicula",
                  titulo="Película compartida", anio=2025),
            Medio(jellyfin_id="serie-compartida", tipo="serie",
                  titulo="Serie compartida", anio=2025),
        ])
        db.commit()

    current = {"id": 1}

    def fake_profile() -> Perfil:
        with Session(engine) as session:
            profile = session.get(Perfil, current["id"])
            assert profile is not None
            return profile

    def fake_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    keys = [get_current_profile, get_session]
    prior = {key: app.dependency_overrides.get(key) for key in keys}
    app.dependency_overrides[get_current_profile] = fake_profile
    app.dependency_overrides[get_session] = fake_session
    try:
        with TestClient(app) as client:
            yield client, engine, current
    finally:
        for key, previous in prior.items():
            if previous is None:
                app.dependency_overrides.pop(key, None)
            else:
                app.dependency_overrides[key] = previous
        engine.dispose()


def _catalog(client: TestClient, expected_id: int) -> dict:
    response = client.get(f"/jellyfin/catalog?perfil_id_esperado={expected_id}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["vary"] == "Cookie"
    result = response.json()
    assert result["perfil_id"] == expected_id
    return result


def _film(items: dict) -> dict:
    return next(row for row in items["elementos"] if row["tipo"] == "pelicula")


def _mark(client: TestClient, expected_id: int, viewed: bool) -> None:
    response = client.post("/almacenamiento/peliculas/1/visto", json={
        "visto": viewed, "perfil_id_esperado": expected_id,
    })
    assert response.status_code == 200
    assert response.json()["visto"] is viewed


def test_pelicula_permanece_en_ambos_cuando_solo_uno_la_ve(perfiles_0053):
    client, engine, current = perfiles_0053
    initial = _catalog(client, 1)
    assert initial["total"] == 2
    assert _film(initial)["visto"] is False
    _mark(client, 1, True)
    a = _catalog(client, 1)
    assert a["total"] == 2
    assert _film(a)["visto"] is True
    current["id"] = 2
    b = _catalog(client, 2)
    assert b["total"] == 2
    assert {x["id"] for x in a["elementos"]} == {
        x["id"] for x in b["elementos"]
    }
    assert _film(b)["visto"] is False
    with Session(engine) as session:
        assert len(session.exec(select(Medio)).all()) == 2
        rows = session.exec(select(PeliculaVista)).all()
        assert [(r.perfil_id, r.medio_id) for r in rows] == [(1, 1)]
        assert session.exec(select(SolicitudRetirada)).all() == []


def test_los_dos_ven_estado_independiente_sin_retirar_pelicula(perfiles_0053):
    client, engine, current = perfiles_0053
    _mark(client, 1, True)
    current["id"] = 2
    _mark(client, 2, True)
    for profile_id in (1, 2):
        current["id"] = profile_id
        result = _catalog(client, profile_id)
        assert result["total"] == 2
        assert _film(result)["visto"] is True
    _mark(client, 2, False)
    assert _film(_catalog(client, 2))["visto"] is False
    current["id"] = 1
    assert _film(_catalog(client, 1))["visto"] is True
    with Session(engine) as session:
        assert len(session.exec(select(Medio)).all()) == 2
        assert [(r.perfil_id, r.medio_id) for r in
                session.exec(select(PeliculaVista)).all()] == [(1, 1)]


def test_ver_pelicula_no_registra_automaticamente_retirada(perfiles_0053):
    client, engine, _ = perfiles_0053
    _mark(client, 1, True)
    _mark(client, 1, True)
    with Session(engine) as session:
        assert session.exec(select(SolicitudRetirada)).all() == []
        assert len(session.exec(select(Medio)).all()) == 2


def test_solicitar_retirada_en_un_perfil_no_la_oculta_en_el_otro(perfiles_0053):
    client, engine, current = perfiles_0053
    _mark(client, 1, True)
    response = client.post("/almacenamiento/peliculas/1/retirada", json={
        "titulo": "Película compartida", "perfil_id_esperado": 1,
    })
    assert response.status_code == 202
    assert response.json()["estado"] == "pendiente_revision"
    assert _film(_catalog(client, 1))["visto"] is True
    current["id"] = 2
    assert _film(_catalog(client, 2))["visto"] is False
    other = client.get("/almacenamiento/peliculas?perfil_id_esperado=2")
    assert other.status_code == 200
    assert other.headers["cache-control"] == "private, no-store"
    assert other.headers["vary"] == "Cookie"
    assert other.json()["total"] == 1
    assert other.json()["elementos"][0]["solicitud_retirada"] is None
    with Session(engine) as session:
        assert session.get(Medio, 1) is not None


@pytest.mark.parametrize("endpoint", (
    "/jellyfin/catalog?perfil_id_esperado=2",
    "/almacenamiento/peliculas?perfil_id_esperado=2",
))
def test_cambio_cookie_entre_pestanas_no_revela_estado_ajeno(
    perfiles_0053, endpoint,
):
    client, _, _ = perfiles_0053
    assert client.get(endpoint).status_code == 409


@pytest.mark.parametrize("viewed", (True, False))
def test_vista_de_otra_pestana_no_cambia_perfil_equivocado(
    perfiles_0053, viewed,
):
    client, engine, current = perfiles_0053
    _mark(client, 1, True)
    current["id"] = 2
    denied = client.post("/almacenamiento/peliculas/1/visto", json={
        "visto": viewed, "perfil_id_esperado": 1,
    })
    assert denied.status_code == 409
    assert _film(_catalog(client, 2))["visto"] is False
    current["id"] = 1
    assert _film(_catalog(client, 1))["visto"] is True
    with Session(engine) as session:
        assert len(session.exec(select(PeliculaVista)).all()) == 1


@pytest.mark.parametrize("bad", ("1", True, 0, -1, None))
def test_marca_esperada_no_admite_tipo_falso_o_valor_invalido(
    perfiles_0053, bad,
):
    client, engine, _ = perfiles_0053
    status = client.post("/almacenamiento/peliculas/1/visto", json={
        "visto": True, "perfil_id_esperado": bad,
    })
    if bad is None:
        assert status.status_code == 200
    else:
        assert status.status_code == 422
    with Session(engine) as session:
        assert len(session.exec(select(PeliculaVista)).all()) == (
            1 if bad is None else 0
        )


def test_retirada_y_cancelacion_de_otra_pestana_siempre_rechazadas(perfiles_0053):
    client, engine, current = perfiles_0053
    _mark(client, 1, True)
    current["id"] = 2
    denied = client.post("/almacenamiento/peliculas/1/retirada", json={
        "titulo": "Película compartida", "perfil_id_esperado": 1,
    })
    assert denied.status_code == 409
    assert client.delete(
        "/almacenamiento/peliculas/1/retirada?perfil_id_esperado=1",
    ).status_code == 409
    with Session(engine) as session:
        assert session.exec(select(SolicitudRetirada)).all() == []


def test_todas_las_peliculas_del_catalogo_son_compartidas_aun_con_filtro(
    perfiles_0053,
):
    client, _, current = perfiles_0053
    _mark(client, 1, True)
    for profile_id, watched in ((1, True), (2, False)):
        current["id"] = profile_id
        result = client.get(
            f"/jellyfin/catalog?tipo=pelicula&limit=1&perfil_id_esperado={profile_id}"
        )
        assert result.status_code == 200
        assert result.json()["total"] == 1
        assert len(result.json()["elementos"]) == 1
        assert result.json()["elementos"][0]["visto"] is watched


def test_serie_no_hereda_marca_de_pelicula_del_otro_perfil(perfiles_0053):
    client, _, current = perfiles_0053
    _mark(client, 1, True)
    current["id"] = 2
    listing = _catalog(client, 2)
    assert len(listing["elementos"]) == 2
    assert next(x for x in listing["elementos"] if x["tipo"] == "serie")["visto"] is False

def test_playback_no_se_negocia_con_cookie_de_otro_perfil(perfiles_0053):
    client, _, current = perfiles_0053
    current["id"] = 2
    # Rechazar antes de contactar Jellyfin.
    response = client.post(
        "/jellyfin/media/1/playback-info?perfil_id_esperado=1",
    )
    assert response.status_code == 409
    assert "perfil" in response.json()["detail"].lower()


def test_user_data_jellyfin_compartida_no_sustituye_visto_viewtv(
    perfiles_0053, monkeypatch,
):
    client, _, current = perfiles_0053

    class Source:
        def get_items(self, start_index, limit):
            assert start_index == 0
            return {
                "Items": [
                    {
                        "Id": "pelicula-compartida",
                        "Type": "Movie",
                        "Name": "Película compartida",
                        "UserData": {"Played": True, "PlayCount": 5},
                    },
                    {
                        "Id": "serie-compartida",
                        "Type": "Series",
                        "Name": "Serie compartida",
                        "UserData": {"Played": True},
                    },
                ],
                "TotalRecordCount": 2,
            }

    monkeypatch.setattr("app.jellyfin.JellyfinClient", Source)
    assert client.post("/jellyfin/catalog/sync").status_code == 200
    for profile_id in (1, 2):
        current["id"] = profile_id
        data = _catalog(client, profile_id)
        assert data["total"] == 2
        assert _film(data)["visto"] is False
    current["id"] = 1
    _mark(client, 1, True)
    current["id"] = 2
    assert _film(_catalog(client, 2))["visto"] is False
