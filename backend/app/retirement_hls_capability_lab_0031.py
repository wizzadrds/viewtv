"""0031: capacidades HLS v2 vinculadas a JWT, perfil, sesión y generación.

Contrato criptográfico de LABORATORIO. NO importarlo en app.main hasta
disponer de la autoridad de drenaje durable y del aislamiento externo.
La validación criptográfica NO sustituye la reserva atómica 0031.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from urllib.parse import unquote, urljoin

import jwt

from app.config import Settings
from app.jellyfin import JellyfinError
from app.jellyfin_hls import (
    HLS_TTL_SECONDS,
    MAX_PLAYLIST_BYTES,
    MAX_TOKEN_LENGTH,
    URI_ATTRIBUTE_RE,
    _safe_upstream_url,
)

SESSION_RE = re.compile(r"[a-f0-9]{48}\Z")
JTI_RE = re.compile(r"[a-f0-9]{32}\Z")
ROOT_RE = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
FIELDS = frozenset({"v", "m", "p", "q", "e", "pid", "sid", "g", "root", "c"})


def _fail() -> JellyfinError:
    return JellyfinError("Capacidad de reproducción inválida o revocada.")


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(encoded: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
        raise ValueError("base64")
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (binascii.Error, ValueError):
        raise ValueError("base64") from None
    if _b64encode(raw) != encoded:
        raise ValueError("noncanonical")
    return raw


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    data: dict[str, object] = {}
    for key, value in items:
        if key in data:
            raise ValueError("duplicate")
        data[key] = value
    return data


def _key(settings: Settings) -> bytes:
    if len(settings.jwt_secret) < 32:
        raise _fail()
    return hmac.new(
        settings.jwt_secret.encode("utf-8"), b"VIEWTV-HLS-V2-0031", hashlib.sha256,
    ).digest()


def cookie_fingerprint_0031(cookie: str, profile_id: int, settings: Settings) -> str:
    """Exige JWT auténtico con jti único; el cookie nunca se firma en claro."""
    if (
        type(profile_id) is not int or not 0 < profile_id <= 2_147_483_647
        or not isinstance(cookie, str) or not cookie.isascii()
        or not 20 <= len(cookie) <= 4096
    ):
        raise _fail()
    try:
        data = jwt.decode(
            cookie, settings.jwt_secret, algorithms=["HS256"],
            options={"require": ["sub", "exp", "iat", "jti"]},
        )
        if (
            data.get("sub") != str(profile_id)
            or not isinstance(data.get("jti"), str)
            or JTI_RE.fullmatch(data["jti"]) is None
        ):
            raise ValueError("session")
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise _fail() from None
    return hmac.new(_key(settings), cookie.encode("ascii"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class HLSContext0031:
    media_id: int
    profile_id: int
    session_id: str
    generation: int
    video_root: str
    cookie: str


@dataclass(frozen=True)
class VerifiedHLS0031:
    uri: str
    session_id: str
    generation: int
    video_root: str
    cookie_fingerprint: str


def _validate_context(context: HLSContext0031) -> None:
    if (
        type(context.media_id) is not int or not 0 < context.media_id <= 2_147_483_647
        or type(context.profile_id) is not int
        or not 0 < context.profile_id <= 2_147_483_647
        or type(context.generation) is not int
        or not 0 < context.generation <= 2_147_483_647
        or not isinstance(context.session_id, str)
        or SESSION_RE.fullmatch(context.session_id) is None
        or not isinstance(context.video_root, str)
        or ROOT_RE.fullmatch(context.video_root) is None
    ):
        raise _fail()


def _canonical(uri: str, video_root: str, settings: Settings) -> tuple[str, str]:
    path, query = _safe_upstream_url(uri, settings.jellyfin_base_url)
    # Una playlist contaminada no puede conducir a otro vídeo de Jellyfin.
    if (
        path != unquote(path)
        or path.split("/")[2] != video_root
        or not path.startswith("/videos/" + video_root + "/")
    ):
        raise _fail()
    return path, query


def sign_hls_v2_0031(
    uri: str, context: HLSContext0031, settings: Settings,
    *, expires_at: int | None = None,
) -> str:
    """Emisión exclusiva por backend tras crear sesión durable de laboratorio."""
    _validate_context(context)
    binding = cookie_fingerprint_0031(context.cookie, context.profile_id, settings)
    path, query = _canonical(uri, context.video_root, settings)
    now = int(time.time())
    expiry = now + HLS_TTL_SECONDS if expires_at is None else expires_at
    if type(expiry) is not int or not now < expiry <= now + HLS_TTL_SECONDS:
        raise _fail()
    body = {
        "v": 2, "m": context.media_id, "pid": context.profile_id,
        "sid": context.session_id, "g": context.generation,
        "root": context.video_root, "p": path, "q": query,
        "e": expiry, "c": binding,
    }
    encoded = _b64encode(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    sig = _b64encode(hmac.new(_key(settings), encoded.encode("ascii"), hashlib.sha256).digest())
    token = encoded + "." + sig
    if len(token) > MAX_TOKEN_LENGTH:
        raise _fail()
    return token


def verify_hls_v2_0031(
    token: str, media_id: int, profile_id: int, cookie: str, settings: Settings,
) -> VerifiedHLS0031:
    """Verifica identidad criptográfica; el llamante DEBE reservar en SQLite.

    Se invoca solo DESPUÉS de get_current_profile y ANTES de Jellyfin.
    Un token firmado no demuestra que la película siga admitiendo sesiones.
    """
    if not isinstance(token, str) or not 80 <= len(token) <= MAX_TOKEN_LENGTH:
        raise _fail()
    try:
        binding = cookie_fingerprint_0031(cookie, profile_id, settings)
        encoded, signature = token.split(".")
        expected = _b64encode(
            hmac.new(_key(settings), encoded.encode("ascii"), hashlib.sha256).digest(),
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        body = json.loads(_b64decode(encoded), object_pairs_hook=_pairs)
        if not isinstance(body, dict) or body.keys() != FIELDS:
            raise ValueError("fields")
        if (
            type(body["v"]) is not int or body["v"] != 2
            or type(body["m"]) is not int or body["m"] != media_id
            or type(body["pid"]) is not int or body["pid"] != profile_id
            or type(body["g"]) is not int or not 0 < body["g"] <= 2_147_483_647
            or type(body["e"]) is not int
        ):
            raise ValueError("identity")
        now = int(time.time())
        if not now < body["e"] <= now + HLS_TTL_SECONDS:
            raise ValueError("expiration")
        if (
            not isinstance(body["sid"], str)
            or SESSION_RE.fullmatch(body["sid"]) is None
            or not isinstance(body["root"], str)
            or ROOT_RE.fullmatch(body["root"]) is None
            or not isinstance(body["c"], str)
            or not hmac.compare_digest(body["c"], binding)
            or not isinstance(body["p"], str)
            or not isinstance(body["q"], str)
        ):
            raise ValueError("binding")
        raw = body["p"] + ("?" + body["q"] if body["q"] else "")
        path, query = _canonical(raw, body["root"], settings)
        if path != body["p"] or query != body["q"]:
            raise ValueError("canonical")
        return VerifiedHLS0031(
            raw, body["sid"], body["g"], body["root"], binding,
        )
    except (ValueError, KeyError, TypeError, OverflowError, UnicodeError, IndexError):
        raise _fail() from None


def local_hls_v2_0031(uri: str, context: HLSContext0031, settings: Settings) -> str:
    token = sign_hls_v2_0031(uri, context, settings)
    return f"/jellyfin/media/{context.media_id}/hls?token={token}"


def rewrite_hls_v2_0031(
    contents: bytes, upstream_uri: str, context: HLSContext0031, settings: Settings,
) -> bytes:
    """Reescribe variantes, segmentos, claves y URI con la MISMA sesión."""
    if not isinstance(contents, bytes) or len(contents) > MAX_PLAYLIST_BYTES:
        raise _fail()
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _fail() from None
    if not text.lstrip().startswith("#EXTM3U"):
        raise _fail()
    _canonical(upstream_uri, context.video_root, settings)
    origin = urljoin(settings.jellyfin_base_url.rstrip("/") + "/", upstream_uri)

    def rewrite(value: str) -> str:
        resolved = urljoin(origin, value)
        return "/api/viewtv" + local_hls_v2_0031(resolved, context, settings)

    result: list[str] = []
    for original in text.splitlines():
        line = original.strip()
        if line.startswith("#"):
            result.append(URI_ATTRIBUTE_RE.sub(
                lambda m: 'URI="' + rewrite(m.group(1)) + '"', line,
            ))
        elif line:
            result.append(rewrite(line))
    return ("\n".join(result) + "\n").encode("utf-8")
