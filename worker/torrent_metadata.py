"""Verifica metadatos torrent Jackett antes de cualquier POST a qBittorrent.

No descarga medios; GET restringido a la instancia /dl/ de Jackett,
sin redirecciones, con límite de tamaño. No exponer enlaces ni hashes.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from urllib.parse import urlsplit

import httpx

MAX_TORRENT_BYTES = 4_000_000
MAX_DEPTH = 24
MAX_ITEMS = 10_000
MAX_TOTAL_BYTES = 100 * 1024**4


class TorrentMetadataError(Exception):
    """No se pueden garantizar los metadatos del candidato."""


@dataclass(frozen=True)
class TorrentMetadata:
    size_bytes: int
    info_hash: str


def es_url_jackett_dl(url: str, jackett_base_url: str) -> bool:
    """Solo enlace directo /dl/ desde el servicio Jackett configurado."""
    try:
        src, base = urlsplit(url), urlsplit(jackett_base_url)
        return (
            src.scheme in {"http", "https"}
            and src.scheme == base.scheme
            and src.hostname == base.hostname
            and src.port == base.port
            and src.username is None
            and src.password is None
            and src.path.startswith("/dl/")
        )
    except ValueError:
        return False


def _decode(data: bytes, position: int, depth: int, info_span: list) -> tuple[object, int]:
    if depth > MAX_DEPTH or position >= len(data):
        raise TorrentMetadataError("Torrent malformado.")

    kind = data[position:position + 1]
    if kind == b"i":
        end = data.find(b"e", position + 1)
        if end < 0:
            raise TorrentMetadataError("Entero torrent incompleto.")
        try:
            value = int(data[position + 1:end])
        except ValueError as exc:
            raise TorrentMetadataError("Entero torrent inválido.") from exc
        return value, end + 1

    if kind in (b"d", b"l"):
        is_dict = kind == b"d"
        elements: dict[bytes, object] | list[object] = {} if is_dict else []
        position += 1
        count = 0
        while position < len(data) and data[position:position + 1] != b"e":
            if count >= MAX_ITEMS:
                raise TorrentMetadataError("Demasiados archivos o campos.")
            if is_dict:
                key, position = _decode(data, position, depth + 1, info_span)
                if not isinstance(key, bytes) or key in elements:
                    raise TorrentMetadataError("Claves torrent inválidas.")
                begin = position
                val, position = _decode(data, position, depth + 1, info_span)
                elements[key] = val
                if depth == 0 and key == b"info":
                    if info_span:
                        raise TorrentMetadataError("Info duplicada.")
                    info_span.append((begin, position))
            else:
                val, position = _decode(data, position, depth + 1, info_span)
                elements.append(val)
            count += 1
        if position >= len(data):
            raise TorrentMetadataError("Fin torrent incompleto.")
        return elements, position + 1

    if kind in b"0123456789":
        colon = data.find(b":", position)
        if colon < 0 or colon - position > 10:
            raise TorrentMetadataError("Longitud torrent inválida.")
        try:
            length = int(data[position:colon])
        except ValueError as exc:
            raise TorrentMetadataError("Longitud torrent inválida.") from exc
        end = colon + 1 + length
        if length < 0 or length > MAX_TORRENT_BYTES or end > len(data):
            raise TorrentMetadataError("Cadena torrent fuera de límite.")
        return data[colon + 1:end], end

    raise TorrentMetadataError("Estructura torrent desconocida.")


def interpretar_torrent(raw: bytes) -> TorrentMetadata:
    if not raw or len(raw) > MAX_TORRENT_BYTES or not raw.startswith(b"d"):
        raise TorrentMetadataError("Respuesta no es un fichero torrent válido.")
    span: list[tuple[int, int]] = []
    parsed, end = _decode(raw, 0, 0, span)
    if (
        end != len(raw)
        or not isinstance(parsed, dict)
        or len(span) != 1
        or not isinstance(parsed.get(b"info"), dict)
    ):
        raise TorrentMetadataError("Metadatos torrent incompletos.")
    info = parsed[b"info"]
    files = info.get(b"files")
    if isinstance(files, list):
        if not files or len(files) > MAX_ITEMS:
            raise TorrentMetadataError("Listado torrent inválido.")
        sizes = [
            entry.get(b"length")
            for entry in files
            if isinstance(entry, dict)
        ]
        if len(sizes) != len(files):
            raise TorrentMetadataError("Entrada de fichero inválida.")
    else:
        sizes = [info.get(b"length")]

    if not all(isinstance(size, int) and 0 <= size <= MAX_TOTAL_BYTES for size in sizes):
        raise TorrentMetadataError("Tamaños de fichero inválidos.")
    total = sum(sizes)
    if total <= 0 or total > MAX_TOTAL_BYTES:
        raise TorrentMetadataError("Tamaño total torrent inválido.")
    begin, finish = span[0]
    return TorrentMetadata(
        size_bytes=total,
        info_hash=sha1(raw[begin:finish]).hexdigest(),
    )


def obtener_metadatos_jackett(
    url: str, jackett_base_url: str, *, transport: httpx.BaseTransport | None = None
) -> TorrentMetadata:
    if not es_url_jackett_dl(url, jackett_base_url):
        raise TorrentMetadataError("Origen de metadatos torrent no autorizado.")
    try:
        with httpx.Client(timeout=15, follow_redirects=False, trust_env=False, transport=transport) as client:
            with client.stream("GET", url, headers={"Accept": "application/x-bittorrent"}) as response:
                if response.status_code != 200:
                    raise TorrentMetadataError("Jackett no devolvió un .torrent válido.")
                data = bytearray()
                for chunk in response.iter_bytes(chunk_size=32768):
                    if len(data) + len(chunk) > MAX_TORRENT_BYTES:
                        raise TorrentMetadataError("Torrent demasiado grande para verificar.")
                    data.extend(chunk)
    except httpx.HTTPError as exc:
        raise TorrentMetadataError("No se pudo verificar Jackett; envío bloqueado.") from exc
    return interpretar_torrent(bytes(data))


def tamano_incoherente(anunciado: int | None, real: int) -> bool:
    if anunciado is None or anunciado <= 0:
        return False
    # Permitir pequeñas diferencias por redondeos de tamaño del indexador.
    return abs(anunciado - real) > max(20 * 1024**2, int(anunciado * 0.10))
