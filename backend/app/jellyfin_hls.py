"""Proxy HLS privado de Jellyfin con enlaces temporales firmados.

Las listas y segmentos se solicitan solo al host Jellyfin configurado.
No se propagan claves, destinos remotos ni URL del upstream al navegador.
"""
import base64
import hashlib
import hmac
import json
import re
import time
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit

import httpx

from app.config import Settings
from app.jellyfin import JellyfinError

HLS_TTL_SECONDS = 4 * 3600
MAX_TOKEN_LENGTH = 8192
MAX_UPSTREAM_URI = 4096
MAX_PLAYLIST_BYTES = 2 * 1024 * 1024
URI_ATTRIBUTE_RE = re.compile(r'URI="([^"\r\n]+)"')
ALLOWED_SUFFIXES = frozenset({".m3u8", ".ts", ".m4s", ".mp4", ".aac", ".mp3", ".vtt", ".key"})
CREDENTIAL_QUERY_KEYS = frozenset({
    "apikey", "api_key", "access_token", "token", "x-emby-token", "authorization",
})


def _safe_upstream_url(uri: str, base_url: str) -> tuple[str, str]:
    """Aísla las rutas multimedia de Jellyfin y quita tokens de la URL."""
    if not isinstance(uri, str) or not uri or len(uri) > MAX_UPSTREAM_URI:
        raise JellyfinError("Ruta HLS de Jellyfin no válida.")
    if any(c in uri for c in ("\\", "\r", "\n", "\x00")):
        raise JellyfinError("Ruta HLS de Jellyfin no válida.")
    base = urlsplit(base_url)
    if base.scheme not in {"http", "https"} or not base.hostname:
        raise JellyfinError("Jellyfin no está configurado correctamente.")
    parsed = urlsplit(urljoin(base_url.rstrip("/") + "/", uri))
    if (
        parsed.scheme != base.scheme
        or parsed.hostname != base.hostname
        or parsed.port != base.port
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise JellyfinError("La lista HLS contiene una fuente externa.")
    decoded = unquote(parsed.path)
    segments = decoded.split("/")
    if (
        not decoded.lower().startswith("/videos/")
        or len(segments) < 4
        or any(part in {".", "..", ""} for part in segments[1:])
        or "\\" in decoded
        or "\x00" in decoded
        or decoded.rsplit(".", 1)[-1].lower() not in {
            s[1:] for s in ALLOWED_SUFFIXES
        }
    ):
        raise JellyfinError("La ruta HLS está fuera del vídeo autorizado.")
    try:
        fields = parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=100)
    except ValueError:
        raise JellyfinError("Parámetros HLS inválidos.") from None
    safe_query = urlencode([
        (key, value) for key, value in fields
        if key.casefold() not in CREDENTIAL_QUERY_KEYS
    ])
    return parsed.path, safe_query


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def sign_hls_url(
    uri: str,
    media_id: int,
    settings: Settings,
    *,
    expires_at: int | None = None,
) -> str:
    """Crea una capacidad temporal; nunca contiene la API key Jellyfin."""
    if not settings.jwt_secret or media_id <= 0:
        raise JellyfinError("No se puede proteger la reproducción HLS.")
    path, query = _safe_upstream_url(uri, settings.jellyfin_base_url)
    payload = {
        "m": media_id,
        "p": path,
        "q": query,
        "e": int(expires_at) if expires_at is not None else int(time.time()) + HLS_TTL_SECONDS,
    }
    encoded = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = _encode(
        hmac.new(settings.jwt_secret.encode(), encoded.encode(), hashlib.sha256).digest()
    )
    return encoded + "." + signature


