"""Gestión segura: datos ficticios en SQLite RAM y caché de sandbox.

No toca archivos de vídeo, discos productivos, Jellyfin ni qBittorrent.
"""
import importlib.util
import os
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import almacenamiento
from app.almacenamiento_archivos import (
    MARCA,
    limpiar_temporales,
    tamanio_logico,
)
from app.auth import get_current_profile
from app.database import get_session
from app.main import app
from app.models import Medio, Perfil


@pytest.fixture
def laboratorio(tmp_path, monkeypatch) -> Generator[tuple[TestClient, object, dict], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Perfil(nombre="Ana", pin_hash="falso"),
            Perfil(nombre="Luis", pin_hash="falso"),
            Medio(jellyfin_id="jf-uno", titulo="Película de prueba",
                  tipo="pelicula", anio=2024),
            Medio(jellyfin_id="jf-dos", titulo="Otra película",
                  tipo="pelicula", anio=2010),
            Medio(jellyfin_id="jf-serie", titulo="Serie",
                  tipo="serie"),
        ])
        db.commit()

    state = {"perfil": 1}

    def override_profile():
        with Session(engine) as db:
            return db.get(Perfil, state["perfil"])

    def override_db():
        with Session(engine) as db:
            yield db

    old = {
        get_current_profile: app.dependency_overrides.get(get_current_profile),
        get_session: app.dependency_overrides.get(get_session),
    }
    app.dependency_overrides[get_current_profile] = override_profile
    app.dependency_overrides[get_session] = override_db
    monkeypatch.setattr(
        almacenamiento, "get_settings",
        lambda: SimpleNamespace(cache_dir=tmp_path, cache_quota_gb=80),
    )
    try:
        with TestClient(app) as client:
            yield client, engine, state
    finally:
        for dependency, previous in old.items():
            if previous is None:
                app.dependency_overrides.pop(dependency, None)
            else:
                app.dependency_overrides[dependency] = previous
        engine.dispose()


def test_informe_espacio_no_inventa_liberacion(laboratorio):
    client, _, _ = laboratorio
    response = client.get("/almacenamiento/resumen")
    assert response.status_code == 200
    info = response.json()
    assert info["disco"]["total_bytes"] > 0
    assert info["cache_temporal"]["bytes"] == 0
    assert info["cache_cuota_aplicada"] is False
    assert info["cache_cuota_configurada_bytes"] == 80 * 1024 ** 3
    assert info["cache_gestionada"] is False
    assert "enlaces NTFS" in info["aviso"]
    assert "C:\\VIEWTV" not in str(info)
    assert "qbit" not in str(info).lower() or "qBittorrent" in info["aviso"]


def test_visto_por_perfil_y_retirada_estricta(laboratorio):
    client, _, state = laboratorio
    listing = client.get("/almacenamiento/peliculas").json()
    assert listing["total"] == 2
    assert all(not item["visto"] for item in listing["elementos"])

    assert client.post("/almacenamiento/peliculas/1/retirada",
                       json={"titulo": "Película de prueba"}).status_code == 409
    seen = client.post("/almacenamiento/peliculas/1/visto", json={"visto": True})
    assert seen.status_code == 200
    assert seen.json()["visto"] is True
    assert client.post("/almacenamiento/peliculas/1/visto",
                       json={"visto": True}).status_code == 200

    state["perfil"] = 2
    assert client.get("/almacenamiento/peliculas").json()["elementos"][1]["visto"] is False
    state["perfil"] = 1

    assert client.post("/almacenamiento/peliculas/1/retirada",
                       json={"titulo": "Otra película"}).status_code == 409
    assert client.post("/almacenamiento/peliculas/1/retirada",
                       json={"titulo": "Película de prueba"}).status_code == 202
    assert client.post("/almacenamiento/peliculas/1/retirada",
                       json={"titulo": "Película de prueba"}).status_code == 409
    assert client.post("/almacenamiento/peliculas/1/visto",
                       json={"visto": False}).status_code == 409

    status = client.get("/almacenamiento/peliculas").json()["elementos"]
    assert status[1]["solicitud_retirada"] == "pendiente_revision"
    assert status[1]["eliminacion_automatica_disponible"] is False
    assert client.delete("/almacenamiento/peliculas/1/retirada").status_code == 200
    assert client.delete("/almacenamiento/peliculas/1/retirada").status_code == 404
    assert client.post("/almacenamiento/peliculas/1/visto",
                       json={"visto": False}).status_code == 200

    # Solicitudes de perfil 1 nunca se muestran al 2.
    state["perfil"] = 2
    status = client.get("/almacenamiento/peliculas").json()["elementos"]
    assert status[1]["solicitud_retirada"] is None


