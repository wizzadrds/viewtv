"""Circuito real de API y worker con SQLite efímera y Jackett simulado.

Ejecución exclusivamente en contenedor sin red, origen de código solo lectura.
No utiliza perfiles, torrents, credenciales ni base SQLite productivos.
"""
from __future__ import annotations

import os

import httpx
from app.auth import get_current_profile
from app.config import Settings
from app.database import get_session
from app.jackett import JackettClient
from app.main import app
from app.models import Descarga, Perfil, ResultadoBusqueda, Solicitud
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from worker import processor

XML = b"""<?xml version="1.0"?>
<rss xmlns:torznab="http://torznab.com/schemas/2015/feed">
  <channel>
    <item>
      <title>Obra ficticia A 1080p</title>
      <enclosure url="https://fixture.invalid/a" type="application/x-bittorrent" length="10000"/>
      <torznab:attr name="infohash" value="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/>
      <torznab:attr name="seeders" value="4"/>
    </item>
    <item>
      <title>Obra ficticia B 720p</title>
      <enclosure url="https://fixture.invalid/b" type="application/x-bittorrent" length="5000"/>
      <torznab:attr name="infohash" value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"/>
      <torznab:attr name="seeders" value="2"/>
    </item>
  </channel>
</rss>"""


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise AssertionError(mensaje)


def main() -> None:
    exigir(os.environ.get("VIEWTV_SEARCH_LAB_ONLY") == "1", "No es entorno aislado")
    exigir(os.environ.get("DATABASE_URL") == "sqlite:///:memory:", "Base no ficticia")
    exigir(os.environ.get("VIEWTV_ENABLE_TORRENT_SUBMIT") == "false", "Alta habilitada")
    exigir(os.environ.get("VIEWTV_ENABLE_DOWNLOAD_START") == "false", "Inicio habilitado")
    exigir(not os.path.exists("/opt/viewtv/data"), "Se ha montado producción")

    lab_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(lab_engine)

    with Session(lab_engine) as session:
        session.add(Perfil(nombre="Perfil falso 1", pin_hash="hash-de-prueba"))
        session.add(Perfil(nombre="Perfil falso 2", pin_hash="hash-de-prueba"))
        session.commit()

    def session_falsa():
        with Session(lab_engine) as session:
            yield session

    perfil_actual = [1]

    def autenticacion_falsa():
        with Session(lab_engine) as session:
            perfil = session.get(Perfil, perfil_actual[0])
            exigir(perfil is not None, "Perfil ficticio inexistente")
            return perfil

    prev_session = app.dependency_overrides.get(get_session)
    prev_profile = app.dependency_overrides.get(get_current_profile)
    prev_engine = processor.engine
    app.dependency_overrides[get_session] = session_falsa
    app.dependency_overrides[get_current_profile] = autenticacion_falsa
    processor.engine = lab_engine

    llamadas = []

    def only_fake(request: httpx.Request) -> httpx.Response:
        exigir(request.method == "GET", "Búsqueda no-GET")
        exigir(request.url.host == "proveedor-ficticio.invalid", "Proveedor externo")
        exigir(request.url.params["t"] == "movie", "Tipo de búsqueda incorrecto")
        exigir(request.url.params["q"] == "Obra ficticia", "Título incorrecto")
        llamadas.append(1)
        return httpx.Response(200, request=request, content=XML)

    fake_jackett = JackettClient(
        settings=Settings(
            _env_file=None,
            jackett_base_url="http://proveedor-ficticio.invalid:9117",
            jackett_api_key="clave-sintetica",
        ),
        transport=httpx.MockTransport(only_fake),
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                "/solicitudes",
                json={"titulo": "Obra ficticia", "tipo_medio": "pelicula"},
            )
            exigir(response.status_code == 201, "No se creó solicitud")
            solicitud = response.json()["id"]
            print("PASS_CREAR_SOLICITUD_FICTICIA")

            exigir(
                processor.process_one_request("trabajador-de-ensayo", client=fake_jackett),
                "No se procesó solicitud",
            )
            exigir(len(llamadas) == 1, "El proveedor ficticio se consultó varias veces")
            listed = client.get("/solicitudes")
            exigir(listed.status_code == 200, "No se pudo listar solicitud")
            exigir(
                any(x["id"] == solicitud and x["estado"] == "esperando_seleccion"
                    for x in listed.json()),
                "No llegó a esperando_seleccion",
            )
            print("PASS_BUSQUEDA_COLA_Y_ESTADO")

            options = client.get(f"/solicitudes/{solicitud}/resultados")
            exigir(options.status_code == 200, "No se pudieron listar resultados")
            items = options.json()
            exigir(len(items) == 2, "Resultado de proveedor no persistido")
            exigir(
                all("download_url" not in x and "magnet_url" not in x for x in items),
                "Filtración de enlaces",
            )
            print("PASS_RESULTADOS_API=2")

            perfil_actual[0] = 2
            exigir(client.get("/solicitudes").json() == [], "Lectura cruzada de perfil")
            exigir(
                client.get(f"/solicitudes/{solicitud}/resultados").status_code == 404,
                "Resultados accesibles desde otro perfil",
            )
            perfil_actual[0] = 1
            print("PASS_AISLAMIENTO_ENTRE_PERFILES")

            chosen = client.post(
                f"/solicitudes/{solicitud}/seleccion",
                json={"resultado_id": items[0]["id"]},
            )
            exigir(chosen.status_code == 201, "Selección rechazada")
            exigir(chosen.json()["estado"] == "seleccionada", "Estado inesperado")
            print("PASS_SELECCION")

            tracking = client.get("/solicitudes/descargas")
            exigir(tracking.status_code == 200, "No disponible seguimiento")
            exigir(tracking.json()["total"] == 1, "Seguimiento no muestra la descarga")
            shown = tracking.json()["elementos"][0]
            exigir(shown["estado"] == "seleccionada", "Estado en PWA inesperado")
            exigir(shown["progreso"] == 0, "Progreso simulado incorrecto")
            with Session(lab_engine) as session:
                saved = session.exec(select(Descarga)).all()
                exigir(len(saved) == 1, "Se creó más de una descarga")
                exigir(saved[0].qbittorrent_hash is None, "Se usó qBittorrent")
                exigir(saved[0].intentos_envio == 0, "Se intentó envío")
                exigir(len(session.exec(select(ResultadoBusqueda)).all()) == 2,
                        "Resultados no persistidos en SQLite ficticia")
                exigir(session.get(Solicitud, solicitud).estado == "completada",
                        "Solicitud no cerrada")
            print("PASS_SEGUIMIENTO_SIN_ENVIO")
            print("CIRCUITO_API_FICTICIO=6_PASS")
    finally:
        processor.engine = prev_engine
        for dependency, previous in (
            (get_session, prev_session),
            (get_current_profile, prev_profile),
        ):
            if previous is None:
                app.dependency_overrides.pop(dependency, None)
            else:
                app.dependency_overrides[dependency] = previous
        lab_engine.dispose()


if __name__ == "__main__":
    main()
