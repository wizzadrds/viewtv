"""Clasificación estrictamente de lectura de archivos originales qBittorrent.

NUNCA calcula un plan de borrado. Los archivos fuera del manifiesto pueden
pertenecer al usuario y se protegen incluso si su extensión es conocida.
No imprime nombres, rutas, hashes ni identificadores de torrents.
"""
from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from worker.retirement_preflight_0018 import _valid_relative

VIDEO = frozenset({".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv"})
SUBTITLES = frozenset({".srt", ".ass", ".vtt", ".ssa", ".sub", ".idx"})
METADATA = frozenset({".nfo", ".txt", ".url", ".jpg", ".jpeg", ".png", ".webp"})
MAX_FILES = 100


def _group(name: str) -> str:
    ext = PurePosixPath(name.replace("\\", "/")).suffix.casefold()
    if ext in VIDEO:
        return "video"
    if ext in SUBTITLES:
        return "subtitulo"
    if ext in METADATA:
        return "metadato"
    return "otro"


def analizar_inventario(snapshot: dict, journals: dict) -> dict:
    """Devuelve solo agregados, sin capacidad para autorizar retiradas."""
    if not isinstance(snapshot, dict) or not isinstance(journals, dict):
        raise ValueError("Snapshot no verificable.")  # noqa: TRY004 -- contrato ValueError público
    downloads = snapshot.get("descargas")
    qbit = snapshot.get("qbittorrent")
    if not isinstance(downloads, list) or not isinstance(qbit, dict):
        raise ValueError("Datos incompletos.")  # noqa: TRY004 -- contrato ValueError público
    stats = Counter()
    stats["descargas_analizadas"] = 0
    stats["con_archivos_no_publicados"] = 0
    stats["archivos_qbit"] = 0
    stats["archivos_publicados_correlacionados"] = 0
    stats["archivos_no_publicados_protegidos"] = 0
    stats["no_normalizables"] = 0
    stats["tamanos_incompatibles"] = 0
    stats["qbit_no_disponible"] = 0
    stats["suma_bytes_logicos_no_publicados"] = 0
    for download in downloads:
        if not isinstance(download, dict):
            raise ValueError("Registro de descarga inválido.")  # noqa: TRY004 -- contrato ValueError público
        download_id = download.get("id")
        if type(download_id) is not int or download_id <= 0:
            raise ValueError("ID no válido.")
        journal = journals.get(download_id)
        if journal is None:
            continue
        record = journal[0]
        files = (record.get("intent") or {}).get("files")
        if not isinstance(files, list) or not 1 <= len(files) <= 20:
            raise ValueError("Manifiesto no verificable.")
        expected = {}
        for f in files:
            if not isinstance(f, dict):
                raise ValueError("Archivo de manifiesto no verificable.")  # noqa: TRY004 -- contrato ValueError público
            name, size = f.get("source_relative"), f.get("size_bytes")
            if _valid_relative(name) is None or type(size) is not int or size <= 0:
                raise ValueError("Ruta o tamaño de manifiesto no verificable.")
            key = name.casefold()
            if key in expected:
                raise ValueError("Manifiesto repetido.")
            expected[key] = size
        actual_info = qbit.get(str(download_id), {})
        if not isinstance(actual_info, dict) or actual_info.get("estado_consulta") != "ok":
            stats["qbit_no_disponible"] += 1
            continue
        rows = actual_info.get("files")
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_FILES:
            stats["qbit_no_disponible"] += 1
            continue
        stats["descargas_analizadas"] += 1
        extras = 0
        observed: set[str] = set()
        for f in rows:
            if not isinstance(f, dict):
                raise ValueError("Archivo qBit no verificable.")  # noqa: TRY004 -- contrato ValueError público
            name, size = f.get("name"), f.get("size")
            if not isinstance(name, str):
                raise ValueError("Nombre qBit no verificable.")  # noqa: TRY004 -- contrato ValueError público
            normalized = name.replace("\\", "/")
            key = normalized.casefold()
            stats["archivos_qbit"] += 1
            if _valid_relative(normalized) is None:
                stats["no_normalizables"] += 1
            if key in observed:
                raise ValueError("Archivos duplicados qBit.")
            observed.add(key)
            if key in expected and expected[key] == size:
                stats["archivos_publicados_correlacionados"] += 1
                continue
            if key in expected:
                stats["tamanos_incompatibles"] += 1
            extras += 1
            stats["archivos_no_publicados_protegidos"] += 1
            stats["extra_tipo_" + _group(normalized)] += 1
            if type(size) is int and size > 0:
                stats["suma_bytes_logicos_no_publicados"] += size
        if extras:
            stats["con_archivos_no_publicados"] += 1
    return dict(stats)
