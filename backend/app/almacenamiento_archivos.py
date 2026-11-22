"""Diagnóstico de ocupación y limpieza SOLO de temporales propios de ViewTV.

Nunca accede a .env, metadatos SQLite, torrents, fuente qBit ni medios de vídeo
con permiso de escritura. No confundir tamaño lógico con espacio recuperable
por enlaces duros NTFS.
"""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path

MARCA = b"viewtv-temporales-v1\n"
DIR_CACHE = "viewtv-temporales"
FICHERO_MARCA = ".viewtv-cache-v1"
PATRON_TEMPORAL = re.compile(r"\Aviewtv-[a-f0-9]{16,32}\.tmp\Z")
MAX_ENTRADAS = 100_000
MAX_DEPTH = 12


def volumen(path: Path) -> dict[str, int] | None:
    try:
        info = os.statvfs(path)
    except OSError:
        return None
    total = info.f_blocks * info.f_frsize
    available = info.f_bavail * info.f_frsize
    return {
        "total_bytes": total,
        "libre_bytes": available,
        "ocupado_en_volumen_bytes": max(0, total - info.f_bfree * info.f_frsize),
    }


def tamanio_logico(path: Path) -> dict[str, int | bool]:
    """Cuenta archivos regulares sin seguir symlinks ni atravesar montajes.

    Límite de recorrido y errores expresos para no inventar cifras exactas.
    """
    result: dict[str, int | bool] = {
        "bytes": 0, "archivos": 0, "completo": True,
    }
    try:
        root = path.stat(follow_symlinks=False)
        if not stat.S_ISDIR(root.st_mode):
            return {"bytes": 0, "archivos": 0, "completo": False}
    except FileNotFoundError:
        return result
    except OSError:
        return {"bytes": 0, "archivos": 0, "completo": False}

    visited: set[tuple[int, int]] = set()
    stack = [(path, 0)]
    count = 0
    while stack:
        folder, depth = stack.pop()
        try:
            entries = os.scandir(folder)
            with entries:
                for entry in entries:
                    count += 1
                    if count > MAX_ENTRADAS:
                        result["completo"] = False
                        return result
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        result["completo"] = False
                        continue
                    if info.st_dev != root.st_dev:
                        result["completo"] = False
                        continue
                    if stat.S_ISLNK(info.st_mode):
                        result["completo"] = False
                    elif stat.S_ISDIR(info.st_mode):
                        if depth >= MAX_DEPTH:
                            result["completo"] = False
                        else:
                            stack.append((Path(entry.path), depth + 1))
                    elif stat.S_ISREG(info.st_mode):
                        identity = (info.st_dev, info.st_ino)
                        # Un hardlink cuenta una vez dentro de cada subárbol.
                        if identity not in visited:
                            visited.add(identity)
                            result["bytes"] += info.st_size
                            result["archivos"] += 1
        except OSError:
            result["completo"] = False
    return result


def _cache_own_dir(cache_root: Path) -> Path | None:
    """Sólo un subdirectorio propietario, privado y con marcador exacto."""
    folder = cache_root / DIR_CACHE
    try:
        fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
                return None
            flag = os.open(
                FICHERO_MARCA, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd,
            )
            try:
                data = os.read(flag, 256)
                info_flag = os.fstat(flag)
                if not stat.S_ISREG(info_flag.st_mode) or data != MARCA:
                    return None
            finally:
                os.close(flag)
        finally:
            os.close(fd)
    except OSError:
        return None
    return folder


def limpiar_temporales(cache_root: Path) -> dict[str, int | str]:
    """Elimina únicamente archivos descartables de formato propio.

    No toca directorios, archivos sin marca, symlinks, hardlinks ni otros
    programas. El directorio privado debe pertenecer al uid del proceso.
    """
    folder = _cache_own_dir(cache_root)
    if folder is None:
        return {"estado": "sin_cache_gestionada", "archivos": 0, "bytes": 0}
    fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    removed = 0
    count = 0
    try:
        if os.fstat(fd).st_uid != os.geteuid():
            return {"estado": "propietario_no_autorizado", "archivos": 0, "bytes": 0}
        for name in os.listdir(fd):
            if not PATRON_TEMPORAL.fullmatch(name):
                continue
            # fstat del descriptor O_NOFOLLOW, no admitir enlaces duros.
            try:
                item_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    info = os.fstat(item_fd)
                    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                            or info.st_uid != os.geteuid()):
                        continue
                    snapshot = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if (snapshot.st_dev, snapshot.st_ino) != (
                        info.st_dev, info.st_ino,
                    ):
                        continue
                    # No borrar la fuente (si cambió se conserva por prudencia).
                    os.unlink(name, dir_fd=fd)
                    count += 1
                    removed += info.st_size
                finally:
                    os.close(item_fd)
            except OSError:
                continue
    finally:
        os.close(fd)
    return {"estado": "limpiada", "archivos": count, "bytes": removed}
