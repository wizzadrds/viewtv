"""HLS Jellyfin: negociación, rutas firmadas y playlist sin secretos."""

import base64
import json
import time

import httpx
import pytest

from app.config import Settings
from app.jellyfin import JellyfinError
from app.jellyfin_hls import (
    _safe_upstream_url,
    local_hls_url,
    rewrite_hls_playlist,
    sign_hls_url,
    verify_hls_token,
)
from app.jellyfin_playback import VIDEO_DEVICE_PROFILE, _public_playback_info


def settings():
    return Settings(
        jellyfin_base_url="http://jellyfin.test:8096",
        jellyfin_api_key="secret-provider-key",
        jellyfin_user_id="test-user-id",
        jwt_secret="secret-hmac-key-for-tests",
    )


def test_hls_device_profile_enables_transcoding_not_unsafe_direct_mkv():
    profiles = VIDEO_DEVICE_PROFILE["TranscodingProfiles"]
    assert profiles[0]["Protocol"] == "hls"
    assert profiles[0]["VideoCodec"] == "h264"
    assert profiles[0]["AudioCodec"] == "aac"
    assert "mkv" not in VIDEO_DEVICE_PROFILE["DirectPlayProfiles"][0]["Container"]


def test_hls_url_is_signed_and_does_not_contain_provider_api_key():
    source = (
        "/videos/3f17/master.m3u8?ApiKey=private-provider-value"
        "&PlaySessionId=non-secret-session&MediaSourceId=source1"
    )
    token = sign_hls_url(source, 3, settings())
    assert "private-provider-value" not in token
    body = json.loads(base64.urlsafe_b64decode(token.split(".")[0] + "=="))
    assert "ApiKey" not in body["q"]
    assert "private-provider-value" not in json.dumps(body)
    assert verify_hls_token(token, 3, settings()).startswith("/videos/3f17/master.m3u8?")
    with pytest.raises(JellyfinError):
        verify_hls_token(token, 4, settings())
    with pytest.raises(JellyfinError):
        verify_hls_token(token[:-3] + "abc", 3, settings())


def test_hls_rejects_expired_links_and_forbidden_upstream_origins():
    token = sign_hls_url("/videos/3f17/master.m3u8", 3, settings(), expires_at=int(time.time()) - 1)
    with pytest.raises(JellyfinError):
        verify_hls_token(token, 3, settings())
    for url in (
        "http://malicious.example/videos/id/master.m3u8",
        "//malicious.example/videos/id/master.m3u8",
        "/etc/passwd",
        "/Videos/id/../../../private/master.m3u8",
        "/videos/id/master.m3u8#evil",
        "/videos/id/secret.html",
        "/videos/id/..%2Fadmin/master.m3u8",
    ):
        with pytest.raises(JellyfinError):
            _safe_upstream_url(url, settings().jellyfin_base_url)


def test_hls_manifest_rewrites_variant_segment_and_attribute_links():
    raw = b"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",URI="hls1/audio/main.m3u8?ApiKey=secret-value"
