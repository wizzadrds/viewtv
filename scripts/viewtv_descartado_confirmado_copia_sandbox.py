"""Prueba de selección sin veto histórico, en SQLite SOLO memoria.

La única red es GET de metainfo Jackett; ninguna descarga a qBittorrent
y no se conecta a DB productiva. Evita imprimir claves, hashes o URL.
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
from sqlmodel import Session, create_engine, select


def main():
    assert os.environ.get("VIEWTV_DESCARTADO_SANDBOX") == "1"
    assert os.environ.get("VIEWTV_ENABLE_TORRENT_SUBMIT") == "false"
    assert os.environ.get("VIEWTV_ENABLE_DOWNLOAD_START") == "false"
    assert not os.path.exists("/data/viewtv.db")

    with sqlite3.connect("file:/copia/viewtv.db?mode=ro", uri=True) as src:
        memory_db = sqlite3.connect(":memory:", check_same_thread=False)
        src.backup(memory_db)
    memory_db.execute("PRAGMA foreign_keys=ON")
    engine = create_engine("sqlite://", poolclass=StaticPool, creator=lambda: memory_db)

    with Session(engine) as session:
        old = session.get(Descarga, 1)
        req = session.get(Solicitud, 7)
        assert old is not None and old.estado == "fallida"
        assert req is not None and req.estado == "esperando_seleccion"
        assert session.get(Solicitud, old.solicitud_id).estado == "cancelada"
        results = session.exec(
            select(ResultadoBusqueda).where(ResultadoBusqueda.solicitud_id == 7)
        ).all()
        assert len(results) == 2
        rid = results[0].id
        profile_id = req.perfil_id
        oldhash = old.qbittorrent_hash
        assert oldhash and len(oldhash) == 40

    def sandbox_session():
        with Session(engine) as session:
            yield session

    def sandbox_profile():
        with Session(engine) as session:
            return session.get(Perfil, profile_id)

    old_session = app.dependency_overrides.get(get_session)
    old_profile = app.dependency_overrides.get(get_current_profile)
    old_settings = routes.get_settings
    app.dependency_overrides[get_session] = sandbox_session
    app.dependency_overrides[get_current_profile] = sandbox_profile
    routes.get_settings = lambda: SimpleNamespace(
        jackett_base_url="http://host.docker.internal:9117"
    )
    try:
        with TestClient(app) as client:
            preview = client.get(f"/solicitudes/7/resultados/{rid}/verificacion")
            assert preview.status_code == 200, preview.status_code
            info = preview.json()
            assert info["estado"] == "apto"
            assert info["puede_seleccionar"] is True
            assert "descartado_anteriormente" not in info
            assert info["tamano_real_bytes"] == 17_686_540_911
            assert "info_hash" not in info and "download_url" not in info
            assert not any(
                "descart" in warning.lower() for warning in info["advertencias"]
            )
            print("PASS_TAMANO_REAL_SIN_VETO_DESCARTADO")

            retry = client.post(
                "/solicitudes/7/seleccion",
                json={"resultado_id": rid},
            )
            assert retry.status_code == 201, retry.status_code
            with Session(engine) as session:
                new = session.exec(
                    select(Descarga).where(Descarga.solicitud_id == 7)
                ).one()
                assert new.id > 1
                assert new.estado == "seleccionada"
                assert new.tamano_bytes == 17_686_540_911
                assert new.info_hash == oldhash
                assert new.intentos_envio == 0
                assert new.qbittorrent_hash is None
                assert session.get(Solicitud, 7).estado == "completada"
                assert session.get(Descarga, 1).estado == "fallida"
            print("PASS_ELECCION_NORMAL_SIN_CONFIRMACION_EN_COPIA")
            print("PASS_HISTORICO_INALTERADO_SIN_QBITTORRENT")
    finally:
        routes.get_settings = old_settings
        for dependency, prior in (
            (get_session, old_session), (get_current_profile, old_profile),
        ):
            if prior is None:
                app.dependency_overrides.pop(dependency, None)
            else:
                app.dependency_overrides[dependency] = prior
        engine.dispose()


if __name__ == "__main__":
    main()
