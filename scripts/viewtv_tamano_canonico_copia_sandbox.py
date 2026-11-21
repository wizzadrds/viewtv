"""Prueba end-to-end de tamaño canonico sobre COPIA de SQLite en memoria.

No añade torrents: solo GET metainfo Jackett, API TestClient local y
escrituras exclusivas en SQLite memoria, sin qBittorrent ni medios.
"""
import os
import sqlite3
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Descarga, Perfil, ResultadoBusqueda, Solicitud
import app.solicitudes as routes


def main():
    assert os.environ.get("VIEWTV_TAMANO_CANONICO_SANDBOX") == "1"
    assert os.environ.get("VIEWTV_ENABLE_TORRENT_SUBMIT") == "false"
    assert os.environ.get("VIEWTV_ENABLE_DOWNLOAD_START") == "false"
    assert not os.path.exists("/data/viewtv.db")

    source = sqlite3.connect("file:/copia/viewtv.db?mode=ro", uri=True)
    mem = sqlite3.connect(":memory:", check_same_thread=False)
    source.backup(mem)
    source.close()
    mem.execute("PRAGMA foreign_keys=ON")
    engine = create_engine("sqlite://", poolclass=StaticPool, creator=lambda: mem)

    with Session(engine) as session:
        req = session.get(Solicitud, 6)
        assert req is not None
        dl = session.exec(
            select(Descarga).where(Descarga.solicitud_id == 6)
        ).first()
        if dl is not None:
            assert dl.estado == "seleccionada" and dl.intentos_envio == 0
            assert dl.qbittorrent_hash is None
            # Solo en memoria, si en la copia todavía estaba seleccionada.
            session.delete(dl)
        result = session.exec(
            select(ResultadoBusqueda).where(
                ResultadoBusqueda.solicitud_id == 6,
                ResultadoBusqueda.tamano_bytes == 20 * 1024**3,
            )
        ).first()
        assert result is not None
        result_id = result.id
        profile_id = req.perfil_id

        # Solo sobre la copia RAM: apertura para una nueva selección.
        req.estado = "esperando_seleccion"
        session.add(req)
        session.commit()

    def sandbox_session():
        with Session(engine) as session:
            yield session

    def sandbox_profile():
        with Session(engine) as session:
            return session.get(Perfil, profile_id)

    saved_sess = app.dependency_overrides.get(get_session)
    saved_prof = app.dependency_overrides.get(get_current_profile)
    saved_settings = routes.get_settings
    app.dependency_overrides[get_session] = sandbox_session
    app.dependency_overrides[get_current_profile] = sandbox_profile
    routes.get_settings = lambda: SimpleNamespace(
        jackett_base_url="http://host.docker.internal:9117"
    )
    try:
        with TestClient(app) as client:
            preview = client.get(
                f"/solicitudes/6/resultados/{result_id}/verificacion"
            )
            assert preview.status_code == 200, preview.status_code
            info = preview.json()
            assert info["estado"] == "apto"
            assert info["puede_seleccionar"] is True
            assert info["tamano_anunciado_bytes"] == 20 * 1024**3
            assert info["tamano_real_bytes"] == 33_260_748_236
            assert len(info["advertencias"]) >= 1
            print("PASS_PREVIEW_TAMANO_REAL_COMO_FUENTE")
            print("PASS_DIFERENCIA_JACKETT_NO_BLOQUEA")
            for hidden in ("info_hash", "download_url", "magnet_url", "clave"):
                assert hidden not in info
            print("PASS_PRIVACIDAD_RESPUESTA")

            selected = client.post(
                "/solicitudes/6/seleccion",
                json={"resultado_id": result_id},
            )
            assert selected.status_code == 201, selected.status_code
            with Session(engine) as session:
                item = session.exec(
                    select(Descarga).where(Descarga.solicitud_id == 6)
                ).one()
                assert item.estado == "seleccionada"
                assert item.tamano_bytes == 33_260_748_236
                assert item.info_hash and len(item.info_hash) == 40
                assert item.qbittorrent_hash is None
                assert item.intentos_envio == 0
            print("PASS_DB_TAMANO_CANONICO")
            print("PASS_DB_HASH_CANONICO")
            print("PASS_SIN_DESCARGA_REAL")
    finally:
        routes.get_settings = saved_settings
        for dependency, original in (
            (get_session, saved_sess),
            (get_current_profile, saved_prof),
        ):
            if original is None:
                app.dependency_overrides.pop(dependency, None)
            else:
                app.dependency_overrides[dependency] = original
        engine.dispose()


if __name__ == "__main__":
    main()
