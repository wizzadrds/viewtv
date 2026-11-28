"""Ensayo de descarte explícito sobre copia SQLite, sin conexión qBit.

La copia se clona en memoria: NO se modifican producción ni torrents.
"""
import os
import sqlite3

import app.solicitudes as routes
from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Descarga, Perfil, Solicitud
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine


def main():
    assert os.environ.get("VIEWTV_DISCARD_SANDBOX") == "1"
    assert os.environ.get("DATABASE_URL") == "sqlite:///:memory:"
    assert os.environ.get("VIEWTV_ENABLE_TORRENT_SUBMIT") == "false"
    assert os.environ.get("VIEWTV_ENABLE_DOWNLOAD_START") == "false"
    assert not os.path.exists("/data/viewtv.db")
    src = sqlite3.connect("file:/copia/viewtv.db?mode=ro", uri=True)
    mem = sqlite3.connect(":memory:", check_same_thread=False)
    src.backup(mem)
    src.close()
    mem.execute("PRAGMA foreign_keys=ON")
    engine = create_engine("sqlite://", poolclass=StaticPool, creator=lambda: mem)
    with Session(engine) as session:
        item = session.get(Descarga, 1)
        assert item and item.solicitud_id == 3
        assert item.estado == "enviada" and item.inicio_estado == "pendiente"
        assert item.progreso == 0 and item.inicio_intentos == 0
        profile_id = session.get(Solicitud, 3).perfil_id

    def fake_session():
        with Session(engine) as session:
            yield session

    def fake_profile():
        with Session(engine) as session:
            return session.get(Perfil, profile_id)

    class FakeQB:
        calls = 0
        def torrents_info(self, hashes=None, *, tag=None):
            self.calls += 1
            return []

    qbit = FakeQB()
    previous_db = app.dependency_overrides.get(get_session)
    previous_profile = app.dependency_overrides.get(get_current_profile)
    previous_qbit = routes.QBittorrentClient
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_current_profile] = fake_profile
    routes.QBittorrentClient = lambda: qbit
    try:
        with TestClient(app) as client:
            initial = client.get("/solicitudes/descargas")
            assert initial.status_code == 200
            assert initial.json()["total"] == 1

            result = client.post("/solicitudes/descargas/1/descartar-incorrecta")
            assert result.status_code == 200, result.status_code
            assert result.json() == {"id": 1, "estado": "descartada"}
            assert qbit.calls == 2
            assert client.get("/solicitudes/descargas").json()["total"] == 0
            history = client.get(
                "/solicitudes/descargas?incluir_descartadas=true"
            ).json()
            assert history["total"] == 1
            assert history["elementos"][0]["estado"] == "fallida"

            with Session(engine) as session:
                item = session.get(Descarga, 1)
                req = session.get(Solicitud, 3)
                assert item and req
                assert item.qbittorrent_hash
                assert item.inicio_estado == "requiere_revision"
                assert item.estado == "fallida" and req.estado == "cancelada"
            print("PASS_DESCARTE_EN_COPIA_SIN_POST_QBIT")
            print("PASS_LISTA_PRINCIPAL_LIMPIA")
            print("PASS_HISTORIAL_CONSERVADO")
            print("PASS_INICIO_BLOQUEADO")
    finally:
        routes.QBittorrentClient = previous_qbit
        for dep, old in ((get_session, previous_db),
                         (get_current_profile, previous_profile)):
            if old is None:
                app.dependency_overrides.pop(dep, None)
            else:
                app.dependency_overrides[dep] = old
        engine.dispose()


if __name__ == "__main__":
    main()