def verify_hls_token(token: str, media_id: int, settings: Settings) -> str:
    """Comprueba caducidad, firma y ruta; rechaza tokens inventados."""
    if not settings.jwt_secret or not isinstance(token, str) or len(token) > MAX_TOKEN_LENGTH:
        raise JellyfinError("Enlace de reproducción no válido.")
    try:
        encoded, signature = token.split(".")
        expected = _encode(
            hmac.new(settings.jwt_secret.encode(), encoded.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        payload = json.loads(_decode(encoded))
        if (
            not isinstance(payload, dict)
            or type(payload.get("m")) is not int
            or payload["m"] != media_id
            or type(payload.get("e")) is not int
            or not int(time.time()) <= payload["e"] <= int(time.time()) + HLS_TTL_SECONDS
        ):
            raise ValueError("expired")
        raw = payload["p"] + ("?" + payload["q"] if payload["q"] else "")
        path, query = _safe_upstream_url(raw, settings.jellyfin_base_url)
        if path != payload["p"] or query != payload["q"]:
            raise ValueError("not canonical")
    except (ValueError, KeyError, TypeError, OverflowError):
        raise JellyfinError("Enlace de reproducción no válido.") from None
    return path + ("?" + query if query else "")


def local_hls_url(uri: str, media_id: int, settings: Settings) -> str:
    token = sign_hls_url(uri, media_id, settings)
    return f"/jellyfin/media/{media_id}/hls?token={token}"


def rewrite_hls_playlist(
    contents: bytes,
    upstream_uri: str,
    media_id: int,
    settings: Settings,
) -> bytes:
    """Convierte TODOS los enlaces de master, variantes y segmentos a VIEWTV."""
    if len(contents) > MAX_PLAYLIST_BYTES:
        raise JellyfinError("Lista HLS demasiado grande.")
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise JellyfinError("Jellyfin devolvió una lista HLS inválida.") from None
    if not text.lstrip().startswith("#EXTM3U"):
        raise JellyfinError("Jellyfin devolvió una lista HLS inválida.")
    origin = urljoin(settings.jellyfin_base_url.rstrip("/") + "/", upstream_uri)

    def rewrite(value: str) -> str:
        # Solo se aceptan rutas que sigan dentro del servicio Jellyfin
        # y del prefijo /videos/. Las claves upstream no se transportan.
        resolved = urljoin(origin, value)
        return "/api/viewtv" + local_hls_url(resolved, media_id, settings)

    lines: list[str] = []
    for original in text.splitlines():
        line = original.strip()
        if line.startswith("#"):
            line = URI_ATTRIBUTE_RE.sub(
                lambda m: 'URI="' + rewrite(m.group(1)) + '"', line
            )
            lines.append(line)
        elif line:
            lines.append(rewrite(line))
    return ("\n".join(lines) + "\n").encode("utf-8")


def open_hls_upstream(
    uri: str,
    settings: Settings,
    range_header: str | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> tuple[httpx.Client, httpx.Response]:
    path, query = _safe_upstream_url(uri, settings.jellyfin_base_url)
    if range_header and not re.fullmatch(r"bytes=\d*-\d*", range_header):
        raise JellyfinError("Rango HLS no válido.")
    client = httpx.Client(
        base_url=settings.jellyfin_base_url.rstrip("/"),
        headers={
            "Authorization": f'MediaBrowser Token="{settings.jellyfin_api_key}"',
            "Accept-Encoding": "identity",
        },
        timeout=httpx.Timeout(connect=settings.jellyfin_timeout_seconds,
                              read=45.0, write=settings.jellyfin_timeout_seconds,
                              pool=settings.jellyfin_timeout_seconds),
        follow_redirects=False,
        transport=transport,
    )
    try:
        path_and_query = path + ("?" + query if query else "")
        req = client.build_request(
            "GET", path_and_query,
            headers={"Range": range_header} if range_header else None,
        )
        response = client.send(req, stream=True)
    except httpx.HTTPError as exc:
        client.close()
        raise JellyfinError("No se pudo abrir la fuente HLS.") from exc
    if response.status_code not in {200, 206}:
        code = response.status_code
        response.close()
        client.close()
        if code == 404:
            raise JellyfinError("Jellyfin no encuentra los fragmentos del vídeo.")
        raise JellyfinError("Jellyfin no pudo preparar la reproducción HLS.")
    return client, response