@pytest.mark.parametrize("media_id", [0, 999, 3])
def test_no_marcar_titulos_ajenos_o_series(laboratorio, media_id):
    client, _, _ = laboratorio
    code = client.post(f"/almacenamiento/peliculas/{media_id}/visto",
                       json={"visto": True}).status_code
    assert code in (404, 422)


def test_tipo_visto_debe_ser_booleano(laboratorio):
    client, _, _ = laboratorio
    assert client.post("/almacenamiento/peliculas/1/visto",
                       json={"visto": "sí"}).status_code == 422


def test_cache_propia_borra_solo_descartables(tmp_path):
    folder = tmp_path / "viewtv-temporales"
    folder.mkdir(mode=0o700)
    (folder / ".viewtv-cache-v1").write_bytes(MARCA)
    own = folder / ("viewtv-" + "a" * 16 + ".tmp")
    own.write_bytes(b"temporal")
    important = folder / "pelicula.mkv"
    important.write_bytes(b"nunca")
    outside = tmp_path / "externo"
    outside.write_bytes(b"externo")
    (folder / ("viewtv-" + "b" * 16 + ".tmp")).symlink_to(outside)

    original = folder / "hardlink-contenido"
    original.write_bytes(b"original")
    linked = folder / ("viewtv-" + "c" * 16 + ".tmp")
    os.link(original, linked)

    assert tamanio_logico(folder)["completo"] is False  # El symlink NO se sigue.
    result = limpiar_temporales(tmp_path)
    assert result == {"estado": "limpiada", "archivos": 1, "bytes": 8}
    assert not own.exists()
    assert important.read_bytes() == b"nunca"
    assert outside.read_bytes() == b"externo"
    assert linked.exists()
    assert original.exists()
    assert (folder / ".viewtv-cache-v1").read_bytes() == MARCA
    assert limpiar_temporales(tmp_path)["archivos"] == 0


def test_sin_marcador_o_permisos_privados_no_borra(tmp_path):
    folder = tmp_path / "viewtv-temporales"
    folder.mkdir(mode=0o700)
    own = folder / ("viewtv-" + "a" * 16 + ".tmp")
    own.write_bytes(b"importante")
    assert limpiar_temporales(tmp_path)["estado"] == "sin_cache_gestionada"
    (folder / ".viewtv-cache-v1").write_bytes(MARCA)
    folder.chmod(0o755)
    assert limpiar_temporales(tmp_path)["estado"] == "sin_cache_gestionada"
    assert own.read_bytes() == b"importante"


def test_endpoint_cache_exige_frase_exacta(laboratorio):
    client, _, _ = laboratorio
    assert client.post("/almacenamiento/cache/limpiar",
                       json={"confirmacion": "BORRAR TODO"}).status_code == 422
    assert client.post("/almacenamiento/cache/limpiar",
                       json={"confirmacion": "LIMPIAR TEMPORALES"}).json() == {
        "estado": "sin_cache_gestionada", "archivos": 0, "bytes": 0,
    }


