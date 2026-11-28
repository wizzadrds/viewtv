"""Probar la preselección con COPIA SQLite real; sin POST a qBittorrent.

Este proceso sólo escribe en una SQLite en memoria. Realiza únicamente
GET de metadatos Jackett y TestClient hacia su API interna local.
"""
import os
import sqlite3
from types import SimpleNamespace

import app.solicitudes as routes
from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Descarga, Perfil, ResultadoBusqueda, Solicitud
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine


def main():
    assert os.environ.get("VIEWTV_PREVIEW_SANDBOX") == "1"
    assert os.environ.get("VIEWTV_ENABLE_TORRENT_SUBMIT") == "false"
    assert os.environ.get("VIEWTV_ENABLE_DOWNLOAD_START") == "false"
    assert not os.path.exists("/data/viewtv.db")

    original = sqlite3.connect("file:/copia/viewtv.db?mode=ro", uri=True)
    mem = sqlite3.connect(":memory:", check_same_thread=False)
    original.backup(mem)
    original.close()
    mem.execute("PRAGMA foreign_keys=ON")
    engine = create_engine("sqlite://", poolclass=StaticPool, creator=lambda: mem)

    with Session(engine) as session:
        req = session.get(Solicitud, 6)
        descarga = session.get(Descarga, 2)
        assert req is not None and descarga is not None
        assert descarga.solicitud_id == 6
        assert descarga.estado == "seleccionada" and descarga.intentos_envio == 0
        assert descarga.qbittorrent_hash is None
        result = session.get(ResultadoBusqueda, descarga.resultado_busqueda_id)
        assert result is not None and result.tamano_bytes == 20 * 1024**3
        result_id = result.id
        profile_id = req.perfil_id
        # Solo en memoria: permitir comprobar el resultado de la solicitud
        # que en producción ya fue seleccionado. No elimina ni altera SQLite real.
        req.estado = "esperando_seleccion"
        session.add(req)
        session.commit()

    def get_session_fake():
        with Session(engine) as session:
            yield session

    def get_profile_fake():
        with Session(engine) as session:
            return session.get(Perfil, profile_id)

    old_session = app.dependency_overrides.get(get_session)
    old_profile = app.dependency_overrides.get(get_current_profile)
    old_settings = routes.get_settings
    app.dependency_overrides[get_session] = get_session_fake
    app.dependency_overrides[get_current_profile] = get_profile_fake
    routes.get_settings = lambda: SimpleNamespace(
        jackett_base_url="http://host.docker.internal:9117"
    )
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/solicitudes/6/resultados/{result_id}/verificacion"
            )
            assert response.status_code == 200, response.status_code
            info = response.json()
            assert info["estado"] == "bloqueado"
            assert info["puede_seleccionar"] is False
            assert info["tamano_anunciado_bytes"] == 20 * 1024**3
            assert info["tamano_real_bytes"] == 33_260_748_236
            assert "download_url" not in info and "info_hash" not in info
            assert any("tamaño real" in warning for warning in info["advertencias"])
            print("PASS_METADATOS_REALES_33GB")
            print("PASS_PRESELECCION_RECHAZADA")
            print("PASS_PRIVACIDAD_SIN_LINKS_HASHES")

            selected = client.post(
                "/solicitudes/6/seleccion", json={"resultado_id": result_id}
            )
            assert selected.status_code == 409, selected.status_code
            print("PASS_SELECCION_DIRECTA_BLOQUEADA")
            with Session(engine) as session:
                item = session.get(Descarga, 2)
                assert item.estado == "seleccionada" and item.intentos_envio == 0
                assert item.qbittorrent_hash is None
            print("PASS_NINGUN_ENVIO_NI_CAMBIO_PRODUCCION")
    finally:
        routes.get_settings = old_settings
        for dep, old in (
            (get_session, old_session),
            (get_current_profile, old_profile),
        ):
            if old is None:
                app.dependency_overrides.pop(dep, None)
            else:
                app.dependency_overrides[dep] = old
        engine.dispose()


if __name__ == "__main__":
    main()
