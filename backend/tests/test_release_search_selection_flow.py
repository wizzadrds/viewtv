"""Recorrido de salida VIEWTV con Jackett ficticio, SQLite en memoria y API real.

No toca perfiles productivos, proveedores reales, qBittorrent ni NTFS.
"""

from collections.abc import Generator

import httpx
import pytest
import worker.processor as processor
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.auth import get_current_profile
from app.config import Settings
from app.database import get_session
from app.jackett import JackettClient
from app.main import app
from app.models import Descarga, Perfil, ResultadoBusqueda, Solicitud

XML_TWO_RESULTS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:torznab="http://torznab.com/schemas/2015/feed">
 <channel>
  <item>
   <title>Contenido ficticio 1080p WEB</title>
   <enclosure url="https://ejemplo.invalid/descarga-fixture-1"
       type="application/x-bittorrent" length="1000000000"/>
   <torznab:attr name="seeders" value="20"/>
   <torznab:attr name="infohash"
       value="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/>
   <jackettindexer>indexador-local-de-prueba</jackettindexer>
  </item>
  <item>
   <title>Contenido ficticio 720p</title>
   <enclosure url="https://ejemplo.invalid/descarga-fixture-2"
       type="application/x-bittorrent" length="500000000"/>
   <torznab:attr name="seeders" value="40"/>
   <torznab:attr name="infohash"
       value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"/>
  </item>
 </channel>
