"""0032: rutas productivas FastAPI con puente HLS v2 SOLO en TestClient.

El origen Jellyfin es ficticio. Se usa SQLite TEMP GUID y una memoria
SQLite de perfiles; NO se toca la DB ni los vídeos ni los puertos reales.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from worker.retirement_hls_session_lab_0031 import AdmisionHLSLab0031
from worker.retirement_playback_admission_0027 import MARKER

import app.auth as auth
import app.jellyfin_playback as playback
from app.config import Settings
from app.database import get_session
from app.jellyfin_hls import sign_hls_url
from app.main import app
from app.models import Medio, Perfil
from app.retirement_authenticated_gate_lab_0029 import (
    AuthenticatedPlaybackGateLab0029,
    VerificadorPerfilLab0029,
)
from app.retirement_hls_bridge_contract_0032 import get_hls_bridge_0032
from app.retirement_hls_capability_lab_0031 import (
    cookie_fingerprint_0031,
    verify_hls_v2_0031,
)
from app.retirement_hls_route_bridge_lab_0032 import HLSRouteBridgeLab0032


@pytest.fixture
def harness(monkeypatch):
    root = Path(tempfile.gettempdir()) / ("viewtv-admission-0027-" + uuid.uuid4().hex)
    root.mkdir(mode=0o700)
    marker = root / "marca-0027.txt"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(marker, flags, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(MARKER)
    lab = AdmisionHLSLab0031(root)
    engine = create_engine(
        "sqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Perfil(id=17, nombre="Perfil ficticio A", pin_hash="test"),
            Perfil(id=18, nombre="Perfil ficticio B", pin_hash="test"),
            Medio(
                id=4, jellyfin_id="fake-jf4", titulo="Ficticia",
                tipo="pelicula", disponible_en_jellyfin=True,
            ),
            Medio(
                id=5, jellyfin_id="fake-jf5", titulo="Otra ficticia",
                tipo="pelicula", disponible_en_jellyfin=True,
            ),
        ])
        db.commit()

    def session_factory():
        return Session(engine)

    def route_db():
        with session_factory() as db:
            yield db

    config = Settings(
        jwt_secret="hls-rutas-0032-ficticio-" + "z" * 48,
        auth_cookie_name="viewtv_session",
        jellyfin_base_url="http://jellyfin-ficticio.invalid:8096",
        jellyfin_api_key="not-a-real-provider-key",
        jellyfin_user_id="ficticio",
    )
    monkeypatch.setattr(auth, "get_settings", lambda: config)
    monkeypatch.setattr(playback, "get_settings", lambda: config)
    bridge = HLSRouteBridgeLab0032(lab, config)

    previous_session = app.dependency_overrides.get(get_session)
    previous_bridge = app.dependency_overrides.get(get_hls_bridge_0032)
    app.dependency_overrides[get_session] = route_db
    app.dependency_overrides[get_hls_bridge_0032] = lambda: bridge
    upstream: list[str] = []

    class FakePlaybackClient:
        def playback_info(self, item_id, start_time_ticks=0):
            assert item_id == "fake-jf4"
            upstream.append("negociacion")
            return {
                "PlaySessionId": "ficticia",
                "MediaSources": [{
                    "Id": "fake-source-1", "SupportsDirectPlay": False,
                    "SupportsTranscoding": True,
                    "TranscodingUrl": (
                        "/videos/abc/master.m3u8?"
                        "ApiKey=provider-private&PlaySessionId=playlist-test"
                    ),
                    "Container": "mkv",
                }],
            }

        def open_stream(self, item_id, source, range_header, if_range):
            assert item_id == "fake-jf4"
            upstream.append("directo")
            return SimpleNamespace(close=lambda: None), httpx.Response(
                206 if range_header else 200,
                content=b"video-ficticio",
                headers={"content-type": "video/mp4"},
            )

    def fake_open_hls(uri, _settings, range_header):
        assert uri.startswith("/videos/abc/")
        assert "ApiKey" not in uri
        if range_header:
            assert range_header == "bytes=0-4"
        upstream.append("hls")
        if uri.split("?", 1)[0].endswith(".m3u8"):
            body = (
                b'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,'
                b'URI="hls1/secret.key"\n#EXTINF:4,\nhls1/fragment.ts\n'
            )
            mimetype = "application/vnd.apple.mpegurl"
        else:
            body = b"fragmento-sintetico"
            mimetype = "video/mp2t"
        return SimpleNamespace(close=lambda: None), httpx.Response(
            200, content=body, headers={"content-type": mimetype},
        )

    monkeypatch.setattr(playback, "JellyfinPlaybackClient", FakePlaybackClient)
    monkeypatch.setattr(playback, "open_hls_upstream", fake_open_hls)
    gated = AuthenticatedPlaybackGateLab0029(
        app, lab, VerificadorPerfilLab0029(session_factory),
    )
    cookie_a = auth.create_access_token(17)
    cookie_a2 = auth.create_access_token(17)
    cookie_b = auth.create_access_token(18)
    try:
        yield {
            "gate": gated, "lab": lab, "bridge": bridge, "config": config,
            "a": cookie_a, "a2": cookie_a2, "b": cookie_b,
            "upstream": upstream,
        }
    finally:
        if previous_session is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous_session
        if previous_bridge is None:
            app.dependency_overrides.pop(get_hls_bridge_0032, None)
        else:
            app.dependency_overrides[get_hls_bridge_0032] = previous_bridge
        engine.dispose()
        shutil.rmtree(root)


def login(harness, cookie):
    client = TestClient(harness["gate"])
    client.cookies.set(harness["config"].auth_cookie_name, cookie)
    return client


def close_hls(harness, token):
    binding = verify_hls_v2_0031(
        token, 4, 17, harness["a"], harness["config"],
    )
    harness["lab"].cerrar_hls(
        4, 17, binding.session_id, binding.generation, binding.video_root,
        cookie_fingerprint_0031(harness["a"], 17, harness["config"]),
    )


def test_real_route_playback_info_hls_v2_and_streams(harness):
    with login(harness, harness["a"]) as client:
        info = client.post("/jellyfin/media/4/playback-info")
        assert info.status_code == 200, info.text
        url = info.json()["fuentes"][0]["url"]
        assert url.startswith("/jellyfin/media/4/hls?token=")
        assert "provider-private" not in url
        token = url.split("token=", 1)[1]
        assert harness["lab"].observar(4)["sesiones_viewtv_pendientes"] == 1

        master = client.get(url)
        assert master.status_code == 200
        assert master.headers["cache-control"] == "private, no-store"
        urls = [
            line.split("token=", 1)[1].split('"')[0]
            for line in master.text.splitlines() if "token=" in line
        ]
        assert len(urls) == 2
        for inner in urls:
            verified = verify_hls_v2_0031(
                inner, 4, 17, harness["a"], harness["config"],
            )
            assert verified.session_id == verify_hls_v2_0031(
                token, 4, 17, harness["a"], harness["config"],
            ).session_id
            fragment = client.get(
                "/jellyfin/media/4/hls?token=" + inner,
                headers={"Range": "bytes=0-4"},
            )
            assert fragment.status_code == 200
            assert fragment.content == b"fragmento-sintetico"

        assert harness["lab"].observar(4)["peticiones_video_pendientes"] == 0
        close_hls(harness, token)
        assert harness["lab"].observar(4)["sesiones_viewtv_pendientes"] == 0
        assert harness["upstream"] == ["negociacion", "hls", "hls", "hls"]


def test_real_routes_reject_stolen_tokens_and_v1(harness):
    with login(harness, harness["a"]) as owner:
        info = owner.post("/jellyfin/media/4/playback-info")
        url = info.json()["fuentes"][0]["url"]
        assert owner.get(url).status_code == 200
    with login(harness, harness["b"]) as other:
        assert other.get(url).status_code == 403
    with login(harness, harness["a2"]) as relogin:
        assert relogin.get(url).status_code == 403
    legacy = sign_hls_url("/videos/abc/master.m3u8", 4, harness["config"])
    with login(harness, harness["a"]) as owner:
        assert owner.get("/jellyfin/media/4/hls?token=" + legacy).status_code == 403
    assert harness["upstream"] == ["negociacion", "hls"]
    close_hls(harness, url.split("token=", 1)[1])


def test_drain_denies_real_playback_direct_master_segments_without_upstream(harness):
    with login(harness, harness["a"]) as client:
        info = client.post("/jellyfin/media/4/playback-info").json()
        url = info["fuentes"][0]["url"]
        master = client.get(url)
        segment = master.text.splitlines()[-1].removeprefix("/api/viewtv")
        before = list(harness["upstream"])
        assert harness["lab"].iniciar_drenaje(4)["estado"] == "drenando"
        assert client.post("/jellyfin/media/4/playback-info").status_code == 423
        assert client.get("/jellyfin/media/4/stream").status_code == 423
        assert client.get(url).status_code == 423
        assert client.get(segment).status_code == 423
        assert harness["upstream"] == before
        close_hls(harness, url.split("token=", 1)[1])
        assert harness["lab"].observar(4)["estado"] == "listo_para_preflight"
        assert harness["lab"].observar_agregado(4)["autoriza_borrado_fisico"] is False


def test_anon_does_not_learn_drain_state(harness):
    harness["lab"].iniciar_drenaje(4)
    with TestClient(harness["gate"]) as client:
        for path in (
            "/jellyfin/media/4/playback-info",
            "/jellyfin/media/4/stream",
            "/jellyfin/media/4/hls?token=" + "a" * 80,
        ):
            response = (
                client.post(path) if path.endswith("/playback-info")
                else client.get(path)
            )
            assert response.status_code == 401
    assert harness["upstream"] == []


def test_upstream_failure_releases_io_but_keeps_session(harness, monkeypatch):
    def failed(_uri, _settings, _range):
        raise playback.JellyfinError("fallo simulado")

    with login(harness, harness["a"]) as client:
        info = client.post("/jellyfin/media/4/playback-info").json()
        url = info["fuentes"][0]["url"]
        monkeypatch.setattr(playback, "open_hls_upstream", failed)
        error = client.get(url)
        assert error.status_code == 503
        observed = harness["lab"].observar(4)
        assert observed["sesiones_viewtv_pendientes"] == 1
        assert observed["peticiones_video_pendientes"] == 0
        close_hls(harness, url.split("token=", 1)[1])
        assert harness["lab"].observar(4)["sesiones_viewtv_pendientes"] == 0


def test_inflight_segment_keeps_drain_blocked_until_body_finishes(
    harness, monkeypatch,
):
    started, release = threading.Event(), threading.Event()
    result: dict[str, object] = {}

    def blocked_stream():
        started.set()
        yield b"first-chunk"
        if not release.wait(timeout=8):
            raise RuntimeError("El test bloqueó un stream ficticio demasiado tiempo.")
        yield b"second-chunk"

    class BlockingByteStream(httpx.SyncByteStream):
        def __iter__(self):
            yield from blocked_stream()

        def close(self):
            return None

    def blocked_open(_uri, _settings, _range):
        return SimpleNamespace(close=lambda: None), httpx.Response(
            200,
            stream=BlockingByteStream(),
            headers={"content-type": "video/mp2t"},
        )

    with login(harness, harness["a"]) as client:
        info = client.post("/jellyfin/media/4/playback-info").json()
        token = info["fuentes"][0]["url"].split("token=", 1)[1]
        master = client.get(info["fuentes"][0]["url"])
        fragment_url = master.text.splitlines()[-1].removeprefix("/api/viewtv")
        monkeypatch.setattr(playback, "open_hls_upstream", blocked_open)

        def reader():
            try:
                result["response"] = client.get(fragment_url)
            except Exception as exc:  # noqa: BLE001 -- conservar fallo del hilo de prueba
                result["error"] = exc

        worker = threading.Thread(target=reader, daemon=True)
        worker.start()
        try:
            assert started.wait(timeout=5), result
            observed = harness["lab"].observar(4)
            assert observed["peticiones_video_pendientes"] >= 2
            assert harness["lab"].iniciar_drenaje(4)["estado"] == "drenando"
            assert harness["lab"].observar(4)["no_hay_sesiones_viewtv"] is False
            with login(harness, harness["a"]) as second:
                assert second.get(fragment_url).status_code == 423
        finally:
            release.set()
            worker.join(timeout=8)
        assert not worker.is_alive(), "La respuesta no terminó tras liberarla."
        assert "error" not in result, result.get("error")
        assert result["response"].status_code == 200
        assert result["response"].content == b"first-chunksecond-chunk"
        assert harness["lab"].observar(4)["peticiones_video_pendientes"] == 0
        assert harness["lab"].observar(4)["estado"] == "drenando"
        close_hls(harness, token)
        assert harness["lab"].observar(4)["estado"] == "listo_para_preflight"


def test_invalid_playlist_releases_real_http_reservation(harness, monkeypatch):
    def malformed(_uri, _settings, _range):
        return SimpleNamespace(close=lambda: None), httpx.Response(
            200,
            content=b"#EXTM3U\nhttp://attacker.invalid/videos/abc/0.ts\n",
            headers={"content-type": "application/vnd.apple.mpegurl"},
        )

    with login(harness, harness["a"]) as client:
        url = client.post("/jellyfin/media/4/playback-info").json()["fuentes"][0]["url"]
        monkeypatch.setattr(playback, "open_hls_upstream", malformed)
        response = client.get(url)
        assert response.status_code == 503
        assert harness["lab"].observar(4)["peticiones_video_pendientes"] == 0
        close_hls(harness, url.split("token=", 1)[1])
        assert harness["lab"].observar(4)["sesiones_viewtv_pendientes"] == 0


def test_bridge_without_authenticated_asgi_guard_denies_all_video_routes(harness):
    """No permitir que alguien inyecte v2 sin activar la barrera de admisión."""
    # Se utiliza app.main real, pero la dependencia HLS se inyectó en memoria.
    # Al no pasar por el wrapper 0029, no existe marca de admisión comprobada.
    with TestClient(app) as client:
        client.cookies.set(harness["config"].auth_cookie_name, harness["a"])
        assert client.post("/jellyfin/media/4/playback-info").status_code == 423
        assert client.get("/jellyfin/media/4/stream").status_code == 423
        v1 = sign_hls_url("/videos/abc/master.m3u8", 4, harness["config"])
        assert client.get("/jellyfin/media/4/hls?token=" + v1).status_code == 423
    assert harness["upstream"] == []
