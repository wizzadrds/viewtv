"""0029 — cookie real de VIEWTV ANTES de revelar drenaje, SOLO TestClient.

Usa get_current_profile auténtico + SQLite de perfiles EN MEMORIA y
upstream Jellyfin totalmente ficticio; no se conecta a la API productiva.
La capa nueva NO está registrada en app.main ni permite borrar ficheros.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from worker.retirement_playback_admission_0027 import MARKER
from worker.retirement_profile_admission_0029 import AdmisionPerfilLab0029

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


@pytest.fixture
def harness(monkeypatch):
    root = Path(tempfile.gettempdir()) / (
        "viewtv-admission-0027-" + uuid.uuid4().hex
    )
    root.mkdir(mode=0o700)
    marker = root / "marca-0027.txt"
    fd = os.open(
        marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY
        | getattr(os, "O_NOFOLLOW", 0), 0o600,
    )
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(MARKER)
    lab = AdmisionPerfilLab0029(root)

    engine = create_engine(
        "sqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Perfil(id=17, nombre="Perfil ficticio A", pin_hash="fake-test"),
            Perfil(id=18, nombre="Perfil ficticio B", pin_hash="fake-test"),
            Perfil(id=19, nombre="Perfil ficticio inactivo", pin_hash="fake-test", activo=False),
            Medio(id=4, jellyfin_id="jf-ficticio-0029",
                  titulo="Pelicula ficticia", tipo="pelicula", disponible_en_jellyfin=True),
        ])
        db.commit()

    def db_session():
        return Session(engine)

    def route_db():
        with db_session() as db:
            yield db

    config = Settings(
        jwt_secret="testing-secret-0029-" + "z" * 48,
        auth_cookie_name="viewtv_session",
        jellyfin_base_url="http://ficticio-jf.invalid:8096",
        jellyfin_api_key="test-not-real",
        jellyfin_user_id="jf-user-fictional",
    )
    monkeypatch.setattr(auth, "get_settings", lambda: config)
    monkeypatch.setattr(playback, "get_settings", lambda: config)

    old_session = app.dependency_overrides.get(get_session)
    app.dependency_overrides[get_session] = route_db
    upstream: list[str] = []

    class JellyfinFicticio:
        def __init__(self):
            pass

        def playback_info(self, item_id, start_time_ticks=0):
            assert item_id == "jf-ficticio-0029"
            upstream.append("negociacion")
            return {"MediaSources": [{
                "Id": "source-fake", "SupportsDirectPlay": True,
                "Container": "mp4",
            }]}

        def open_stream(self, item_id, source, range_header, if_range):
            assert item_id == "jf-ficticio-0029"
            upstream.append("directo")
            return SimpleNamespace(close=lambda: None), httpx.Response(
                200, content=b"video-sintetico",
                headers={"content-type": "video/mp4"},
            )

    def fake_open_hls(uri, settings, range_header):
        assert uri.startswith("/videos/abc/")
        upstream.append("hls")
        is_list = uri.split("?", 1)[0].endswith(".m3u8")
        return SimpleNamespace(close=lambda: None), httpx.Response(
            200,
            content=(
                b"#EXTM3U\n#EXTINF:4,\nhls1/main/0.ts\n"
                if is_list else b"segmento-sintetico"
            ),
            headers={
                "content-type": (
                    "application/vnd.apple.mpegurl" if is_list
                    else "video/mp2t"
                ),
            },
        )

    monkeypatch.setattr(playback, "JellyfinPlaybackClient", JellyfinFicticio)
    monkeypatch.setattr(playback, "open_hls_upstream", fake_open_hls)

    gate = AuthenticatedPlaybackGateLab0029(
        app, lab, VerificadorPerfilLab0029(db_session),
    )
    signed = sign_hls_url("/videos/abc/master.m3u8", 4, config)
    cookie_17 = auth.create_access_token(17)
    cookie_18 = auth.create_access_token(18)
    cookie_inactive = auth.create_access_token(19)
    expired = jwt.encode(
        {
            "sub": "17",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        config.jwt_secret,
        algorithm="HS256",
    )
    try:
        yield {
            "lab": lab, "app": gate, "upstream": upstream,
            "cookie": config.auth_cookie_name,
            "valid": cookie_17, "other": cookie_18,
            "inactive": cookie_inactive, "expired": expired,
            "hls": "/jellyfin/media/4/hls?token=" + signed,
        }
    finally:
        if old_session is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = old_session
        engine.dispose()
        shutil.rmtree(root)


@pytest.mark.parametrize(("method", "path"), [
    ("POST", "/jellyfin/media/4/playback-info"),
    ("GET", "/jellyfin/media/4/stream"),
    ("GET", "/jellyfin/media/4/hls?token=unknown"),
    ("GET", "/jellyfin/media/4/nueva-ruta"),
    ("GET", "/jellyfin/media/04/hls"),
])
@pytest.mark.parametrize("drain_first", [True, False])
def test_anonimo_no_descubre_estado_ni_contacta_jellyfin(
    harness, method, path, drain_first,
):
    if drain_first:
        harness["lab"].iniciar_drenaje(4)
    with TestClient(harness["app"]) as client:
        response = client.request(method, path)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "private, no-store"
    assert harness["upstream"] == []
    assert harness["lab"].observar(4)["sesiones_viewtv_pendientes"] == 0


@pytest.mark.parametrize("actor", ["expired", "inactive", "invalid"])
@pytest.mark.parametrize("drain_first", [True, False])
def test_expirado_inactivo_o_falsificado_siempre_es_401(
    harness, actor, drain_first,
):
    if drain_first:
        harness["lab"].iniciar_drenaje(4)
    token = "wrong-token" if actor == "invalid" else harness[actor]
    with TestClient(harness["app"]) as client:
        client.cookies.set(harness["cookie"], token)
        status = client.get("/jellyfin/media/4/stream")
        assert status.status_code == 401
    assert not harness["upstream"]


def test_perfil_activo_accede_y_drenaje_deniega_antes_del_upstream(harness):
    with TestClient(harness["app"]) as client:
        client.cookies.set(harness["cookie"], harness["valid"])
        assert client.post("/jellyfin/media/4/playback-info").status_code == 200
        assert client.get("/jellyfin/media/4/stream").content == b"video-sintetico"
        playlist = client.get(harness["hls"])
        assert playlist.status_code == 200
        segment = playlist.text.splitlines()[-1].removeprefix("/api/viewtv")
        assert segment.startswith("/jellyfin/media/4/hls?token=")
        assert client.get(segment).content == b"segmento-sintetico"
        assert harness["upstream"] == ["negociacion", "directo", "hls", "hls"]
        assert harness["lab"].observar(4)["sesiones_viewtv_pendientes"] == 0
        assert harness["lab"].iniciar_drenaje(4)["estado"] == "listo_para_preflight"
        for method, path in (
            ("POST", "/jellyfin/media/4/playback-info"),
            ("GET", "/jellyfin/media/4/stream"),
            ("GET", harness["hls"]),
            ("GET", segment),
        ):
            response = client.request(method, path)
            assert response.status_code == 423
            assert response.headers["cache-control"] == "private, no-store"
        assert harness["upstream"] == ["negociacion", "directo", "hls", "hls"]
    assert harness["lab"].observar_agregado(4)["autoriza_borrado_fisico"] is False


def test_ruta_futura_identificada_tras_autenticar_es_404(harness):
    with TestClient(harness["app"]) as client:
        client.cookies.set(harness["cookie"], harness["valid"])
        assert client.get("/jellyfin/media/4/futuro").status_code == 404
        harness["lab"].iniciar_drenaje(4)
        assert client.get("/jellyfin/media/4/futuro").status_code == 404
    assert not harness["upstream"]


def test_perfiles_distintos_tienen_igual_rechazo_en_drenaje(harness):
    harness["lab"].iniciar_drenaje(4)
    with TestClient(harness["app"]) as client:
        for cookie in (harness["valid"], harness["other"]):
            client.cookies.set(harness["cookie"], cookie)
            assert client.get("/jellyfin/media/4/stream").status_code == 423
    assert not harness["upstream"]


def test_limitacion_hls_aun_no_vincula_token_a_perfil(harness):
    """Hallazgo: la URL firmada de VIEWTV sigue transferible entre perfiles.

    Esta es una DEMOSTRACIÓN DEL LÍMITE, no una propiedad deseada de producción.
    """
    with TestClient(harness["app"]) as client:
        client.cookies.set(harness["cookie"], harness["valid"])
        assert client.get(harness["hls"]).status_code == 200
        client.cookies.set(harness["cookie"], harness["other"])
        assert client.get(harness["hls"]).status_code == 200
    assert harness["upstream"] == ["hls", "hls"]
    assert harness["lab"].observar_agregado(4)["autoriza_borrado_fisico"] is False


def test_ni_en_una_pelicula_distinta_se_omiten_cookies(harness):
    with TestClient(harness["app"]) as client:
        assert client.get("/jellyfin/media/5/stream").status_code == 401
        client.cookies.set(harness["cookie"], harness["valid"])
        assert client.get("/jellyfin/media/5/stream").status_code == 404
    assert not harness["upstream"]


def test_sin_provisionar_autenticacion_no_admite_ningun_stream(harness):
    failing = AuthenticatedPlaybackGateLab0029(
        app,
        harness["lab"],
        VerificadorPerfilLab0029(lambda: (_ for _ in ()).throw(OSError("token privado"))),
    )
    with TestClient(failing) as client:
        client.cookies.set(harness["cookie"], harness["valid"])
        result = client.get("/jellyfin/media/4/stream")
        assert result.status_code == 503
        assert "token privado" not in result.text
    assert harness["upstream"] == []


def test_no_se_ha_desplegado_capa_en_app_main(harness):
    assert all(
        m.cls is not AuthenticatedPlaybackGateLab0029
        for m in app.user_middleware
    )
    assert not isinstance(app, AuthenticatedPlaybackGateLab0029)
    assert harness["lab"].observar_agregado(4)["autoriza_borrado_fisico"] is False
