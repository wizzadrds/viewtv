"""Regresión HTTP 500 de /solicitudes/{id}/resultados, sin producción.

Contenedor sin red, sin volúmenes de datos y con SQLite en memoria.
"""
from datetime import datetime, timezone
import os

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Perfil, ResultadoBusqueda, Solicitud


def main():
    assert os.getenv("VIEWTV_FECHAS_SANDBOX") == "1"
    assert os.getenv("DATABASE_URL") == "sqlite:///:memory:"
    assert os.getenv("VIEWTV_ENABLE_TORRENT_SUBMIT") == "false"
    assert os.getenv("VIEWTV_ENABLE_DOWNLOAD_START") == "false"
    assert not os.path.exists("/opt/viewtv/data"), "Volumen de producción montado"

    engine = create_engine(
        "sqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Perfil(nombre="Perfil de laboratorio", pin_hash="ficticio"))
        session.commit()
        request = Solicitud(
            perfil_id=1, titulo="Película ficticia", tipo_medio="pelicula",
            estado="esperando_seleccion",
        )
        session.add(request)
        session.commit()
        session.refresh(request)
        sid = request.id
        for key, date in (
            ("con_fecha", datetime(2025, 8, 15, 17, 30, tzinfo=timezone.utc)),
            ("sin_fecha", None),
        ):
            session.add(ResultadoBusqueda(
                solicitud_id=sid, clave=key,
                titulo="Película ficticia 1080p", indexador="ficticio",
                download_url="https://fixture.invalid/no-descargar",
                publicado_en=date,
            ))
        session.commit()

    def fake_session():
        with Session(engine) as session:
            yield session

    def fake_profile():
        with Session(engine) as session:
            return session.get(Perfil, 1)

    previous_session = app.dependency_overrides.get(get_session)
    previous_profile = app.dependency_overrides.get(get_current_profile)
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_current_profile] = fake_profile
    try:
        with TestClient(app) as client:
            response = client.get(f"/solicitudes/{sid}/resultados")
            assert response.status_code == 200, response.status_code
            results = response.json()
            assert len(results) == 2, len(results)
            dates = {result["id"]: result["publicado_en"] for result in results}
            assert any(isinstance(v, str) and v.startswith("2025-08-15T17:30:00")
                       for v in dates.values())
            assert any(v is None for v in dates.values())
            for result in results:
                assert {"download_url", "magnet_url", "info_hash", "clave"}.isdisjoint(result)
            print("PASS_HTTP_200_FECHA_REAL", flush=True)
            print("PASS_FECHA_NULA", flush=True)
            print("PASS_NO_REVELAR_ENLACES", flush=True)
    finally:
        for dep, previous in ((get_session, previous_session),
                              (get_current_profile, previous_profile)):
            if previous is None:
                app.dependency_overrides.pop(dep, None)
            else:
                app.dependency_overrides[dep] = previous
        engine.dispose()


if __name__ == "__main__":
    main()
