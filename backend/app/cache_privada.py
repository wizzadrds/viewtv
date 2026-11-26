"""Cuota real y evicción SOLO para temporales exclusivos de ViewTV.

Raíz esperada: volumen Docker dedicado /cache-gestionada. Nunca apunta a
/media, /cache heredada, qBittorrent, Jellyfin, SQLite ni la carpeta Windows.
La función de escritura es interna: ningún endpoint acepta bytes ni rutas.
"""
from __future__ import annotations

import fcntl
import os
import secrets
import stat
import time
from pathlib import Path

from app.almacenamiento_archivos import DIR_CACHE, FICHERO_MARCA, MARCA, PATRON_TEMPORAL

MARCADOR_BLOQUEO = ".viewtv-lock-v1"
MAX_ENTRADAS = 10_000
MAX_OBJETO = 16 * 1024 * 1024
CADUCIDAD_SEGUNDOS = 14 * 86400
FLAGS_DIRECTORIO = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FLAGS_LECTURA = os.O_RDONLY | os.O_NOFOLLOW


class CacheNoConfiable(RuntimeError):
    """La zona no acredita propiedad exclusiva; no tocar archivos."""


def _raiz(root: Path) -> int:
    try:
        fd = os.open(root, FLAGS_DIRECTORIO)
    except OSError as exc:
        raise CacheNoConfiable("Volumen de caché no disponible.") from exc
    info = os.fstat(fd)
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_mode & 0o022
    ):
        os.close(fd)
        raise CacheNoConfiable("El volumen de caché no es privado.")
    return fd


def _directorio(rootfd: int, *, crear: bool) -> int | None:
    """Serializa inicialización y lectura del marcador incluso entre procesos."""
    fcntl.flock(rootfd, fcntl.LOCK_EX)
    try:
        return _directorio_bajo_bloqueo(rootfd, crear=crear)
    finally:
        fcntl.flock(rootfd, fcntl.LOCK_UN)


def _directorio_bajo_bloqueo(rootfd: int, *, crear: bool) -> int | None:
    try:
        fd = os.open(DIR_CACHE, FLAGS_DIRECTORIO, dir_fd=rootfd)
    except FileNotFoundError:
        if not crear:
            return None
        try:
            os.mkdir(DIR_CACHE, mode=0o700, dir_fd=rootfd)
        except FileExistsError:
            # Entre la comprobación y el mkdir hubo una carrera;
            # abrir con O_NOFOLLOW y comprobar de nuevo.
            pass
        fd = os.open(DIR_CACHE, FLAGS_DIRECTORIO, dir_fd=rootfd)
        flag = None
        try:
            flag = os.open(
                FICHERO_MARCA,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=fd,
            )
            os.write(flag, MARCA)
            os.fsync(flag)
        except FileExistsError:
            pass
        finally:
            if flag is not None:
                os.close(flag)
    info = os.fstat(fd)
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_mode & 0o077
    ):
        os.close(fd)
        raise CacheNoConfiable("El directorio no tiene permisos seguros.")
    try:
        marker = os.open(FICHERO_MARCA, FLAGS_LECTURA, dir_fd=fd)
        try:
            flag = os.fstat(marker)
            if (
                not stat.S_ISREG(flag.st_mode)
                or flag.st_uid != os.geteuid()
                or flag.st_nlink != 1
                or flag.st_mode & 0o077
                or os.read(marker, 64) != MARCA
            ):
                raise CacheNoConfiable("Marcador de caché no válido.")
        finally:
            os.close(marker)
    except (OSError, CacheNoConfiable) as exc:
        os.close(fd)
        raise CacheNoConfiable("La caché no acredita propiedad.") from exc
    return fd


def _bloquear(fd: int) -> int:
    lock = os.open(
        MARCADOR_BLOQUEO,
        os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
        0o600,
        dir_fd=fd,
    )
    info = os.fstat(lock)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_uid != os.geteuid()
        or info.st_mode & 0o077
    ):
        os.close(lock)
        raise CacheNoConfiable("Bloqueo de caché no confiable.")
    fcntl.flock(lock, fcntl.LOCK_EX)
    return lock


def _entradas(fd: int) -> list[tuple[str, os.stat_result]]:
    names = os.listdir(fd)
    if len(names) > MAX_ENTRADAS:
        raise CacheNoConfiable("Demasiadas entradas para revisar con seguridad.")
    result = []
    parent = os.fstat(fd)
    for name in names:
        if name in {FICHERO_MARCA, MARCADOR_BLOQUEO}:
            continue
        if PATRON_TEMPORAL.fullmatch(name) is None:
            raise CacheNoConfiable("Existe un archivo ajeno en la caché privada.")
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        except OSError as exc:
            raise CacheNoConfiable("No se puede comprobar un temporal.") from exc
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_dev != parent.st_dev
            or info.st_nlink != 1
            or info.st_mode & 0o077
        ):
            raise CacheNoConfiable("Temporal con identidad insegura.")
        result.append((name, info))
    return result