</rss>"""


@pytest.fixture
def flow_lab(monkeypatch) -> Generator[tuple[TestClient, Engine], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Perfil(nombre="Perfil ficticio", pin_hash="hash-no-real"))
        session.commit()

    def session_override() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def profile_override() -> Perfil:
        with Session(engine) as session:
            profile = session.get(Perfil, 1)
            assert profile is not None
            return profile

    previous = {
        get_session: app.dependency_overrides.get(get_session),
        get_current_profile: app.dependency_overrides.get(get_current_profile),
    }
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_current_profile] = profile_override
    monkeypatch.setattr(processor, "engine", engine)

    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        for dependency, prior in previous.items():
            if prior is None:
                app.dependency_overrides.pop(dependency, None)
            else:
                app.dependency_overrides[dependency] = prior
        engine.dispose()


def make_fake_jackett(search_requests: list[httpx.Request], xml: bytes) -> JackettClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "jackett-falso.invalid"
        assert request.method == "GET"
        assert request.url.path.endswith("/results/torznab/api")
        search_requests.append(request)
        return httpx.Response(200, request=request, content=xml)

    settings = Settings(
        _env_file=None,
        jackett_base_url="http://jackett-falso.invalid:9117",
        jackett_api_key="clave-ficticia-no-productiva",
    )
    return JackettClient(settings=settings, transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    "media_kind,expected_search", [("pelicula", "movie"), ("serie", "tvsearch")]
)
def test_api_worker_torznab_selection_and_download_tracking(flow_lab, media_kind, expected_search):
    """POST formulario -> worker -> resultados -> POST selección -> GET descargas."""
    client, engine = flow_lab
    created = client.post(
        "/solicitudes",
        json={"titulo": "Contenido ficticio", "tipo_medio": media_kind, "anio": 2026},
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    assert (
        client.post(
            "/solicitudes",
            json={"titulo": " contenido ficticio ", "tipo_medio": media_kind, "anio": 2026},
        ).status_code
        == 409
    )

    search_requests: list[httpx.Request] = []
    jackett = make_fake_jackett(search_requests, XML_TWO_RESULTS)
    assert processor.process_one_request("worker-de-prueba", client=jackett)
    assert len(search_requests) == 1
    assert search_requests[0].url.params["q"] == "Contenido ficticio 2026"
    assert search_requests[0].url.params["t"] == expected_search

    listed = client.get("/solicitudes")
    assert listed.status_code == 200
    assert listed.json()[0]["estado"] == "esperando_seleccion"

    response = client.get(f"/solicitudes/{request_id}/resultados")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    assert [item["resolucion"] for item in results] == ["1080p", "720p"]
    assert {"download_url", "magnet_url", "info_hash", "clave"}.isdisjoint(results[0])

    selected = client.post(
        f"/solicitudes/{request_id}/seleccion",
        json={"resultado_id": results[0]["id"]},
    )
    assert selected.status_code == 201
    assert selected.json()["estado"] == "seleccionada"
    assert (
        client.post(
            f"/solicitudes/{request_id}/seleccion",
            json={"resultado_id": results[1]["id"]},
        ).status_code
        == 409
    )

    downloads = client.get("/solicitudes/descargas?limit=20&offset=0")
    assert downloads.status_code == 200
    assert downloads.json()["total"] == 1
    shown = downloads.json()["elementos"][0]
    assert shown["solicitud_id"] == request_id
    assert shown["estado"] == "seleccionada"
    assert shown["progreso"] == 0
    assert {"info_hash", "magnet_url", "download_url", "clave"}.isdisjoint(shown)

    with Session(engine) as session:
        saved = session.exec(select(Descarga)).all()
        assert len(saved) == 1
        assert saved[0].qbittorrent_hash is None
        assert saved[0].inicio_estado == "no_requerido"
        assert saved[0].intentos_envio == 0
        assert session.get(Solicitud, request_id).estado == "completada"
        assert len(session.exec(select(ResultadoBusqueda)).all()) == 2


def test_no_results_does_not_create_download(flow_lab):
    client, engine = flow_lab
    created = client.post(
        "/solicitudes",
        json={"titulo": "Película ficticia ausente", "tipo_medio": "pelicula"},
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    calls = []
    assert processor.process_one_request(
        "worker-de-prueba", client=make_fake_jackett(calls, b"<rss><channel/></rss>")
    )
    listed = client.get("/solicitudes")
    assert listed.status_code == 200
    assert listed.json()[0]["estado"] == "sin_resultados"
    assert client.get(f"/solicitudes/{request_id}/resultados").status_code == 409
    assert client.get("/solicitudes/descargas").json()["total"] == 0

    with Session(engine) as session:
        assert session.exec(select(Descarga)).all() == []


def test_other_profile_cannot_read_or_select_foreign_results(flow_lab):
    client, engine = flow_lab
    created = client.post(
        "/solicitudes",
        json={"titulo": "Contenido ficticio", "tipo_medio": "pelicula"},
    )
    assert created.status_code == 201
    request_id = created.json()["id"]
    assert processor.process_one_request(
        "worker-de-prueba", client=make_fake_jackett([], XML_TWO_RESULTS)
    )
    with Session(engine) as session:
        result = session.exec(select(ResultadoBusqueda)).first()
        assert result is not None
        result_id = result.id
        session.add(Perfil(nombre="Otro perfil ficticio", pin_hash="no-real"))
        session.commit()

    def other_profile() -> Perfil:
        with Session(engine) as session:
            profile = session.get(Perfil, 2)
            assert profile is not None
            return profile

    previous = app.dependency_overrides[get_current_profile]
    app.dependency_overrides[get_current_profile] = other_profile
    try:
        assert client.get("/solicitudes").json() == []
        assert client.get(f"/solicitudes/{request_id}/resultados").status_code == 404
        assert (
            client.post(
                f"/solicitudes/{request_id}/seleccion",
                json={"resultado_id": result_id},
            ).status_code
            == 404
        )
        assert client.get("/solicitudes/descargas").json()["total"] == 0
    finally:
        app.dependency_overrides[get_current_profile] = previous

    with Session(engine) as session:
        assert session.exec(select(Descarga)).all() == []

def test_worker_filters_unrelated_series_from_film_search(flow_lab):
    client, engine = flow_lab
    created = client.post(
        "/solicitudes", json={"titulo": "Nadie 2", "tipo_medio": "pelicula"},
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    wrong = b"""<rss><channel>
      <item><title>Cuando.nadie.nos.ve.S01E01.HDTV.720p.SPANISH</title>
        <enclosure url="https://fixture.invalid/episode"/></item>
      <item><title>Nadie.2.2025.1080p.WEB.SPANISH</title>
        <enclosure url="https://fixture.invalid/movie"/></item>
    </channel></rss>"""
    assert processor.process_one_request(
        "worker-de-prueba", client=make_fake_jackett([], wrong),
    )
    response = client.get(f"/solicitudes/{rid}/resultados")
    assert response.status_code == 200
    assert [i["titulo"] for i in response.json()] == ["Nadie.2.2025.1080p.WEB.SPANISH"]
    with Session(engine) as session:
        titles = [x.titulo for x in session.exec(select(ResultadoBusqueda)).all()]
        assert titles == ["Nadie.2.2025.1080p.WEB.SPANISH"]


def test_worker_marks_no_results_if_only_unrelated_releases(flow_lab):
    client, engine = flow_lab
    rid = client.post(
        "/solicitudes", json={"titulo": "Nadie 2", "tipo_medio": "pelicula"},
    ).json()["id"]
    wrong = b"""<rss><channel>
      <item><title>Cuando.nadie.nos.ve.S01E01.HDTV.720p.SPANISH</title>
        <enclosure url="https://fixture.invalid/episode"/></item>
    </channel></rss>"""
    assert processor.process_one_request(
        "worker-de-prueba", client=make_fake_jackett([], wrong),
    )
    all_requests = client.get("/solicitudes").json()
    assert all_requests[0]["estado"] == "sin_resultados"
    assert client.get("/solicitudes?solo_activas=true").json() == []
    with Session(engine) as session:
        assert session.exec(select(ResultadoBusqueda)).all() == []