def test_sin_autenticacion_no_muestra_lista_ni_toca_cache(tmp_path, monkeypatch):
    # No utilizar el fixture que autentica el perfil.
    for path in ("/almacenamiento/resumen", "/almacenamiento/peliculas"):
        with TestClient(app) as client:
            assert client.get(path).status_code == 401
    with TestClient(app) as client:
        assert client.post("/almacenamiento/cache/limpiar",
                           json={"confirmacion": "LIMPIAR TEMPORALES"}).status_code == 401


def test_migracion_reversible_sin_datos_y_bloqueada_con_datos():
    file = (
        Path(__file__).resolve().parents[1] / "migrations" / "versions"
        / "0015_gestion_espacio_vistas.py"
    )
    spec = importlib.util.spec_from_file_location("viewtv_0015", file)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE perfil (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE medio (id INTEGER PRIMARY KEY)"))
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            module.upgrade()
        tables = {row[0] for row in conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert {"pelicula_vista", "solicitud_retirada"}.issubset(tables)
        with Operations.context(context):
            module.downgrade()
        with Operations.context(context):
            module.upgrade()
        conn.execute(text("INSERT INTO perfil(id) VALUES(1)"))
        conn.execute(text("INSERT INTO medio(id) VALUES(2)"))
        conn.execute(text(
            "INSERT INTO pelicula_vista(perfil_id,medio_id,vista_en) "
            "VALUES(1,2,CURRENT_TIMESTAMP)"
        ))
        with Operations.context(context):
            with pytest.raises(RuntimeError, match="visionado"):
                module.downgrade()
        assert conn.execute(text("PRAGMA integrity_check")).fetchone()[0] == "ok"
    engine.dispose()


def test_endpoint_cuota_y_limpieza_de_cache_privada(laboratorio, tmp_path, monkeypatch):
    from app.cache_privada import guardar_temporal

    client, _, _ = laboratorio
    monkeypatch.setattr(almacenamiento, "CACHE_PROPIA_ROOT", tmp_path)
    summary = client.get("/almacenamiento/resumen")
    assert summary.status_code == 200
    own = summary.json()["cache_propia"]
    assert own["estado"] == "vacia_sin_inicializar"
    assert own["bytes"] == 0
    assert own["cuota_efectiva_para_escritores_propios"] is True
    assert summary.json()["cache_cuota_aplicada"] is False

    assert client.post(
        "/almacenamiento/cache/propia/limpiar",
        json={"confirmacion": "LIMPIAR TEMPORALES"},
    ).status_code == 422

    guardar_temporal(tmp_path, b"solo propia", 80 * 1024**3)
    updated = client.get("/almacenamiento/resumen").json()
    assert updated["cache_propia"]["archivos"] == 1
    assert updated["cache_propia"]["bytes"] == 11

    result = client.post(
        "/almacenamiento/cache/propia/limpiar",
        json={"confirmacion": "LIMPIAR CACHE PROPIA"},
    )
    assert result.status_code == 200
    assert result.json() == {"estado": "limpiada", "archivos": 1, "bytes": 11}
    assert client.get("/almacenamiento/resumen").json()["cache_propia"]["bytes"] == 0


def test_cache_privada_bloqueada_no_borra_ni_revela_rutas(
    laboratorio, tmp_path, monkeypatch,
):
    from app.cache_privada import DIR_CACHE, guardar_temporal

    client, _, _ = laboratorio
    monkeypatch.setattr(almacenamiento, "CACHE_PROPIA_ROOT", tmp_path)
    guardada = guardar_temporal(tmp_path, b"conservar", 80 * 1024**3)
    folder = tmp_path / DIR_CACHE
    (folder / "archivo-ajeno.mkv").write_bytes(b"pelicula")
    response = client.post(
        "/almacenamiento/cache/propia/limpiar",
        json={"confirmacion": "LIMPIAR CACHE PROPIA"},
    )
    assert response.status_code == 409
    assert str(tmp_path) not in str(response.json())
    assert (folder / guardada).read_bytes() == b"conservar"
    assert (folder / "archivo-ajeno.mkv").read_bytes() == b"pelicula"