def _borrar(fd: int, name: str, expected: os.stat_result) -> int:
    # Descriptor primero, revalidar inodo y número de enlaces. El árbol
    # privado 0700 y el flock cierran la carrera entre escritores de ViewTV.
    filefd = os.open(name, FLAGS_LECTURA, dir_fd=fd)
    try:
        info = os.fstat(filefd)
        live = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if any(
            (i.st_dev, i.st_ino, i.st_size, i.st_nlink) !=
            (expected.st_dev, expected.st_ino, expected.st_size, expected.st_nlink)
            for i in (info, live)
        ) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise CacheNoConfiable("Cambió la identidad del archivo temporal.")
        os.unlink(name, dir_fd=fd)
        return info.st_size
    finally:
        os.close(filefd)


def estado_cache(root: Path, quota_bytes: int) -> dict:
    if not isinstance(quota_bytes, int) or quota_bytes <= 0:
        raise ValueError("Cuota de caché no válida.")
    try:
        rootfd = _raiz(root)
        try:
            fd = _directorio(rootfd, crear=False)
            if fd is None:
                return {
                    "estado": "vacia_sin_inicializar", "archivos": 0,
                    "bytes": 0, "cuota_bytes": quota_bytes,
                    "cuota_efectiva_para_escritores_propios": True,
                }
            try:
                lock = _bloquear(fd)
                try:
                    records = _entradas(fd)
                    return {
                        "estado": "disponible", "archivos": len(records),
                        "bytes": sum(info.st_size for _, info in records),
                        "cuota_bytes": quota_bytes,
                        "cuota_efectiva_para_escritores_propios": True,
                    }
                finally:
                    os.close(lock)
            finally:
                os.close(fd)
        finally:
            os.close(rootfd)
    except (CacheNoConfiable, OSError):
        return {
            "estado": "no_confiable", "archivos": None, "bytes": None,
            "cuota_bytes": quota_bytes,
            "cuota_efectiva_para_escritores_propios": False,
        }


def _recortar(
    fd: int, records: list[tuple[str, os.stat_result]],
    quota: int, reserve: int = 0,
) -> tuple[int, int]:
    now = time.time()
    size = sum(info.st_size for _, info in records)
    deleted = 0
    freed = 0
    for name, info in sorted(records, key=lambda item: (item[1].st_mtime_ns, item[0])):
        old = now - info.st_mtime > CADUCIDAD_SEGUNDOS
        if not old and size + reserve <= quota:
            continue
        removed = _borrar(fd, name, info)
        size -= removed
        freed += removed
        deleted += 1
    return deleted, freed


def guardar_temporal(root: Path, data: bytes, quota_bytes: int) -> str:
    """Escritor privado con límite efectivo: rechaza datos sobredimensionados.

    Los únicos archivos que crea se encuentran dentro de su volumen Docker
    propio. No hay API HTTP pública que invoque esta función.
    """
    if (
        not isinstance(data, bytes)
        or not isinstance(quota_bytes, int)
        or quota_bytes <= 0
        or len(data) > MAX_OBJETO
        or len(data) > quota_bytes
    ):
        raise ValueError("Archivo temporal o cuota no admitidos.")
    rootfd = _raiz(root)
    try:
        fd = _directorio(rootfd, crear=True)
        assert fd is not None
        try:
            lock = _bloquear(fd)
            try:
                records = _entradas(fd)
                _recortar(fd, records, quota_bytes, len(data))
                name = "viewtv-" + secrets.token_hex(16) + ".tmp"
                output = os.open(
                    name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600, dir_fd=fd,
                )
                try:
                    remaining = memoryview(data)
                    while remaining:
                        remaining = remaining[os.write(output, remaining):]
                    os.fsync(output)
                except BaseException:
                    os.unlink(name, dir_fd=fd)
                    raise
                finally:
                    os.close(output)
                return name
            finally:
                os.close(lock)
        finally:
            os.close(fd)
    finally:
        os.close(rootfd)


def limpiar_cache(root: Path, quota_bytes: int) -> dict:
    """Evicción explícita de todos los archivos propios, nunca otros datos."""
    if not isinstance(quota_bytes, int) or quota_bytes <= 0:
        raise ValueError("Cuota inválida.")
    rootfd = _raiz(root)
    try:
        fd = _directorio(rootfd, crear=False)
        if fd is None:
            return {"estado": "sin_cache_gestionada", "archivos": 0, "bytes": 0}
        try:
            lock = _bloquear(fd)
            try:
                deleted = 0
                freed = 0
                for name, info in _entradas(fd):
                    freed += _borrar(fd, name, info)
                    deleted += 1
                return {"estado": "limpiada", "archivos": deleted, "bytes": freed}
            finally:
                os.close(lock)
        finally:
            os.close(fd)
    finally:
        os.close(rootfd)
