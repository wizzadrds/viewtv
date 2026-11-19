"""Publicación atómica de planes SOLO EN UN SANDBOX TEMPORAL.

No admite /media ni las bibliotecas reales. No hay integración con el worker.
No borra originales ni limpia restos de operaciones interrumpidas.
"""

import ctypes
import errno
import hashlib
import os
import stat
import tempfile
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from pathlib import Path

from worker.organization_planner import OrganizationPlan, UnsafeOrganizationPlan

MARKER = "VIEWTV_ORGANIZATION_TEST_SANDBOX_V1\n"
MAX_TEST_FILE_BYTES = 32 * 1024 * 1024
_READ_SIZE = 1024 * 1024
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC


def _check_sandbox(path: Path) -> Path:
    """Exige un marcador explícito dentro de /tmp; no acepta producción."""
    if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts:
        raise UnsafeOrganizationPlan("Ruta de sandbox inválida.")
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if path.is_symlink() or not path.is_dir():
        raise UnsafeOrganizationPlan("No existe el directorio de pruebas.")
    root = path.resolve(strict=True)
    if root == temp or not root.is_relative_to(temp):
        raise UnsafeOrganizationPlan("Solo se admiten directorios bajo /tmp.")
    marker = root / ".viewtv-organization-test-only"
    if marker.is_symlink() or not marker.is_file() or marker.read_text() != MARKER:
        raise UnsafeOrganizationPlan("Falta marcador explícito de sandbox.")
    return root


@contextmanager
def _managed_fd(fd: int):
    try:
        yield fd
    finally:
        os.close(fd)


def _dir(fd: int, name: str) -> int:
    return os.open(name, _DIR_FLAGS, dir_fd=fd)


def _write_chunk(fd: int, data: memoryview) -> int:
    return os.write(fd, data)


def _source_fd(root_fd: int, parts: tuple[str, ...]) -> int:
    """Abrir componentes sin seguir enlaces simbólicos, incluso bajo carreras."""
    with ExitStack() as stack:
        parent = root_fd
        for part in parts[:-1]:
            parent = stack.enter_context(_managed_fd(_dir(parent, part)))
        return os.open(parts[-1], _FILE_FLAGS, dir_fd=parent)


