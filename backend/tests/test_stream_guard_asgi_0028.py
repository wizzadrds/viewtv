"""0028: la barrera ASGI incluye TODAS las rutas de vídeo, SOLO tests.

No hay instalación en app.main ni cambios en Jellyfin, la SQLite real,
perfiles, torrents ni vídeos. Todos los IDs y tokens son ficticios.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from worker.retirement_playback_admission_0027 import (
    MARKER,
    LaboratorioAdmision0027,
)

from app.retirement_http_gate_lab_0028 import StreamingRouteGuardLab0028


@pytest.fixture
def lab():
    root = Path(tempfile.gettempdir()) / (
        "viewtv-admission-0027-" + uuid.uuid4().hex
    )
    root.mkdir(mode=0o700)
    marker = root / "marca-0027.txt"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(marker, flags, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as stream:
        stream.write(MARKER)
    try:
        yield LaboratorioAdmision0027(root)
    finally:
        shutil.rmtree(root)


def synthetic_app():
    app = FastAPI()
    calls: list[str] = []

    @app.post("/jellyfin/media/{media_id}/playback-info")
    def negotiate(media_id: int):
        calls.append("negotiate")
        return {"medio": media_id}

    @app.get("/jellyfin/media/{media_id}/stream")
    def stream(media_id: int):
        calls.append("stream")
        return PlainTextResponse("direct:" + str(media_id))

    @app.get("/jellyfin/media/{media_id}/hls")
    def hls(media_id: int):
        calls.append("hls")
        return PlainTextResponse("hls:" + str(media_id))

    @app.get("/jellyfin/media/{media_id}/images/primary")
    def poster(media_id: int):
        calls.append("poster")
        return PlainTextResponse("poster:" + str(media_id))

    @app.get("/health")
    def health():
        calls.append("health")
        return PlainTextResponse("ok")

    @app.get("/jellyfin/media/{media_id}/nueva-ruta-video")
    def future(media_id: int):
        calls.append("future")
        return PlainTextResponse("new:" + str(media_id))

    return app, calls


@pytest.mark.parametrize(("method", "path", "body"), [
    ("POST", "/jellyfin/media/4/playback-info", {"medio": 4}),
    ("GET", "/jellyfin/media/4/stream", None),
    ("GET", "/jellyfin/media/4/hls", None),
])
def test_tres_rutas_admiten_peticion_antes_de_drenar(lab, method, path, body):
    app, calls = synthetic_app()
    with TestClient(StreamingRouteGuardLab0028(app, lab)) as client:
        response = client.request(method, path)
        assert response.status_code == 200
        if body is not None:
            assert response.json() == body
    assert len(calls) == 1
    report = lab.observar(4)
    assert report["estado"] == "libre"
    assert report["sesiones_viewtv_pendientes"] == 0
    assert report["peticiones_video_pendientes"] == 0


@pytest.mark.parametrize(("method", "path"), [
    ("POST", "/jellyfin/media/4/playback-info"),
    ("GET", "/jellyfin/media/4/stream"),
    ("GET", "/jellyfin/media/4/hls?token=simulated"),
])
def test_al_drenar_nueva_peticion_denegada_antes_del_handler(lab, method, path):
    app, calls = synthetic_app()
    assert lab.iniciar_drenaje(4)["estado"] == "listo_para_preflight"
    with TestClient(StreamingRouteGuardLab0028(app, lab)) as client:
        response = client.request(method, path)
        assert response.status_code == 423
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["detail"].startswith("Reproduccion")
    assert calls == []
    assert lab.observar(4)["sesiones_viewtv_pendientes"] == 0


def test_otro_medio_no_se_bloquea_y_las_imagenes_siguen_disponibles(lab):
    app, calls = synthetic_app()
    lab.iniciar_drenaje(4)
    with TestClient(StreamingRouteGuardLab0028(app, lab)) as client:
        assert client.get("/jellyfin/media/5/stream").status_code == 200
        assert client.get("/jellyfin/media/4/images/primary").status_code == 200
        assert client.get("/health").status_code == 200
    assert calls == ["stream", "poster", "health"]


@pytest.mark.parametrize(("method", "path"), [
    ("GET", "/jellyfin/media/4/playback-info"),
    ("POST", "/jellyfin/media/4/hls"),
    ("GET", "/jellyfin/media/004/hls"),
    ("GET", "/jellyfin/media/0/stream"),
    ("GET", "/jellyfin/media/2147483648/hls"),
    ("GET", "/jellyfin/media/4/nueva-ruta-video"),
    ("GET", "/jellyfin/media/4/hls/extra"),
    ("GET", "/jellyfin/media/4/images/extra"),
])
def test_ruta_futura_o_ambigua_denegada_antes_de_stream(lab, method, path):
    app, calls = synthetic_app()
    with TestClient(StreamingRouteGuardLab0028(app, lab)) as client:
        response = client.request(method, path)
    assert response.status_code == 423
    assert not calls


def test_porcentajes_codificados_no_saltan_barrera(lab):
    app, calls = synthetic_app()
    with TestClient(StreamingRouteGuardLab0028(app, lab)) as client:
        # Un slash codificado puede ser decodificado por el ASGI.
        result = client.get(
            "/jellyfin/media/4%2Fhls?token=" + quote("token-intento")
        )
        assert result.status_code == 423
    assert calls == []


def test_stream_en_vuelo_no_deja_libre_el_medio_hasta_terminar(lab):
    opened = asyncio.Event()
    finish = asyncio.Event()

    async def streaming(_scope, _receive, send):
        await send({
            "type": "http.response.start", "status": 200,
            "headers": [(b"content-type", b"video/mp4")],
        })
        opened.set()
        await send({
            "type": "http.response.body", "body": b"primero", "more_body": True,
        })
        await finish.wait()
        await send({
            "type": "http.response.body", "body": b"ultimo", "more_body": False,
        })

    async def scenario():
        middleware = StreamingRouteGuardLab0028(streaming, lab)
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(payload):
            sent.append(payload)

        scope = {
            "type": "http", "method": "GET",
            "path": "/jellyfin/media/4/stream",
            "raw_path": b"/jellyfin/media/4/stream",
        }
        task = asyncio.create_task(middleware(scope, receive, send))
        await asyncio.wait_for(opened.wait(), timeout=5)
        assert lab.observar(4)["peticiones_video_pendientes"] == 1
        assert lab.iniciar_drenaje(4)["estado"] == "drenando"
        assert lab.observar(4)["sesiones_viewtv_pendientes"] == 1
        finish.set()
        await asyncio.wait_for(task, timeout=5)
        assert lab.observar(4)["estado"] == "listo_para_preflight"
        assert sent[-1]["body"] == b"ultimo"

    asyncio.run(scenario())


def test_cancelacion_http_libera_ticket_y_drena(lab):
    begun = asyncio.Event()

    async def interrupted(_scope, _receive, send):
        begun.set()
        await asyncio.Event().wait()

    async def scenario():
        middleware = StreamingRouteGuardLab0028(interrupted, lab)
        scope = {
            "type": "http", "method": "GET",
            "path": "/jellyfin/media/4/hls",
            "raw_path": b"/jellyfin/media/4/hls",
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(_):
            return None

        task = asyncio.create_task(middleware(scope, receive, send))
        await asyncio.wait_for(begun.wait(), timeout=5)
        assert lab.iniciar_drenaje(4)["estado"] == "drenando"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert lab.observar(4)["estado"] == "listo_para_preflight"

    asyncio.run(scenario())


def test_sesion_atascada_por_caida_previa_bloquea_para_siempre(lab):
    token = lab.abrir_sesion(4)
    io = lab.iniciar_peticion(4, token)
    lab.cerrar_sesion(4, token)
    assert lab.iniciar_drenaje(4)["estado"] == "drenando"
    app, _ = synthetic_app()
    with TestClient(StreamingRouteGuardLab0028(app, lab)) as client:
        assert client.get("/jellyfin/media/4/hls").status_code == 423
    assert lab.observar(4)["estado"] == "drenando"
    # Solo el ensayo posee ambos tokens para finalizar la solicitud ficticia.
    lab.terminar_peticion(4, token, io)
    assert lab.observar(4)["estado"] == "listo_para_preflight"


def test_no_registra_capa_en_la_api_real():
    from app.main import app

    assert all(
        middleware.cls is not StreamingRouteGuardLab0028
        for middleware in app.user_middleware
    )
    assert not isinstance(app, StreamingRouteGuardLab0028)


def test_db_invalida_denegada_sin_devolver_excepcion(lab):
    app, calls = synthetic_app()
    lab.iniciar_drenaje(4)
    # La autoridad existe, pero una película en drenaje es DENEGADA.
    with TestClient(StreamingRouteGuardLab0028(app, lab)) as client:
        assert client.get("/jellyfin/media/4/stream").status_code == 423
    assert not calls
