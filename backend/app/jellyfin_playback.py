import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.auth import get_current_profile
from app.config import Settings, get_settings
from app.database import get_session
from app.jellyfin import JellyfinError
from app.models import Medio, Perfil

router = APIRouter(prefix="/jellyfin", tags=["reproducción"])
VIDEO_DEVICE_PROFILE: dict[str, Any] = {
    "Name": "VIEWTV Web",
    "MaxStreamingBitrate": 20_000_000,
    "DirectPlayProfiles": [
        {
            "Type": "Video",
            "Container": "mp4,m4v,webm",
            "VideoCodec": "h264,vp9,av1",
            "AudioCodec": "aac,mp3,opus,vorbis",
        }
    ],
    "SubtitleProfiles": [
        {"Format": "vtt", "Method": "External"},
        {"Format": "srt", "Method": "External"},
    ],
}
STREAM_RESPONSE_HEADERS = (
    "accept-ranges",
    "content-length",
    "content-range",
    "content-type",
    "etag",
    "last-modified",
)


class JellyfinPlaybackClient:
    """Cliente de negociación y streaming; la clave nunca sale del backend."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.jellyfin_base_url.rstrip("/")
        self.api_key = self.settings.jellyfin_api_key
        self.timeout = self.settings.jellyfin_timeout_seconds
        self.transport = transport
        if not self.base_url or not self.api_key:
            raise JellyfinError("Jellyfin no está configurado.")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f'MediaBrowser Token="{self.api_key}"',
            "Accept": "application/json",
        }

    def playback_info(self, item_id: str, start_time_ticks: int = 0) -> dict[str, Any]:
        encoded_id = quote(item_id, safe="")
        payload = {
            "DeviceProfile": VIDEO_DEVICE_PROFILE,
            "StartTimeTicks": start_time_ticks,
            "EnableDirectPlay": True,
            "EnableDirectStream": True,
            "EnableTranscoding": True,
            "AllowVideoStreamCopy": True,
            "AllowAudioStreamCopy": True,
        }
        try:
            with httpx.Client(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = client.post(
                    f"/Items/{encoded_id}/PlaybackInfo",
                    params={"IsPlayback": "true", "AutoOpenLiveStream": "true"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise JellyfinError("No se pudo negociar la reproducción con Jellyfin.") from exc
        if not isinstance(data, dict):
            raise JellyfinError("Jellyfin devolvió datos de reproducción no válidos.")
        return data

    def open_stream(
        self,
        item_id: str,
        media_source_id: str | None,
        range_header: str | None,
        if_range: str | None,
    ) -> tuple[httpx.Client, httpx.Response]:
        encoded_id = quote(item_id, safe="")
        params: dict[str, str] = {"static": "true"}
        if media_source_id:
            params["mediaSourceId"] = media_source_id
        headers = {"Accept": "video/*,application/octet-stream", "Accept-Encoding": "identity"}
        if range_header:
            headers["Range"] = range_header
        if if_range:
            headers["If-Range"] = if_range

        client = httpx.Client(
            base_url=self.base_url,
            headers=self.headers,
            timeout=httpx.Timeout(
                connect=self.timeout,
                read=None,
                write=self.timeout,
                pool=self.timeout,
            ),
            transport=self.transport,
        )
        try:
            request = client.build_request(
                "GET",
                f"/Videos/{encoded_id}/stream",
                params=params,
                headers=headers,
            )
            response = client.send(request, stream=True)
        except httpx.HTTPError as exc:
            client.close()
            raise JellyfinError("No se pudo abrir el vídeo en Jellyfin.") from exc

        if response.status_code not in {200, 206, 416}:
            upstream_status = response.status_code
            response.close()
            client.close()
            if upstream_status == 404:
                raise LookupError("Jellyfin no encuentra el archivo de vídeo.")
            raise JellyfinError("Jellyfin no pudo entregar el vídeo.")
        content_type = response.headers.get("content-type", "").split(";")[0].lower()
        if response.status_code != 416 and not (
            content_type.startswith("video/") or content_type == "application/octet-stream"
        ):
            response.close()
            client.close()
            raise JellyfinError("Jellyfin devolvió un formato de vídeo no permitido.")
        return client, response


def _public_playback_info(data: dict[str, Any], media_id: int) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    raw_sources = data.get("MediaSources")
    if isinstance(raw_sources, list):
        for source in raw_sources:
            if not isinstance(source, dict):
                continue
            source_id = source.get("Id")
            if not isinstance(source_id, str) or not source_id:
                continue
            direct_play = source.get("SupportsDirectPlay") is True
            sources.append(
                {
                    "id": source_id,
                    "contenedor": source.get("Container"),
                    "bitrate": source.get("Bitrate"),
                    "reproduccion_directa": direct_play,
                    "requiere_transcodificacion": not direct_play,
                    "url": (
                        f"/jellyfin/media/{media_id}/stream"
                        f"?media_source_id={quote(source_id, safe='')}"
                        if direct_play
                        else None
                    ),
                }
            )
    playable = any(source["reproduccion_directa"] for source in sources)
    return {
        "estado": "listo" if playable else "requiere_transcodificacion",
        "play_session_id": data.get("PlaySessionId"),
        "fuentes": sources,
    }


@router.post("/media/{media_id}/playback-info")
def get_media_playback_info(
    media_id: int,
    _profile: Perfil = Depends(get_current_profile),
    session: Session = Depends(get_session),
    start_time_ticks: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    media = session.get(Medio, media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Elemento no encontrado.")
    try:
        data = JellyfinPlaybackClient().playback_info(media.jellyfin_id, start_time_ticks)
    except JellyfinError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None
    return _public_playback_info(data, media_id)


@router.get("/media/{media_id}/stream")
def stream_media(
    media_id: int,
    _profile: Perfil = Depends(get_current_profile),
    session: Session = Depends(get_session),
    media_source_id: str | None = Query(default=None, max_length=128, pattern=r"^[A-Za-z0-9-]+$"),
    range_header: str | None = Header(default=None, alias="Range", max_length=128),
    if_range: str | None = Header(default=None, alias="If-Range", max_length=256),
) -> StreamingResponse:
    media = session.get(Medio, media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Elemento no encontrado.")
    if range_header and not re.fullmatch(r"bytes=\d*-\d*(,\d*-\d*)*", range_header):
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Rango no válido.",
        )
    try:
        upstream_client, upstream = JellyfinPlaybackClient().open_stream(
            media.jellyfin_id,
            media_source_id,
            range_header,
            if_range,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vídeo no encontrado.",
        ) from None
    except JellyfinError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None

    headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() in STREAM_RESPONSE_HEADERS
    }

    if upstream.status_code == 416:
        content = upstream.read()
        upstream.close()
        upstream_client.close()
        return StreamingResponse(
            iter((content,)),
            status_code=416,
            headers=headers,
        )

    def chunks() -> Iterator[bytes]:
        try:
            yield from upstream.iter_bytes(chunk_size=64 * 1024)
        finally:
            upstream.close()
            upstream_client.close()

    return StreamingResponse(
        chunks(),
        status_code=upstream.status_code,
        headers=headers,
        media_type=upstream.headers.get("content-type", "application/octet-stream"),
    )