#EXT-X-STREAM-INF:BANDWIDTH=8000000
hls1/main/playlist.m3u8?api_key=secret-value
#EXTINF:4,
hls1/main/0.ts?ApiKey=secret-value
"""
    output = rewrite_hls_playlist(raw, "/videos/123/master.m3u8", 3, settings())
    text = output.decode()
    assert text.startswith("#EXTM3U")
    assert text.count("/api/viewtv/jellyfin/media/3/hls?token=") == 3
    assert "secret-value" not in text
    assert "/videos/123/" not in text
    for line in text.splitlines():
        if "token=" in line:
            token = line.split("token=", 1)[1].split('"')[0]
            uri = verify_hls_token(token, 3, settings())
            assert "ApiKey" not in uri
            assert "/videos/123/hls1/" in uri


def test_hls_manifest_rejects_external_or_unsafe_media():
    for playlist in (
        b"#EXTM3U\nhttp://evil.test/videos/abc/0.ts\n",
        b'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="http://evil.test/videos/a/key.key"\n',
        b"#EXTM3U\n/other/path/fragment.ts\n",
        b"INVALID\nfile.ts\n",
    ):
        with pytest.raises(JellyfinError):
            rewrite_hls_playlist(playlist, "/videos/123/master.m3u8", 3, settings())


def test_hls_info_is_offered_for_transcoding_without_direct_play(monkeypatch):
    monkeypatch.setattr("app.jellyfin_playback.get_settings", settings)
    data = {
        "MediaSources": [
            {
                "Id": "source1",
                "Container": "mkv",
                "SupportsDirectPlay": False,
                "SupportsTranscoding": True,
                "TranscodingUrl": (
                    "/videos/123/master.m3u8?ApiKey=secret-provider-key&PlaySessionId=ps"
                ),
            }
        ]
    }
    result = _public_playback_info(data, 3)
    assert result["estado"] == "listo"
    assert result["fuentes"][0]["modo"] == "hls"
    assert result["fuentes"][0]["reproduccion_directa"] is False
    assert result["fuentes"][0]["url"].startswith("/jellyfin/media/3/hls?token=")
    assert "secret-provider-key" not in str(result)
    assert "videos/123" not in str(result)


def test_hls_direct_play_remains_preferred():
    result = _public_playback_info(
        {"MediaSources": [{"Id": "src", "Container": "mp4", "SupportsDirectPlay": True}]}, 3
    )
    assert result["estado"] == "listo"
    assert result["fuentes"][0]["modo"] == "direct"


def test_hls_manifest_size_limit():
    with pytest.raises(JellyfinError):
        rewrite_hls_playlist(
            b"#EXTM3U\n" + b"a" * (2 * 1024 * 1024), "/videos/123/master.m3u8", 3, settings()
        )


def test_hls_upstream_uses_private_authorization_and_strips_api_key():
    from app.jellyfin_hls import open_hls_upstream

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "jellyfin.test"
        assert request.url.path == "/videos/abc/hls1/main/0.ts"
        assert "ApiKey" not in str(request.url)
        assert request.headers["Authorization"] == 'MediaBrowser Token="secret-provider-key"'
        assert request.headers["Range"] == "bytes=0-1023"
        return httpx.Response(
            206,
            content=b"mpeg-ts-sample",
            headers={"Content-Type": "video/mp2t", "Content-Range": "bytes 0-13/1500"},
        )

    client, response = open_hls_upstream(
        "/videos/abc/hls1/main/0.ts?ApiKey=very-private-key",
        settings(),
        "bytes=0-1023",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert response.status_code == 206
        assert response.read() == b"mpeg-ts-sample"
    finally:
        response.close()
        client.close()


def test_hls_upstream_rejects_redirect_and_nonexistent_segment():
    from app.jellyfin_hls import open_hls_upstream

    transport = httpx.MockTransport(
        lambda _req: httpx.Response(302, headers={"Location": "http://evil.example/video"})
    )
    with pytest.raises(JellyfinError):
        open_hls_upstream("/videos/id/hls1/main/0.ts", settings(), transport=transport)


def test_hls_route_requires_profile():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/jellyfin/media/3/hls?token=" + "a" * 60)
        assert response.status_code == 401


def test_hls_route_rewrites_manifest_and_streams_segment_with_profile(monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine

    from app.auth import get_current_profile
    from app.database import get_session
    from app.main import app
    from app.models import Medio, Perfil

    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        m = Medio(
            jellyfin_id="jellyfin-test-3",
            titulo="Nadie 2",
            tipo="pelicula",
            disponible_en_jellyfin=True,
        )
        session.add(m)
        session.commit()
        mid = m.id

    def fake_session():
        with Session(engine) as session:
            yield session

    def fake_profile():
        return Perfil(id=17, nombre="Test")

    previous_session = app.dependency_overrides.get(get_session)
    previous_profile = app.dependency_overrides.get(get_current_profile)
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_current_profile] = fake_profile
    monkeypatch.setattr("app.jellyfin_playback.get_settings", settings)

    upstream_uris = []

    def fake_open(uri, _settings, _range):
        upstream_uris.append(uri)
        if uri.endswith(".ts"):
            response = httpx.Response(
                206,
                content=b"test-packet",
                headers={"content-type": "video/mp2t", "content-range": "bytes 0-10/20"},
            )
        else:
            response = httpx.Response(
                200,
                content=b"#EXTM3U\n#EXTINF:4,\nhls1/main/0.ts?ApiKey=secret-provider-key\n",
                headers={"content-type": "application/vnd.apple.mpegurl"},
            )
        return SimpleNamespace(close=lambda: None), response

    monkeypatch.setattr("app.jellyfin_playback.open_hls_upstream", fake_open)
    try:
        with TestClient(app) as client:
            start = local_hls_url(
                "/videos/abc/master.m3u8?ApiKey=secret-provider-key", mid, settings()
            )
            playlist = client.get(start)
            assert playlist.status_code == 200, playlist.text
            assert playlist.headers["content-type"].startswith("application/vnd.apple.mpegurl")
            assert "secret-provider-key" not in playlist.text
            assert "ApiKey=" not in playlist.text
            path = playlist.text.strip().splitlines()[-1]
            assert path.startswith("/api/viewtv/jellyfin/media/")
            fragment = client.get(path.removeprefix("/api/viewtv"))
            assert fragment.status_code == 206
            assert fragment.content == b"test-packet"
            assert fragment.headers.get("content-range") == "bytes 0-10/20"
            assert len(upstream_uris) == 2
            assert all("ApiKey" not in path for path in upstream_uris)
            wrong = client.get(local_hls_url("/videos/abc/master.m3u8", mid + 10, settings()))
            assert wrong.status_code == 404
    finally:
        if previous_profile is None:
            app.dependency_overrides.pop(get_current_profile, None)
        else:
            app.dependency_overrides[get_current_profile] = previous_profile
        if previous_session is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous_session
        engine.dispose()
