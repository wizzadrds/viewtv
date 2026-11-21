import json

import httpx
import pytest

from app.config import Settings
from app.jellyfin import JellyfinError
from app.jellyfin_playback import JellyfinPlaybackClient, _public_playback_info


def make_settings() -> Settings:
    return Settings(
        jellyfin_base_url="http://jellyfin.test:8096",
        jellyfin_api_key="private-test-key",
        jellyfin_user_id="test-user-id",
        jellyfin_timeout_seconds=5,
    )


def test_playback_info_posts_device_profile_and_sanitizes_server_urls():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/Items/jf-item-1/PlaybackInfo"
        assert request.headers["Authorization"] == 'MediaBrowser Token="private-test-key"'
        assert request.url.params["IsPlayback"] == "true"
        assert request.url.params["UserId"] == "test-user-id"
        payload = json.loads(request.content)
        assert payload["DeviceProfile"]["Name"] == "VIEWTV Web"
        assert payload["EnableTranscoding"] is True
        return httpx.Response(
            200,
            json={
                "PlaySessionId": "session-1",
                "MediaSources": [
                    {
                        "Id": "source-1",
                        "Container": "mp4",
                        "Bitrate": 1_500_000,
                        "SupportsDirectPlay": True,
                        "DirectStreamUrl": "/Videos/jf-item-1/stream?api_key=secret",
                        "TranscodingUrl": "/Videos/jf-item-1/master.m3u8?api_key=secret",
                    }
                ],
            },
        )

    data = JellyfinPlaybackClient(make_settings(), httpx.MockTransport(handler)).playback_info(
        "jf-item-1", 0
    )
    public = _public_playback_info(data, 7)
    assert public["estado"] == "listo"
    assert public["fuentes"][0]["url"] == ("/jellyfin/media/7/stream?media_source_id=source-1")
    assert "api_key" not in str(public)
    assert "TranscodingUrl" not in str(public)


def test_playback_info_marks_transcoding_when_direct_play_is_unavailable():
    public = _public_playback_info(
        {
            "MediaSources": [
                {
                    "Id": "source-1",
                    "Container": "mkv",
                    "SupportsDirectPlay": False,
                    "TranscodingUrl": "/private/transcode?api_key=secret",
                }
            ]
        },
        7,
    )
    assert public["estado"] == "requiere_transcodificacion"
    assert public["fuentes"][0]["url"] is None
    assert "secret" not in str(public)


def test_stream_forwards_range_and_keeps_authorization_server_side():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/Videos/jf-item-1/stream"
        assert request.url.params["static"] == "true"
        assert request.url.params["mediaSourceId"] == "source-1"
        assert request.headers["Range"] == "bytes=100-199"
        assert request.headers["If-Range"] == '"etag-1"'
        assert request.headers["Authorization"] == 'MediaBrowser Token="private-test-key"'
        return httpx.Response(
            206,
            content=b"video-fragment",
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": "14",
                "Content-Range": "bytes 100-113/1000",
                "Accept-Ranges": "bytes",
            },
        )

    client, response = JellyfinPlaybackClient(
        make_settings(), httpx.MockTransport(handler)
    ).open_stream("jf-item-1", "source-1", "bytes=100-199", '"etag-1"')
    try:
        assert response.status_code == 206
        assert response.read() == b"video-fragment"
        assert response.headers["Content-Range"] == "bytes 100-113/1000"
    finally:
        response.close()
        client.close()


def test_stream_rejects_non_video_response():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>", headers={"Content-Type": "text/html"})

    with pytest.raises(JellyfinError, match="formato de vídeo"):
        JellyfinPlaybackClient(make_settings(), httpx.MockTransport(handler)).open_stream(
            "jf-item-1", None, None, None
        )


def test_stream_maps_missing_video_to_lookup_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with pytest.raises(LookupError, match="no encuentra"):
        JellyfinPlaybackClient(make_settings(), httpx.MockTransport(handler)).open_stream(
            "jf-item-1", None, None, None
        )


def test_playback_info_disables_automatically_burned_subtitles_with_pinned_source():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            assert "MediaSourceId" not in body
            assert "SubtitleStreamIndex" not in body
            return httpx.Response(200, json={
                "MediaSources": [{
                    "Id": "source-1", "SupportsDirectPlay": False,
                    "SupportsTranscoding": True,
                    "TranscodingUrl": (
                        "/Videos/abc/master.m3u8?"
                        "SubtitleStreamIndex=2&SubtitleMethod=Encode&ApiKey=SECRET"
                    ),
                }]
            })
        assert body["MediaSourceId"] == "source-1"
        assert body["SubtitleStreamIndex"] == -1
        assert body["AlwaysBurnInSubtitleWhenTranscoding"] is False
        assert request.url.params["MediaSourceId"] == "source-1"
        assert request.url.params["SubtitleStreamIndex"] == "-1"
        return httpx.Response(200, json={
            "MediaSources": [{
                "Id": "source-1", "SupportsDirectPlay": False,
                "SupportsTranscoding": True,
                "TranscodingUrl": "/Videos/abc/master.m3u8?SubtitleMethod=Encode&ApiKey=SECRET",
            }]
        })

    result = JellyfinPlaybackClient(make_settings(), httpx.MockTransport(handler)).playback_info(
        "jf-item-1"
    )
    assert len(calls) == 2
    assert result["MediaSources"][0]["Id"] == "source-1"
    assert "SubtitleStreamIndex" not in result["MediaSources"][0]["TranscodingUrl"]


def test_playback_info_fails_closed_when_subtitle_burn_in_persists():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={
            "MediaSources": [{
                "Id": "source-1", "SupportsDirectPlay": False,
                "SupportsTranscoding": True,
                "TranscodingUrl": (
                    "/Videos/abc/master.m3u8?SubtitleStreamIndex=2&SubtitleMethod=Encode"
                ),
            }]
        })

    with pytest.raises(JellyfinError, match="subtítulos incrustados"):
        JellyfinPlaybackClient(make_settings(), httpx.MockTransport(handler)).playback_info(
            "jf-item-1"
        )
    assert len(calls) == 2


def test_playback_info_keeps_multiple_sources_unchanged():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={
            "MediaSources": [
                {
                    "Id": sid, "SupportsDirectPlay": False,
                    "SupportsTranscoding": True,
                    "TranscodingUrl": (
                        "/Videos/abc/master.m3u8?SubtitleStreamIndex=2&SubtitleMethod=Encode"
                    ),
                } for sid in ("source-1", "source-2")
            ]
        })

    data = JellyfinPlaybackClient(make_settings(), httpx.MockTransport(handler)).playback_info(
        "jf-item-1"
    )
    assert len(data["MediaSources"]) == 2
    assert len(calls) == 1
