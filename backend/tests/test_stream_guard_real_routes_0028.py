"""0028: envolver las rutas reales FastAPI con gate ASGI solo en TestClient.

Todas las fuentes Jellyfin son MockTransport/in-memory; no usa ni modifica
la SQLite, servicios, perfiles, vídeos o contenedores de VIEWTV.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from worker.retirement_playback_admission_0027 import (
    MARKER,
    LaboratorioAdmision0027,
)

from app.auth import get_current_profile
from app.config import Settings
from app.database import get_session
from app.jellyfin_hls import sign_hls_url
from app.main import app
from app.models import Medio, Perfil
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


@pytest.fixture
def harness(lab, monkeypatch):
    import app.jellyfin_playback as playback

    memory = create_engine(
        "sqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(memory)
    with Session(memory) as db:
        db.add(Medio(
            jellyfin_id="jf-ficticio-0028", titulo="Pelicula ficticia 0028",
            tipo="pelicula", disponible_en_jellyfin=True,
        ))
        db.commit()
        movie = db.exec(
            __import__("sqlmodel").select(Medio).where(
                Medio.jellyfin_id == "jf-ficticio-0028"
            )
        ).one()
        mid = movie.id
    assert type(mid) is int and mid > 0

    def session():
        with Session(memory) as db:
            yield db

    def profile():
        return Perfil(id=88, nombre="Perfil ficticio 0028")

    prior_session = app.dependency_overrides.get(get_session)
    prior_profile = app.dependency_overrides.get(get_current_profile)
    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_current_profile] = profile

    config = Settings(
        jellyfin_base_url="http://jellyfin-ficticio.test:8096",
        jellyfin_api_key="solo-clave-test",
        jellyfin_user_id="solo-perfil-test",
        jwt_secret="0123456789abcdef" * 4,
    )
    monkeypatch.setattr(playback, "get_settings", lambda: config)
    upstream_access: list[str] = []

    class FakePlaybackClient:
        def playback_info(self, jellyfin_id, start_time_ticks=0):
            assert jellyfin_id == "jf-ficticio-0028"
            upstream_access.append("negociacion")
            return {
                "MediaSources": [{
                    "Id": "fuente-ficticia",
                    "Container": "mp4",
                    "SupportsDirectPlay": True,
                }],
            }

        def open_stream(self, jellyfin_id, media_source_id, range_header, if_range):
            assert jellyfin_id == "jf-ficticio-0028"
            upstream_access.append("directo")
            result = httpx.Response(
                200, content=b"video-ficticio",
                headers={"content-type": "video/mp4"},
            )
            return SimpleNamespace(close=lambda: None), result

    def fake_open_hls(uri, _settings, range_header=None):
        assert uri.startswith("/videos/abc/")
        upstream_access.append("hls")
        is_playlist = uri.split("?", 1)[0].endswith(".m3u8")
        content = (
            b"#EXTM3U\n#EXTINF:4,\nhls1/main/0.ts\n"
            if is_playlist else b"fragmento-ficticio"
        )
        response = httpx.Response(
            200, content=content,
            headers={"content-type": (
                "application/vnd.apple.mpegurl" if is_playlist else "video/mp2t"
            )},
        )
        return SimpleNamespace(close=lambda: None), response

    monkeypatch.setattr(playback, "JellyfinPlaybackClient", FakePlaybackClient)
    monkeypatch.setattr(playback, "open_hls_upstream", fake_open_hls)

    try:
        yield {
            "app": StreamingRouteGuardLab0028(app, lab),
            "media": mid,
            "settings": config,
            "requests": upstream_access,
            "lab": lab,
        }
    finally:
        if prior_session is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = prior_session
        if prior_profile is None:
            app.dependency_overrides.pop(get_current_profile, None)
        else:
            app.dependency_overrides[get_current_profile] = prior_profile
        memory.dispose()


def test_rutas_reales_se_drenan_antes_de_tocar_jellyfin(harness):
    movie = harness["media"]
    lab = harness["lab"]
    hls = sign_hls_url(
        "/videos/abc/master.m3u8", movie, harness["settings"],
    )
    path = f"/jellyfin/media/{movie}"
    playlist_path = path + "/hls?token=" + hls

    with TestClient(harness["app"]) as client:
        neg = client.post(path + "/playback-info")
        assert neg.status_code == 200
        assert neg.json()["fuentes"][0]["modo"] == "direct"

        direct = client.get(path + "/stream")
        assert direct.status_code == 200
        assert direct.content == b"video-ficticio"

        playlist = client.get(playlist_path)
        assert playlist.status_code == 200
        segment_url = playlist.text.splitlines()[-1]
        assert segment_url.startswith("/api/viewtv" + path + "/hls?token=")
        segment_path = segment_url.removeprefix("/api/viewtv")
        segment = client.get(segment_path)
        assert segment.status_code == 200
        assert segment.content == b"fragmento-ficticio"

        # Todas las peticiones cerradas: los contadores vuelven a cero.
        assert lab.observar(movie)["sesiones_viewtv_pendientes"] == 0
        assert lab.observar(movie)["peticiones_video_pendientes"] == 0
        assert harness["requests"] == [
            "negociacion", "directo", "hls", "hls",
        ]

        assert lab.iniciar_drenaje(movie)["estado"] == "listo_para_preflight"
        before = len(harness["requests"])
        assert client.post(path + "/playback-info").status_code == 423
        assert client.get(path + "/stream").status_code == 423
        # Los dos tokens HLS siguen firmados y en plazo, pero el gate los
        # rechaza antes de contactar con Jellyfin.
        assert client.get(playlist_path).status_code == 423
        assert client.get(segment_path).status_code == 423
        assert len(harness["requests"]) == before
        assert client.get("/health").status_code == 200

    assert lab.observar(movie)["autoriza_borrado_fisico"] is False


def test_login_no_se_sustituye_por_un_token_de_laboratorio(lab):
    from app.main import app as live_source

    # La protección de sesión VIEWTV sigue siendo ajena al laboratorio.
    # No se inyectan perfiles y no hay credenciales reales.
    gated = StreamingRouteGuardLab0028(live_source, lab)
    with TestClient(gated) as client:
        assert client.post(
            "/jellyfin/media/987654321/playback-info"
        ).status_code == 401
    observed = lab.observar(987654321)
    assert observed["sesiones_viewtv_pendientes"] == 0
    assert observed["peticiones_video_pendientes"] == 0
