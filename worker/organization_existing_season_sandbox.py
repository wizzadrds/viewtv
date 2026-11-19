"""Añadir UN episodio a una temporada existente: SOLO SANDBOX bajo /tmp.

El fichero se publica mediante enlace duro sin reemplazar, con staging
independiente. No soporta subtítulos ni múltiples archivos en esta fase.
NO es un ejecutor real y NO se importa desde worker/main.py.
"""

import errno
import os
import re
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path

from worker.organization_copy_sandbox import (
    _DIR_FLAGS,
    _check_sandbox,
    _copy_one,
    _dir,
    _managed_fd,
)
from worker.organization_planner import (
    EPISODE_RE,
    VIDEO_EXTENSIONS,
    OrganizationPlan,
    UnsafeOrganizationPlan,
    _safe_title,
)

SEASON_RE = re.compile(r"Temporada [0-9]{2}\Z")


def _single_media_entry(plan: OrganizationPlan, root: Path) -> tuple:
    """Comprueba el plan sin fiarse de rutas preparadas por el llamador."""
    if (
        not isinstance(plan, OrganizationPlan)
        or not isinstance(plan.download_id, int)
        or isinstance(plan.download_id, bool)
        or plan.download_id <= 0
        or plan.library != "Series"
        or len(plan.entries) != 1
    ):
        raise UnsafeOrganizationPlan(
            "Solo se admiten episodios individuales de series existentes."
        )

    entry = plan.entries[0]
    dest = entry.destination
    source = entry.source
    series = root / "media" / "Series"
    downloads = root / "media" / "descargas_temporales"
    if not isinstance(dest, Path) or not isinstance(source, Path):
        raise UnsafeOrganizationPlan("Rutas de prueba inválidas.")
    if not dest.is_absolute() or not source.is_absolute():
        raise UnsafeOrganizationPlan("Se requieren rutas absolutas de sandbox.")
    if ".." in dest.parts or ".." in source.parts:
        raise UnsafeOrganizationPlan("No se permiten componentes superiores.")

    season = dest.parent.name
    show = dest.parent.parent.name
    if (
        dest.parent.parent.parent != series
        or SEASON_RE.fullmatch(season) is None
        or _safe_title(show) != show
        or dest.suffix.lower() not in VIDEO_EXTENSIONS
        or not dest.name.startswith(show + " - S")
        or EPISODE_RE.search(dest.stem) is None
        or dest.name.startswith(".")
    ):
        raise UnsafeOrganizationPlan("Destino de episodio no autorizado.")

    try:
        source_relative = source.relative_to(downloads)
    except ValueError:
        raise UnsafeOrganizationPlan("Origen fuera de descargas de prueba.") from None
    if not source_relative.parts or ".." in source_relative.parts:
        raise UnsafeOrganizationPlan("Ruta de origen no autorizada.")
    if isinstance(entry.size_bytes, bool) or not isinstance(entry.size_bytes, int):
        raise UnsafeOrganizationPlan("Tamaño de origen inválido.")
    return show, season, dest.name, source_relative.parts, entry.size_bytes


def publish_test_existing_episode(
    plan: OrganizationPlan,
    sandbox_root: Path,
    *,
    progress_callback: Callable[[], None] | None = None,
) -> Path:
    """Publica un solo vídeo en una temporada PREEXISTENTE, nunca sobrescribe."""
    root = _check_sandbox(sandbox_root)
    show, season, target, source_parts, size = _single_media_entry(plan, root)
    media = root / "media"
    if media.is_symlink() or not media.is_dir():
        raise UnsafeOrganizationPlan("Raíz de pruebas no segura.")
    stage_name = f".viewtv-test-episode-{plan.download_id}"

    with ExitStack() as stack:
        media_fd = stack.enter_context(_managed_fd(os.open(media, _DIR_FLAGS)))
        sources_fd = stack.enter_context(
            _managed_fd(_dir(media_fd, "descargas_temporales"))
        )
        series_fd = stack.enter_context(_managed_fd(_dir(media_fd, "Series")))
        if show not in os.listdir(series_fd):
            raise UnsafeOrganizationPlan("La serie debe existir previamente.")
        show_fd = stack.enter_context(_managed_fd(_dir(series_fd, show)))
        if season not in os.listdir(show_fd):
            raise UnsafeOrganizationPlan("La temporada debe existir previamente.")
        season_fd = stack.enter_context(_managed_fd(_dir(show_fd, season)))

        existing = {name.casefold() for name in os.listdir(season_fd)}
        if target.casefold() in existing:
            raise UnsafeOrganizationPlan("El episodio ya existe.")
        if stage_name.casefold() in existing:
            raise UnsafeOrganizationPlan(
                "La copia anterior está pendiente de revisión."
            )

        os.mkdir(stage_name, mode=0o700, dir_fd=season_fd)
        staging_fd = stack.enter_context(_managed_fd(_dir(season_fd, stage_name)))

        _copy_one(
            sources_fd, source_parts, staging_fd, target, size,
            progress_callback,
        )
        os.fsync(staging_fd)
        if progress_callback is not None:
            progress_callback()

        # os.link sobre mismo filesystem crea el nombre destino solo si
        # NO existe. No usar os.rename ni reemplazos automáticos en DrvFS.
        try:
            os.link(
                target, target,
                src_dir_fd=staging_fd,
                dst_dir_fd=season_fd,
                follow_symlinks=False,
            )
        except FileExistsError:
            raise UnsafeOrganizationPlan(
                "El episodio apareció durante la copia: revisión."
            ) from None
        except OSError as exc:
            if exc.errno in (errno.EEXIST, errno.ENOTEMPTY):
                raise UnsafeOrganizationPlan("El episodio ya existe.") from exc
            raise

        os.fsync(season_fd)
        # Se elimina exclusivamente el duplicado temporal NUEVO bajo
        # nuestro staging; el fichero publicado y el origen se conservan.
        os.unlink(target, dir_fd=staging_fd)
        os.rmdir(stage_name, dir_fd=season_fd)
        os.fsync(season_fd)

    return root / "media" / "Series" / show / season / target
