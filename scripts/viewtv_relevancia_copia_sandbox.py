"""Prueba de reversión/filtrado contra una COPIA SQLite, nunca producción.

Toma snapshot ro, copia a memoria, simula autenticación local y comprueba
deshacer selección #1, rechazo de episodio y elegir coincidencia plausible.
No descarga ni expone secretos; no imprime títulos, hashes, PIN ni URLs.
"""
import os
import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Perfil, ResultadoBusqueda, Solicitud
from app.relevancia_resultado import coincide_con_solicitud


def main():
    assert os.environ.get("VIEWTV_RELEVANCIA_TEST_ONLY") == "1"
    assert os.environ.get("DATABASE_URL") == "sqlite:///:memory:"
    assert os.environ.get("VIEWTV_ENABLE_TORRENT_SUBMIT") == "false"
    assert os.environ.get("VIEWTV_ENABLE_DOWNLOAD_START") == "false"
    assert not os.path.exists("/data/viewtv.db")
    raw = sqlite3.connect("file:/copia/viewtv.db?mode=ro", uri=True)
    memory = sqlite3.connect(":memory:", check_same_thread=False)
    raw.backup(memory)
    raw.close()
    memory.execute("PRAGMA foreign_keys=ON")
    engine = create_engine("sqlite://", poolclass=StaticPool, creator=lambda: memory)
    with Session(engine) as session:
        solicitud = session.get(Solicitud, 3)
        assert solicitud is not None
        assert solicitud.estado == "completada"
        pid = solicitud.perfil_id
        old = memory.execute(
            "SELECT resultado_busqueda_id FROM descarga WHERE id=1 AND solicitud_id=3 "
            "AND estado='seleccionada' AND qbittorrent_hash IS NULL AND intentos_envio=0"
        ).fetchone()
        assert old is not None
        bad_id = old[0]
        records = session.exec(
            select(ResultadoBusqueda).where(ResultadoBusqueda.solicitud_id == 3)
        ).all()
        assert len(records) > 2
        assert any(i.id == bad_id and not coincide_con_solicitud(
            solicitud.titulo, solicitud.tipo_medio, solicitud.anio, i.titulo
        ) for i in records)
        goods = [i.id for i in records if coincide_con_solicitud(
            solicitud.titulo, solicitud.tipo_medio, solicitud.anio, i.titulo
        )]
        assert 0 < len(goods) < len(records)

    def own_session():
        with Session(engine) as session:
            yield session

    def own_profile():
        with Session(engine) as session:
            return session.get(Perfil, pid)

    old_session = app.dependency_overrides.get(get_session)
    old_profile = app.dependency_overrides.get(get_current_profile)
    app.dependency_overrides[get_session] = own_session
    app.dependency_overrides[get_current_profile] = own_profile
    try:
        with TestClient(app) as client:
            undone = client.post("/solicitudes/descargas/1/deshacer-seleccion")
            assert undone.status_code == 200
            assert client.get("/solicitudes/descargas").json()["total"] == 0
            assert any(x["id"] == 3 for x in client.get("/solicitudes?solo_activas=true").json())
            print("PASS_DESHACER_ERRONEA_EN_COPIA")

            displayed = client.get("/solicitudes/3/resultados")
            assert displayed.status_code == 200
            ids = [item["id"] for item in displayed.json()]
            assert set(ids) == set(goods)
            assert bad_id not in ids
            print("PASS_OCULTAR_EPISODIO_REAL")

            invalid = client.post(
                "/solicitudes/3/seleccion", json={"resultado_id": bad_id},
            )
            assert invalid.status_code == 409
            valid = client.post(
                "/solicitudes/3/seleccion", json={"resultado_id": goods[0]},
            )
            assert valid.status_code == 201
            assert client.get("/solicitudes?solo_activas=true").json() == []
            assert client.get("/solicitudes/descargas").json()["total"] == 1
            print("PASS_RECHAZAR_ERRONEA_ELEGIR_COINCIDENTE")
            print("PASS_LIMPIEZA_LISTA_PENDIENTES")
    finally:
        for dep, prev in ((get_session, old_session), (get_current_profile, old_profile)):
            if prev is None:
                app.dependency_overrides.pop(dep, None)
            else:
                app.dependency_overrides[dep] = prev
        engine.dispose()


if __name__ == "__main__":
    main()
