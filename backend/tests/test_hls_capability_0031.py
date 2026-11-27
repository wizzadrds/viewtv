"""0031: pruebas de capacidades HLS con HTTP real y upstream ficticio.

Sin tocar app.main, Jellyfin/qBit, SQLite productiva ni medios NTFS.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from worker.retirement_hls_session_lab_0031 import AdmisionHLSLab0031
from worker.retirement_playback_admission_0027 import MARKER, AdmisionRechazada

import app.auth as auth
from app.auth import get_current_profile
from app.config import Settings
from app.database import get_session
from app.jellyfin import JellyfinError
from app.jellyfin_hls import sign_hls_url
from app.models import Medio, Perfil
from app.retirement_hls_capability_lab_0031 import (
    HLSContext0031,
    _b64encode,
    _key,
    cookie_fingerprint_0031,
    rewrite_hls_v2_0031,
    sign_hls_v2_0031,
    verify_hls_v2_0031,
)


@pytest.fixture
def hls_lab(monkeypatch):
    root = Path(tempfile.gettempdir()) / ("viewtv-admission-0027-" + uuid.uuid4().hex)
    root.mkdir(mode=0o700)
    marker = root / "marca-0027.txt"
    fd = os.open(
        marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY
        | getattr(os, "O_NOFOLLOW", 0), 0o600,
    )
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(MARKER)
    lab = AdmisionHLSLab0031(root)
    config = Settings(
        jwt_secret="viewtv-capability-0031-" + "z" * 48,
        auth_cookie_name="viewtv_session",
        jellyfin_base_url="http://jellyfin-ficticio.invalid:8096",
        jellyfin_api_key="not-a-real-provider-key",
    )
    monkeypatch.setattr(auth, "get_settings", lambda: config)
    engine = create_engine(
        "sqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Perfil(id=17, nombre="A", pin_hash="sandbox"),
            Perfil(id=18, nombre="B", pin_hash="sandbox"),
            Medio(id=4, titulo="Prueba", jellyfin_id="fake-4", tipo="pelicula",
                  disponible_en_jellyfin=True),
            Medio(id=5, titulo="Otra prueba", jellyfin_id="fake-5", tipo="pelicula",
                  disponible_en_jellyfin=True),
        ])
        db.commit()

    def route_db():
        with Session(engine) as db:
            yield db

    api = FastAPI()
    api.dependency_overrides[get_session] = route_db
    upstream: list[str] = []

    @api.post("/lab/abrir/{media_id}")
    def abrir(
        media_id: int, request: Request,
        profile: Perfil = Depends(get_current_profile),
    ):
        cookie = request.cookies[config.auth_cookie_name]
        fp = cookie_fingerprint_0031(cookie, profile.id, config)
        try:
            session_id, generation = lab.abrir_hls(media_id, profile.id, "abc", fp)
        except AdmisionRechazada:
            raise HTTPException(423, "Película no disponible.") from None
        context = HLSContext0031(
            media_id, profile.id, session_id, generation, "abc", cookie,
        )
        return {
            "url": "/jellyfin/media/" + str(media_id) + "/hls?token=" +
            sign_hls_v2_0031("/videos/abc/master.m3u8", context, config),
            "session": session_id, "generation": generation,
        }

    @api.get("/jellyfin/media/{media_id}/hls")
    def video(
        media_id: int, request: Request,
        token: str = Query(min_length=40, max_length=8192),
        profile: Perfil = Depends(get_current_profile),
        db: Session = Depends(get_session),
    ):
        medium = db.get(Medio, media_id)
        if medium is None or not medium.disponible_en_jellyfin:
            raise HTTPException(404, "Vídeo no disponible.")
        cookie = request.cookies[config.auth_cookie_name]
        try:
            signed = verify_hls_v2_0031(token, media_id, profile.id, cookie, config)
            io = lab.reservar_lectura_hls(
                media_id, profile.id, signed.session_id, signed.generation,
                signed.video_root, signed.cookie_fingerprint,
            )
        except JellyfinError:
            raise HTTPException(403, "Capacidad inválida.") from None
        except AdmisionRechazada:
            raise HTTPException(423, "Película no disponible.") from None

        upstream.append(signed.uri)
        ctx = HLSContext0031(
            media_id, profile.id, signed.session_id, signed.generation,
            signed.video_root, cookie,
        )
        if signed.uri.endswith(".m3u8"):
            try:
                response = rewrite_hls_v2_0031(
                    b'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="hls1/key.key"\n'
                    b'#EXTINF:4,\nhls1/segment.ts\n',
                    signed.uri, ctx, config,
                )
                return Response(
                    response, media_type="application/vnd.apple.mpegurl",
                    headers={"Cache-Control": "private, no-store"},
                )
            finally:
                lab.terminar_lectura(
                    media_id, profile.id, signed.session_id, io,
                )

        def chunks():
            try:
                yield b"fichero-ficticio"
            finally:
                lab.terminar_lectura(
                    media_id, profile.id, signed.session_id, io,
                )

        return StreamingResponse(
            chunks(), headers={"Cache-Control": "private, no-store"},
        )

    cookie_a = auth.create_access_token(17)
    cookie_a2 = auth.create_access_token(17)
    cookie_b = auth.create_access_token(18)
    try:
        yield {
            "api": api, "lab": lab, "config": config, "root": root,
            "a": cookie_a, "a2": cookie_a2, "b": cookie_b,
            "upstream": upstream,
        }
    finally:
        engine.dispose()
        shutil.rmtree(root)


def _client(lab, cookie):
    client = TestClient(lab["api"])
    client.cookies.set(lab["config"].auth_cookie_name, cookie)
    return client


def _context(lab, opened):
    return HLSContext0031(
        4, 17, opened["session"], opened["generation"], "abc", lab["a"],
    )


def test_login_creates_distinct_jti_per_same_profile(hls_lab):
    lab = hls_lab
    assert lab["a"] != lab["a2"]
    a = jwt.decode(lab["a"], lab["config"].jwt_secret, algorithms=["HS256"])
    b = jwt.decode(lab["a2"], lab["config"].jwt_secret, algorithms=["HS256"])
    assert a["jti"] != b["jti"]
    assert a["sub"] == b["sub"] == "17"


def test_real_http_master_key_segment_range_and_no_upstream_leak(hls_lab):
    lab = hls_lab
    with _client(lab, lab["a"]) as client:
        opened = client.post("/lab/abrir/4").json()
        master = client.get(opened["url"])
        assert master.status_code == 200, master.text
        assert master.headers["cache-control"] == "private, no-store"
        assert "jellyfin-ficticio" not in master.text
        assert "not-a-real-provider-key" not in master.text
        urls = [
            part.split("token=", 1)[1].split('"')[0]
            for part in master.text.splitlines() if "token=" in part
        ]
        assert len(urls) == 2
        for token in urls:
            signed = verify_hls_v2_0031(token, 4, 17, lab["a"], lab["config"])
            assert signed.session_id == opened["session"]
            assert signed.generation == opened["generation"]
            response = client.get("/jellyfin/media/4/hls?token=" + token,
                                  headers={"Range": "bytes=0-3"})
            assert response.status_code == 200
            assert response.content == b"fichero-ficticio"
        assert len(lab["upstream"]) == 3
        lab["lab"].cerrar_hls(
            4, 17, opened["session"], opened["generation"], "abc",
            cookie_fingerprint_0031(lab["a"], 17, lab["config"]),
        )
        assert lab["lab"].observar(4)["sesiones_viewtv_pendientes"] == 0


def test_profile_and_different_login_cannot_reuse_token(hls_lab):
    lab = hls_lab
    with _client(lab, lab["a"]) as owner:
        opened = owner.post("/lab/abrir/4").json()
        assert owner.get(opened["url"]).status_code == 200
    with _client(lab, lab["b"]) as other:
        assert other.get(opened["url"]).status_code == 403
    with _client(lab, lab["a2"]) as other_login:
        assert other_login.get(opened["url"]).status_code == 403
    assert len(lab["upstream"]) == 1


def test_drain_revokes_existing_master_and_segment_before_upstream(hls_lab):
    lab = hls_lab
    with _client(lab, lab["a"]) as client:
        opened = client.post("/lab/abrir/4").json()
        master = client.get(opened["url"])
        segment_url = master.text.splitlines()[-1].removeprefix("/api/viewtv")
        before = len(lab["upstream"])
        assert lab["lab"].iniciar_drenaje(4)["estado"] == "drenando"
        assert client.get(opened["url"]).status_code == 423
        assert client.get(segment_url).status_code == 423
        assert client.post("/lab/abrir/4").status_code == 423
        assert len(lab["upstream"]) == before
        fp = cookie_fingerprint_0031(lab["a"], 17, lab["config"])
        lab["lab"].cerrar_hls(4, 17, opened["session"], opened["generation"], "abc", fp)
        assert lab["lab"].observar(4)["estado"] == "listo_para_preflight"
        assert lab["lab"].iniciar_drenaje(4)["estado"] == "listo_para_preflight"
        assert lab["lab"].observar(5)["estado"] == "libre"


def test_crash_and_restart_preserve_unfinished_read_without_permission(hls_lab):
    lab = hls_lab
    cookie = lab["a"]
    with _client(lab, cookie) as client:
        opened = client.post("/lab/abrir/4").json()
    fp = cookie_fingerprint_0031(cookie, 17, lab["config"])
    request = lab["lab"].reservar_lectura_hls(
        4, 17, opened["session"], opened["generation"], "abc", fp,
    )
    lab["lab"].cerrar_hls(4, 17, opened["session"], opened["generation"], "abc", fp)
    assert lab["lab"].iniciar_drenaje(4)["estado"] == "drenando"
    reopened = AdmisionHLSLab0031(lab["root"])
    assert reopened.observar(4)["peticiones_video_pendientes"] == 1
    assert reopened.observar(4)["estado"] == "drenando"
    assert reopened.observar_agregado(4)["autoriza_borrado_fisico"] is False
    reopened.terminar_lectura(4, 17, opened["session"], request)
    assert reopened.observar(4)["estado"] == "listo_para_preflight"


@pytest.mark.parametrize("alter", [
    "other_movie", "other_profile", "wrong_session", "other_video",
    "wrong_generation", "expired", "future", "old_v1",
])
def test_context_or_expiration_mismatch_fails_closed(hls_lab, alter):
    lab = hls_lab
    with _client(lab, lab["a"]) as client:
        opened = client.post("/lab/abrir/4").json()
    ctx = _context(lab, opened)
    data = dict(ctx.__dict__)
    if alter == "other_movie":
        data["media_id"] = 5
    elif alter == "other_profile":
        data["profile_id"] = 18
    elif alter == "wrong_session":
        data["session_id"] = "a" * 48
    elif alter == "other_video":
        data["video_root"] = "other"
    elif alter == "wrong_generation":
        data["generation"] += 1
    uri = "/videos/" + data["video_root"] + "/master.m3u8"
    if alter == "expired":
        with pytest.raises(JellyfinError):
            sign_hls_v2_0031(uri, ctx, lab["config"], expires_at=int(time.time()) - 1)
    elif alter == "future":
        with pytest.raises(JellyfinError):
            sign_hls_v2_0031(
                uri, ctx, lab["config"], expires_at=int(time.time()) + 5 * 3600,
            )
    elif alter == "old_v1":
        token = sign_hls_url("/videos/abc/master.m3u8", 4, lab["config"])
        with pytest.raises(JellyfinError):
            verify_hls_v2_0031(token, 4, 17, lab["a"], lab["config"])
    elif alter == "other_profile":
        with pytest.raises(JellyfinError):
            sign_hls_v2_0031(uri, HLSContext0031(**data), lab["config"])
    else:
        token = sign_hls_v2_0031(uri, HLSContext0031(**data), lab["config"])
        checked = verify_hls_v2_0031(token, data["media_id"], 17, lab["a"], lab["config"])
        with pytest.raises(AdmisionRechazada):
            lab["lab"].reservar_lectura_hls(
                data["media_id"], 17, checked.session_id, checked.generation,
                checked.video_root, checked.cookie_fingerprint,
            )


@pytest.mark.parametrize("malformed", ["duplicate", "unknown", "boolean", "bad_signature"])
def test_invalid_json_signature_and_types_fail_closed(hls_lab, malformed):
    lab = hls_lab
    with _client(lab, lab["a"]) as client:
        opened = client.post("/lab/abrir/4").json()
    token = sign_hls_v2_0031("/videos/abc/master.m3u8", _context(lab, opened),
                             lab["config"])
    encoded, signature = token.split(".")
    fields = json.loads(base64.urlsafe_b64decode(encoded + "=="))
    if malformed == "duplicate":
        raw = json.dumps(fields)[:-1] + ',"m":4}'
    elif malformed == "unknown":
        fields["unknown"] = True
        raw = json.dumps(fields)
    elif malformed == "boolean":
        fields["g"] = True
        raw = json.dumps(fields)
    else:
        raw = json.dumps(fields)
    updated = _b64encode(raw.encode("utf-8"))
    forged = updated + "." + _b64encode(
        hmac.new(_key(lab["config"]), updated.encode(), hashlib.sha256).digest(),
    )
    if malformed == "bad_signature":
        forged = encoded + "." + ("a" if signature[0] != "a" else "b") + signature[1:]
    with pytest.raises(JellyfinError):
        verify_hls_v2_0031(forged, 4, 17, lab["a"], lab["config"])


def test_cross_video_playlist_rejected_and_jwt_without_jti_rejected(hls_lab):
    lab = hls_lab
    with _client(lab, lab["a"]) as client:
        opened = client.post("/lab/abrir/4").json()
    context = _context(lab, opened)
    with pytest.raises(JellyfinError):
        rewrite_hls_v2_0031(
            b"#EXTM3U\n/videos/unrelated/hls/0.ts\n",
            "/videos/abc/master.m3u8", context, lab["config"],
        )
    with pytest.raises(JellyfinError):
        rewrite_hls_v2_0031(
            b"#EXTM3U\nhttp://attacker.test/videos/abc/0.ts\n",
            "/videos/abc/master.m3u8", context, lab["config"],
        )
    legacy = jwt.encode(
        {"sub": "17", "iat": int(time.time()), "exp": int(time.time()) + 3600},
        lab["config"].jwt_secret, algorithm="HS256",
    )
    with pytest.raises(JellyfinError):
        cookie_fingerprint_0031(legacy, 17, lab["config"])


def test_released_and_corrupted_session_denied(hls_lab):
    lab = hls_lab
    with _client(lab, lab["a"]) as client:
        opened = client.post("/lab/abrir/4").json()
        signed = verify_hls_v2_0031(
            opened["url"].split("token=", 1)[1], 4, 17, lab["a"], lab["config"],
        )
        fp = signed.cookie_fingerprint
        lab["lab"].cerrar_hls(4, 17, signed.session_id, signed.generation, "abc", fp)
        assert client.get(opened["url"]).status_code == 423
        assert not lab["upstream"]
