import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.auth import get_current_profile
from app.config import Settings, get_settings
from app.database import get_session
from app.jellyfin import JellyfinError
from app.jellyfin_hls import (
    MAX_PLAYLIST_BYTES,
    local_hls_url,
    open_hls_upstream,
    rewrite_hls_playlist,
    verify_hls_token,
)
from app.models import Medio, Perfil
from app.retirement_hls_bridge_contract_0032 import (
    HLSAdmissionClosed0032,
    HLSBridge0032,
    get_hls_bridge_0032,
)

router = APIRouter(prefix="/jellyfin", tags=["reproducción"])
VIDEO_DEVICE_PROFILE: dict[str, Any] = {
    "Name": "VIEWTV Web",
    "MaxStreamingBitrate": 8_000_000,
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
    # Un MKV HEVC/E-AC3 no es reproducible directamente en la mayoría
    # de navegadores. Jellyfin debe poder ofrecer H.264/AAC por HLS.
    "TranscodingProfiles": [
        {
            "Type": "Video",
            "Container": "ts",
            "Protocol": "hls",
            "Context": "Streaming",
            "VideoCodec": "h264",
            "AudioCodec": "aac",
            "MaxAudioChannels": "2",
            "MinSegments": "2",
            "SegmentLength": "4",
            "BreakOnNonKeyFrames": False,
        }
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


def _source_with_burned_subtitles(data: dict[str, Any]) -> str | None:
    """Solo una fuente HLS que fuerza incrustar subtítulos en vídeo.

    En la PWA actual no hay selector de subtítulos. Evitar que una pista
    ASS elegida automáticamente ralentice la transcodificación de inicio.
    """
    sources = data.get("MediaSources")
    if not isinstance(sources, list) or len(sources) != 1:
        return None
    source = sources[0]
    if not isinstance(source, dict) or source.get("SupportsDirectPlay") is True:
        return None
    source_id = source.get("Id")
    url = source.get("TranscodingUrl")
    if (
        not isinstance(source_id, str)
        or re.fullmatch(r"[A-Za-z0-9-]{1,128}", source_id) is None
        or not isinstance(url, str)
        or not urlsplit(url).path.lower().endswith(".m3u8")
    ):
        return None
    try:
        query = {key.casefold(): values for key, values in
                 parse_qs(urlsplit(url).query, max_num_fields=100).items()}
    except ValueError:
        return None
    indexes = query.get("subtitlestreamindex", [])
    methods = query.get("subtitlemethod", [])
    if (
        len(indexes) == 1
        and indexes[0].isascii()
        and indexes[0].isdecimal()
        and len(methods) == 1
        and methods[0].casefold() == "encode"
    ):
        return source_id
    return None


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
        self.user_id = self.settings.jellyfin_user_id.strip()
        if not self.base_url or not self.api_key or not self.user_id:
            raise JellyfinError("Jellyfin no está configurado.")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f'MediaBrowser Token="{self.api_key}"',
            "Accept": "application/json",
        }

    def playback_info(
        self,
        item_id: str,
        start_time_ticks: int = 0,
        *,
        media_source_id: str | None = None,
        subtitle_stream_index: int | None = None,
    ) -> dict[str, Any]:
        encoded_id = quote(item_id, safe="")
        payload: dict[str, Any] = {
            "DeviceProfile": VIDEO_DEVICE_PROFILE,
            "StartTimeTicks": start_time_ticks,
            "EnableDirectPlay": True,
            "EnableDirectStream": True,
            "EnableTranscoding": True,
            "AllowVideoStreamCopy": True,
            "AllowAudioStreamCopy": True,
        }
        params = {
            "UserId": self.user_id,
            "IsPlayback": "true",
            "AutoOpenLiveStream": "true",
        }
        if media_source_id is not None:
            payload["MediaSourceId"] = media_source_id
            params["MediaSourceId"] = media_source_id
        if subtitle_stream_index is not None:
            payload["SubtitleStreamIndex"] = subtitle_stream_index
            params["SubtitleStreamIndex"] = str(subtitle_stream_index)
            payload["AlwaysBurnInSubtitleWhenTranscoding"] = False
        try:
            with httpx.Client(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = client.post(
                    f"/Items/{encoded_id}/PlaybackInfo",
                    params=params,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise JellyfinError("No se pudo negociar la reproducción con Jellyfin.") from exc
        if not isinstance(data, dict):
            raise JellyfinError("Jellyfin devolvió datos de reproducción no válidos.")
        if media_source_id is None:
            selected = _source_with_burned_subtitles(data)
            if selected is not None:
                # Jellyfin solo respeta SubtitleStreamIndex=-1 cuando
                # MediaSourceId también está fijado (revalidado en host).
                return self.playback_info(
                    item_id,
                    start_time_ticks,
                    media_source_id=selected,
                    subtitle_stream_index=-1,
                )
        elif subtitle_stream_index == -1 and (
            _source_with_burned_subtitles(data) is not None
        ):
            raise JellyfinError("Jellyfin no pudo desactivar los subtítulos incrustados.")
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


def _public_playback_info(
    data: dict[str, Any], media_id: int, *,
    hls_bridge: HLSBridge0032 | None = None,
    profile: Perfil | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
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
            transcoding_uri = source.get("TranscodingUrl")
            has_hls = (
                not direct_play
                and source.get("SupportsTranscoding") is True
                and isinstance(transcoding_uri, str)
                and transcoding_uri.split("?", 1)[0].lower().endswith(".m3u8")
            )
            if direct_play:
                playback_url = (
                    f"/jellyfin/media/{media_id}/stream"
                    f"?media_source_id={quote(source_id, safe='')}"
                )
            elif has_hls and hls_bridge is not None:
                if request is None or profile is None:
                    raise JellyfinError("No hay sesión de perfil para HLS.")
                playback_url = hls_bridge.issue(
                    transcoding_uri, media_id, profile, request, get_settings(),
                )
            elif has_hls:
                playback_url = local_hls_url(transcoding_uri, media_id, get_settings())
            else:
                playback_url = None
            sources.append(
                {
                    "id": source_id,
                    "contenedor": source.get("Container"),
                    "bitrate": source.get("Bitrate"),
                    "reproduccion_directa": direct_play,
                    "requiere_transcodificacion": not direct_play,
                    "modo": "direct" if direct_play else "hls" if has_hls else None,
                    "url": playback_url,
                }
            )
    playable = any(source["url"] is not None for source in sources)
    return {
        "estado": "listo" if playable else "requiere_transcodificacion",
        "play_session_id": data.get("PlaySessionId"),
        "fuentes": sources,
    }


@router.post("/media/{media_id}/playback-info")
def get_media_playback_info(
    media_id: int,
    request: Request,
    _profile: Perfil = Depends(get_current_profile),
    session: Session = Depends(get_session),
    start_time_ticks: int = Query(default=0, ge=0),
    hls_bridge: HLSBridge0032 | None = Depends(get_hls_bridge_0032),
) -> dict[str, Any]:
    if hls_bridge is not None:
        try:
            hls_bridge.require_admitted(request)
        except HLSAdmissionClosed0032:
            raise HTTPException(status_code=423, detail="Reproducción no disponible.") from None
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
    try:
        return _public_playback_info(
            data, media_id, hls_bridge=hls_bridge, profile=_profile, request=request,
        )
    except HLSAdmissionClosed0032:
        raise HTTPException(status_code=423, detail="Reproducción no disponible.") from None
    except JellyfinError:
        raise HTTPException(status_code=503, detail="No se pudo proteger el enlace HLS.") from None


@router.get("/media/{media_id}/stream")
def stream_media(
    media_id: int,
    request: Request,
    _profile: Perfil = Depends(get_current_profile),
    session: Session = Depends(get_session),
    media_source_id: str | None = Query(default=None, max_length=128, pattern=r"^[A-Za-z0-9-]+$"),
    range_header: str | None = Header(default=None, alias="Range", max_length=128),
    if_range: str | None = Header(default=None, alias="If-Range", max_length=256),
    hls_bridge: HLSBridge0032 | None = Depends(get_hls_bridge_0032),
) -> StreamingResponse:
    if hls_bridge is not None:
        try:
            hls_bridge.require_admitted(request)
        except HLSAdmissionClosed0032:
            raise HTTPException(status_code=423, detail="Reproducción no disponible.") from None
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


@router.get("/media/{media_id}/hls")
def stream_hls(
    media_id: int,
    request: Request,
    token: str = Query(min_length=40, max_length=8192),
    _profile: Perfil = Depends(get_current_profile),
    session: Session = Depends(get_session),
    range_header: str | None = Header(default=None, alias="Range", max_length=128),
    hls_bridge: HLSBridge0032 | None = Depends(get_hls_bridge_0032),
) -> Response:
    """Proxy privado de playlists/fragmentos con token de ruta firmado.

    La clave API y las URLs internas de Jellyfin nunca llegan al cliente.
    """
    media = session.get(Medio, media_id)
    if media is None or not media.disponible_en_jellyfin:
        raise HTTPException(status_code=404, detail="Vídeo no disponible.")
    settings = get_settings()
    lease: object | None = None
    try:
        if hls_bridge is None:
            uri = verify_hls_token(token, media_id, settings)
        else:
            uri, lease = hls_bridge.reserve(
                token, media_id, _profile, request, settings,
            )
    except JellyfinError:
        raise HTTPException(status_code=403, detail="Enlace HLS no válido o caducado.") from None
    except HLSAdmissionClosed0032:
        raise HTTPException(status_code=423, detail="Reproducción no disponible.") from None

    try:
        upstream_client, upstream = open_hls_upstream(uri, settings, range_header)
    except BaseException as exc:
        if hls_bridge is not None and lease is not None:
            hls_bridge.finish(lease)
        if isinstance(exc, JellyfinError):
            raise HTTPException(status_code=503, detail=str(exc)) from None
        raise

    if uri.split("?", 1)[0].lower().endswith(".m3u8"):
        try:
            chunks = bytearray()
            for chunk in upstream.iter_bytes(chunk_size=64 * 1024):
                chunks.extend(chunk)
                if len(chunks) > MAX_PLAYLIST_BYTES:
                    raise JellyfinError("Lista HLS demasiado grande.")
            playlist = (
                hls_bridge.rewrite(bytes(chunks), uri, lease, settings)
                if hls_bridge is not None and lease is not None
                else rewrite_hls_playlist(bytes(chunks), uri, media_id, settings)
            )
        except (httpx.HTTPError, JellyfinError):
            raise HTTPException(
                status_code=503, detail="Jellyfin no pudo generar la lista HLS."
            ) from None
        finally:
            upstream.close()
            upstream_client.close()
            if hls_bridge is not None and lease is not None:
                hls_bridge.finish(lease)
        return Response(
            content=playlist,
            media_type="application/vnd.apple.mpegurl",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() in STREAM_RESPONSE_HEADERS
    }
    headers["Cache-Control"] = "private, no-store"
    headers["X-Content-Type-Options"] = "nosniff"

    def hls_chunks() -> Iterator[bytes]:
        try:
            yield from upstream.iter_bytes(chunk_size=64 * 1024)
        finally:
            upstream.close()
            upstream_client.close()
            if hls_bridge is not None and lease is not None:
                hls_bridge.finish(lease)

    return StreamingResponse(
        hls_chunks(),
        status_code=upstream.status_code,
        headers=headers,
        media_type=upstream.headers.get("content-type", "application/octet-stream"),
    )
