"""Ensayo read-only con copia de SQLite real, sin sesión ni secretos.

No conecta al volumen productivo, no usa PIN y no devuelve títulos/URLs.
"""
import os
import sqlite3
from pathlib import Path

from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Perfil, ResultadoBusqueda, Solicitud
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select


def main():
    assert os.environ.get("VIEWTV_COPIA_SOLICITUDES_ONLY") == "1"
    assert os.environ.get("DATABASE_URL") == "sqlite:///:memory:"
    assert not Path("/data/viewtv.db").exists()
    assert Path("/copia/viewtv.db").is_file()

    raw = sqlite3.connect(
        "file:/copia/viewtv.db?mode=ro", uri=True, check_same_thread=False,
    )
    raw.execute("PRAGMA query_only=ON")
    engine = create_engine("sqlite://", creator=lambda: raw, poolclass=StaticPool)

    with Session(engine) as session:
        request = session.exec(
            select(Solicitud)
            .where(Solicitud.estado == "esperando_seleccion")
            .order_by(Solicitud.id.desc())
        ).first()
        assert request is not None, "La copia no contiene solicitud seleccionable"
        rid = request.id
        profile_id = request.perfil_id
        count = len(session.exec(
            select(ResultadoBusqueda).where(ResultadoBusqueda.solicitud_id == rid)
        ).all())
        assert count > 0, "No hay resultados en copia"

    def mock_session():
        with Session(engine) as session:
            yield session

    def mock_profile():
        with Session(engine) as session:
            return session.get(Perfil, profile_id)

    old_session = app.dependency_overrides.get(get_session)
    old_profile = app.dependency_overrides.get(get_current_profile)
    app.dependency_overrides[get_session] = mock_session
    app.dependency_overrides[get_current_profile] = mock_profile

    try:
        with TestClient(app) as client:
            response = client.get(f"/solicitudes/{rid}/resultados")
            assert response.status_code == 200, response.status_code
            results = response.json()
            assert len(results) == count, "No coinciden los registros"
            assert any(item["publicado_en"] is not None for item in results)
            for item in results:
                assert {"download_url", "magnet_url", "info_hash", "clave"}.isdisjoint(item)
            print("COPIA_PRODUCCION_RESULTADOS_HTTP=200")
            print("COPIA_PRODUCCION_RESULTADOS_COINCIDEN=SI")
            print("COPIA_PRODUCCION_DATOS_PRIVADOS=NO_EXPUESTOS")
    finally:
        for dep, previous in ((get_session, old_session),
                              (get_current_profile, old_profile)):
            if previous is None:
                app.dependency_overrides.pop(dep, None)
            else:
                app.dependency_overrides[dep] = previous
        engine.dispose()

if __name__ == "__main__":
    main()