def _copy_one(root_fd: int, parts: tuple[str, ...], target_fd: int,
              name: str, expected_size: int,
              progress_callback: Callable[[], None] | None = None) -> None:
    """Copia por descriptores sin symlinks, comprueba estabilidad y SHA-256."""
    if not 0 < expected_size <= MAX_TEST_FILE_BYTES:
        raise UnsafeOrganizationPlan("Tamaño no admitido en la prueba.")

    source_fd = _source_fd(root_fd, parts)
    try:
        initial = os.fstat(source_fd)
        if not stat.S_ISREG(initial.st_mode) or initial.st_size != expected_size:
            raise UnsafeOrganizationPlan("El origen ha cambiado.")
        target = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600, dir_fd=target_fd,
        )
        try:
            digest = hashlib.sha256()
            copied = 0
            while True:
                if progress_callback is not None:
                    progress_callback()
                chunk = os.read(source_fd, _READ_SIZE)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > expected_size:
                    raise UnsafeOrganizationPlan("El origen ha aumentado de tamaño.")
                digest.update(chunk)
                with memoryview(chunk) as pending:
                    while pending:
                        written = _write_chunk(target, pending)
                        if written <= 0:
                            raise OSError("Escritura incompleta.")
                        pending = pending[written:]
            os.fsync(target)
        finally:
            os.close(target)

        after = os.fstat(source_fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if copied != expected_size or any(
            getattr(initial, f) != getattr(after, f) for f in fields
        ):
            raise UnsafeOrganizationPlan("El origen cambió durante la copia.")

        # Segunda lectura del mismo descriptor para detectar alteración in situ.
        os.lseek(source_fd, 0, os.SEEK_SET)
        confirmed = hashlib.sha256()
        while block := os.read(source_fd, _READ_SIZE):
            confirmed.update(block)
        if digest.digest() != confirmed.digest():
            raise UnsafeOrganizationPlan("La integridad del origen ha variado.")

        # Comprobar los bytes realmente escritos, no solo el flujo leído.
        destination_fd = os.open(name, _FILE_FLAGS, dir_fd=target_fd)
        try:
            initial_target = os.fstat(destination_fd)
            if (
                not stat.S_ISREG(initial_target.st_mode)
                or initial_target.st_size != expected_size
            ):
                raise UnsafeOrganizationPlan("El archivo copiado no es válido.")
            published_digest = hashlib.sha256()
            while block := os.read(destination_fd, _READ_SIZE):
                published_digest.update(block)
            final_target = os.fstat(destination_fd)
            if (
                published_digest.digest() != digest.digest()
                or final_target.st_size != expected_size
                or initial_target.st_ino != final_target.st_ino
            ):
                raise UnsafeOrganizationPlan("El archivo copiado no coincide.")
        finally:
            os.close(destination_fd)

        last_source = os.fstat(source_fd)
        if any(
            getattr(initial, field) != getattr(last_source, field)
            for field in fields
        ):
            raise UnsafeOrganizationPlan("El origen cambió tras la comprobación.")
    finally:
        os.close(source_fd)


def _publish_noreplace(directory_fd: int, staged: str, final: str) -> None:
    """Publicar una carpeta en una sola operación, rechazando sobrescrituras."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise UnsafeOrganizationPlan("El sistema no permite publicación atómica segura.")
    rename.argtypes = [
        ctypes.c_int, ctypes.c_char_p,
        ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    if rename(directory_fd, os.fsencode(staged), directory_fd,
              os.fsencode(final), 1) != 0:  # RENAME_NOREPLACE
        code = ctypes.get_errno()
        if code in (errno.EEXIST, errno.ENOTEMPTY):
            raise UnsafeOrganizationPlan("Ya existe el destino: requiere revisión.")
        raise OSError(code, os.strerror(code))
    os.fsync(directory_fd)


def publish_test_plan(
    plan: OrganizationPlan,
    sandbox_root: Path,
    *,
    progress_callback: Callable[[], None] | None = None,
) -> Path:
    """Copia una película o serie nueva en un sandbox marcado de /tmp.

    El montaje real, cualquier carpeta existente y cualquier staging previo
    requieren revisión: NO se limpian de forma automática.
    """
    root = _check_sandbox(sandbox_root)
    if (
        not isinstance(plan, OrganizationPlan)
        or isinstance(plan.download_id, bool)
        or not isinstance(plan.download_id, int)
        or plan.download_id <= 0
        or plan.library not in ("Peliculas", "Series")
        or not 1 <= len(plan.entries) <= 20
    ):
        raise UnsafeOrganizationPlan("Plan inválido.")

    media = root / "media"
    downloads = media / "descargas_temporales"
    category = media / plan.library
    for directory in (media, downloads, category):
        if directory.is_symlink() or not directory.is_dir():
            raise UnsafeOrganizationPlan("Raíz multimedia de prueba no segura.")
    if downloads.resolve() == category.resolve():
        raise UnsafeOrganizationPlan("Origen y destino coinciden.")

    folders = {entry.destination.parent for entry in plan.entries}
    if len(folders) != 1:
        raise UnsafeOrganizationPlan("El plan contiene destinos incompatibles.")
    folder = next(iter(folders))
    if plan.library == "Peliculas":
        final = folder
        if final.parent != category:
            raise UnsafeOrganizationPlan("Destino fuera de películas.")
        subfolder = None
    else:
        final = folder.parent
        if final.parent != category or not folder.name.startswith("Temporada "):
            raise UnsafeOrganizationPlan("Destino fuera de series.")
        subfolder = folder.name

    final_name = final.name
    if (
        not final_name or final_name.startswith(".")
        or final_name in (".", "..") or "/" in final_name
        or "\\" in final_name
    ):
        raise UnsafeOrganizationPlan("Nombre de publicación inválido.")

    sources: list[tuple[tuple[str, ...], str, int]] = []
    seen: set[str] = set()
    for entry in plan.entries:
        try:
            relative = entry.source.relative_to(downloads)
        except ValueError:
            raise UnsafeOrganizationPlan("Origen fuera de las pruebas.") from None
        if not relative.parts or any(p in ("", ".", "..") for p in relative.parts):
            raise UnsafeOrganizationPlan("Origen de prueba inválido.")
        name = entry.destination.name
        if name in ("", ".", "..") or name.startswith(".") or any(
            c in name for c in '/\\'
        ):
            raise UnsafeOrganizationPlan("Nombre final inválido.")
        if name.casefold() in seen:
            raise UnsafeOrganizationPlan("Destino repetido.")
        seen.add(name.casefold())
        sources.append((relative.parts, name, entry.size_bytes))

    stage_name = f".viewtv-test-stage-{plan.download_id}"
    with ExitStack() as stack:
        media_fd = stack.enter_context(_managed_fd(os.open(media, _DIR_FLAGS)))
        root_fd = stack.enter_context(
            _managed_fd(_dir(media_fd, "descargas_temporales"))
        )
        category_fd = stack.enter_context(_managed_fd(_dir(media_fd, plan.library)))
        cfd = category_fd

        existing = {name.casefold() for name in os.listdir(cfd)}
        if final_name.casefold() in existing:
            raise UnsafeOrganizationPlan("Ya existe la biblioteca de destino.")
        if stage_name.casefold() in existing:
            raise UnsafeOrganizationPlan("Staging previo encontrado: requiere revisión.")

        os.mkdir(stage_name, 0o700, dir_fd=cfd)
        stage_fd = stack.enter_context(_managed_fd(_dir(cfd, stage_name)))
        directory_fd = stage_fd
        if subfolder is not None:
            os.mkdir(subfolder, 0o700, dir_fd=directory_fd)
            season_fd = stack.enter_context(_managed_fd(_dir(directory_fd, subfolder)))
            directory_fd = season_fd

        for parts, name, size in sources:
            _copy_one(root_fd, parts, directory_fd, name, size, progress_callback)
        os.fsync(directory_fd)
        os.fsync(stage_fd)
        if progress_callback is not None:
            progress_callback()
        _publish_noreplace(cfd, stage_name, final_name)

    return final
