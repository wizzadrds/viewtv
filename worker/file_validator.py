"""Validación conservadora de archivos descargados."""

import math
from pathlib import Path, PureWindowsPath


class InvalidTorrentFiles(ValueError):
    """Los archivos no cumplen las condiciones de seguridad."""


def validate_torrent_files(
    torrent: dict,
    files: list[dict],
    media_root: Path,
    expected_save_path: str = r"C:\VIEWTV\media\descargas_temporales",
) -> list[Path]:
    """Valida archivos completos sin modificarlos."""

    if not isinstance(torrent, dict):
        raise InvalidTorrentFiles("Datos del torrent no válidos.")

    save_path = torrent.get("save_path")
    if not isinstance(save_path, str):
        raise InvalidTorrentFiles("Carpeta de descarga desconocida.")

    actual = PureWindowsPath(save_path)
    expected = PureWindowsPath(expected_save_path)

    if str(actual).casefold() != str(expected).casefold():
        raise InvalidTorrentFiles("Carpeta de descarga no autorizada.")

    progress = torrent.get("progress")
    if isinstance(progress, bool) or not isinstance(
        progress, (int, float)
    ) or not math.isfinite(progress) or progress != 1:
        raise InvalidTorrentFiles("El torrent no está completo.")

    if not isinstance(files, list) or not files:
        raise InvalidTorrentFiles("No hay archivos para validar.")

    root = media_root.resolve(strict=True)
    if not root.is_dir():
        raise InvalidTorrentFiles("Directorio multimedia no válido.")

    validated = []
    seen = set()
    total_validado = 0

    for item in files:
        if not isinstance(item, dict):
            raise InvalidTorrentFiles("Entrada de archivo no válida.")

        priority = item.get("priority")
        if priority is not None and (
            isinstance(priority, bool)
            or not isinstance(priority, int)
            or priority <= 0
        ):
            raise InvalidTorrentFiles("Archivo excluido o prioridad inválida.")

        name = item.get("name")
        size = item.get("size")
        file_progress = item.get("progress")

        if not isinstance(name, str) or not name or "\\x00" in name:
            raise InvalidTorrentFiles("Nombre de archivo no válido.")

        relative = PureWindowsPath(name)

        if (
            relative.is_absolute()
            or relative.drive
            or any(part in ("..", ".") for part in name.replace(
                "\\", "/"
            ).split("/"))
            or ":" in name
        ):
            raise InvalidTorrentFiles("Ruta de archivo no autorizada.")

        key = str(relative).casefold()
        if key in seen:
            raise InvalidTorrentFiles("Nombre de archivo duplicado.")
        seen.add(key)

        if isinstance(size, bool) or not isinstance(
            size, int
        ) or size < 0:
            raise InvalidTorrentFiles("Tamaño de archivo no válido.")

        if isinstance(file_progress, bool) or not isinstance(
            file_progress, (int, float)
        ) or not math.isfinite(file_progress) or file_progress != 1:
            raise InvalidTorrentFiles("Archivo incompleto.")

        target = root.joinpath(*relative.parts)

        componente = root
        for parte in relative.parts:
            componente = componente / parte
            if componente.is_symlink():
                raise InvalidTorrentFiles(
                    "No se permiten enlaces simbólicos."
                )

        try:
            resolved = target.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise InvalidTorrentFiles("Archivo fuera del directorio.")
            if not target.is_file() or target.is_symlink():
                raise InvalidTorrentFiles("No es un archivo regular.")
            if target.stat().st_size != size:
                raise InvalidTorrentFiles("Tamaño de archivo diferente.")
        except (OSError, RuntimeError) as exc:
            raise InvalidTorrentFiles(
                "No se puede verificar el archivo."
            ) from exc

        validated.append(resolved)
        total_validado += size

    total_esperado = torrent.get("total_size")
    if total_esperado is not None:
        if (
            isinstance(total_esperado, bool)
            or not isinstance(total_esperado, int)
            or total_esperado < -1
        ):
            raise InvalidTorrentFiles("Tamaño total no válido.")

        if total_esperado >= 0 and total_validado != total_esperado:
            raise InvalidTorrentFiles(
                "El tamaño total no coincide con los archivos."
            )

    return validated
