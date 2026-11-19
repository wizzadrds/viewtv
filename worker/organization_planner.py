"""Planificación de biblioteca a partir de descargas verificadas (SOLO LECTURA).

Esta fase NO copia, mueve, borra ni crea archivos o directorios.
La ejecución futura debe volver a validar el estado y las rutas contra TOCTOU.
"""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.models import Descarga, Solicitud


class UnsafeOrganizationPlan(ValueError):
    """La organización exige revisión manual por riesgo o ambigüedad."""


VIDEO_EXTENSIONS = frozenset({".mkv", ".mp4", ".m4v", ".avi"})
SUBTITLE_EXTENSIONS = frozenset({".srt", ".ass", ".vtt"})
EPISODE_RE = re.compile(r"(?i)(?<![A-Za-z0-9])S(\d{1,2})E(\d{1,3})(?!\d)")
LANGUAGE_SUFFIX_RE = re.compile(r"(?:\.[A-Za-z0-9_-]{2,12}){1,3}")
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


@dataclass(frozen=True)
class OrganizationEntry:
    source: Path
    destination: Path
    size_bytes: int


@dataclass(frozen=True)
class OrganizationPlan:
    download_id: int
    library: str
    entries: tuple[OrganizationEntry, ...]


def _safe_title(title: str) -> str:
    if not isinstance(title, str):
        raise UnsafeOrganizationPlan("Título inválido.")
    normalized = unicodedata.normalize("NFKC", title).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if (
        not normalized
        or len(normalized) > 100
        or normalized in {".", ".."}
        or normalized.endswith((".", " "))
        or any(ord(char) < 32 or ord(char) == 127 for char in normalized)
        or any(char in '<>:"/\\|?*' for char in normalized)
        or normalized.split(".")[0].upper() in WINDOWS_RESERVED
    ):
        raise UnsafeOrganizationPlan("Título no apto para una ruta Windows.")
    return normalized


def _source_file(source: Path, root: Path) -> Path:
    if not source.is_absolute():
        raise UnsafeOrganizationPlan("El archivo origen no tiene ruta absoluta.")
    try:
        relative = source.relative_to(root)
    except ValueError:
        raise UnsafeOrganizationPlan("Archivo fuera de las descargas temporales.") from None

    if not relative.parts or ".." in relative.parts:
        raise UnsafeOrganizationPlan("Ruta de archivo no autorizada.")

    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise UnsafeOrganizationPlan("No se admiten enlaces simbólicos en origen.")

    try:
        resolved = source.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise UnsafeOrganizationPlan("El archivo sale del directorio de descargas.")
        if not source.is_file():
            raise UnsafeOrganizationPlan("El archivo origen no es regular.")
        if source.stat().st_size <= 0:
            raise UnsafeOrganizationPlan("El archivo origen está vacío.")
    except (OSError, RuntimeError) as exc:
        raise UnsafeOrganizationPlan("No se puede inspeccionar el archivo.") from exc

    return resolved


def plan_verified_media(
    download: Descarga,
    request: Solicitud,
    source_files: list[Path],
    download_root: Path,
    media_root: Path,
) -> OrganizationPlan:
    """Propone rutas de destino seguras sin modificar el sistema de archivos.

    source_files debe proceder del verificador qBittorrent justo antes de
    ejecutar; una futura operación de escritura debe verificar otra vez.
    """
    if (
        download.id is None
        or download.id <= 0
        or request.id is None
        or download.solicitud_id != request.id
        or download.estado != "completada"
        or download.progreso != 1
        or download.estado_verificacion != "verificada"
    ):
        raise UnsafeOrganizationPlan("Descarga no verificada o solicitud incongruente.")

    if request.tipo_medio not in {"pelicula", "serie"}:
        raise UnsafeOrganizationPlan("Tipo de medio no soportado.")

    if not isinstance(source_files, list) or not 1 <= len(source_files) <= 20:
        raise UnsafeOrganizationPlan("Cantidad de archivos no admitida.")

    if download_root.is_symlink() or media_root.is_symlink():
        raise UnsafeOrganizationPlan("Las raíces no pueden ser enlaces simbólicos.")
    try:
        root = download_root.resolve(strict=True)
        library_root = media_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise UnsafeOrganizationPlan("Raíces multimedia inaccesibles.") from exc
    if not root.is_dir() or not library_root.is_dir():
        raise UnsafeOrganizationPlan("Las raíces no son directorios.")

    library = "Peliculas" if request.tipo_medio == "pelicula" else "Series"
    category = library_root / library
    if category.is_symlink() or category.exists() and not category.is_dir():
        raise UnsafeOrganizationPlan("La biblioteca no es un directorio seguro.")
    if category.resolve(strict=False).is_relative_to(root):
        raise UnsafeOrganizationPlan("El destino apunta a descargas temporales.")

    verified: list[Path] = []
    seen_sources: set[str] = set()
    for file_path in source_files:
        if not isinstance(file_path, Path):
            raise UnsafeOrganizationPlan("Entrada de archivo inválida.")
        actual = _source_file(file_path, root)
        key = str(actual).casefold()
        if key in seen_sources:
            raise UnsafeOrganizationPlan("Archivo origen duplicado.")
        seen_sources.add(key)
        verified.append(actual)

    videos = [path for path in verified if path.suffix.lower() in VIDEO_EXTENSIONS]
    if len(videos) != 1:
        raise UnsafeOrganizationPlan("Se requiere exactamente un archivo de vídeo.")

    video = videos[0]
    subtitle_files = [path for path in verified if path != video]
    if any(path.suffix.lower() not in SUBTITLE_EXTENSIONS for path in subtitle_files):
        raise UnsafeOrganizationPlan("La descarga contiene archivos no reconocidos.")

    title = _safe_title(request.titulo)
    if request.tipo_medio == "pelicula":
        if request.anio is not None and not 1870 <= request.anio <= 2200:
            raise UnsafeOrganizationPlan("Año de película inválido.")
        media_name = f"{title} ({request.anio})" if request.anio else title
        destination_folder = category / media_name
        base_name = media_name
    else:
        episode = EPISODE_RE.search(video.stem)
        if episode is None:
            raise UnsafeOrganizationPlan("No se ha identificado el episodio de la serie.")
        season, number = map(int, episode.groups())
        if number == 0:
            raise UnsafeOrganizationPlan("Episodio no válido.")
        show = _safe_title(EPISODE_RE.sub("", title).strip(" .-_"))
        destination_folder = category / show / f"Temporada {season:02d}"
        base_name = f"{show} - S{season:02d}E{number:02d}"

    # En películas no incorporamos archivos a títulos existentes sin revisión.
    # Para series sí se permiten temporadas existentes, pero no sobreescribir
    # episodios ni atravesar enlaces simbólicos.
    if request.tipo_medio == "pelicula":
        if destination_folder.exists() or destination_folder.is_symlink():
            raise UnsafeOrganizationPlan("La carpeta de película ya existe.")
        if category.is_dir() and any(
            child.name.casefold() == destination_folder.name.casefold()
            for child in category.iterdir()
        ):
            raise UnsafeOrganizationPlan("Existe una película con nombre equivalente.")
    else:
        show_folder = category / show
        for folder in (show_folder, destination_folder):
            if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
                raise UnsafeOrganizationPlan("La carpeta de serie no es segura.")
            if folder.parent.is_dir() and any(
                child.name.casefold() == folder.name.casefold()
                and child.name != folder.name
                for child in folder.parent.iterdir()
            ):
                raise UnsafeOrganizationPlan("Existe una carpeta equivalente con otro nombre.")

    entries = [
        OrganizationEntry(
            source=video,
            destination=destination_folder / (base_name + video.suffix.lower()),
            size_bytes=video.stat().st_size,
        )
    ]

    for subtitle in subtitle_files:
        if subtitle.parent != video.parent:
            raise UnsafeOrganizationPlan("Subtítulo fuera de la carpeta del vídeo.")
        stem = subtitle.stem
        if not stem.casefold().startswith(video.stem.casefold()):
            raise UnsafeOrganizationPlan("Subtítulo sin correspondencia con el vídeo.")
        language = stem[len(video.stem):]
        if language and LANGUAGE_SUFFIX_RE.fullmatch(language) is None:
            raise UnsafeOrganizationPlan("Etiqueta de subtítulo ambigua.")
        entries.append(
            OrganizationEntry(
                source=subtitle,
                destination=destination_folder / (
                    base_name + language + subtitle.suffix.lower()
                ),
                size_bytes=subtitle.stat().st_size,
            )
        )

    dest_keys = [str(entry.destination).casefold() for entry in entries]
    if len(set(dest_keys)) != len(dest_keys):
        raise UnsafeOrganizationPlan("Destinos duplicados o equivalentes.")

    for entry in entries:
        destination = entry.destination
        if destination.exists() or destination.is_symlink():
            raise UnsafeOrganizationPlan("El archivo de destino ya existe.")
        if destination.parent.is_dir() and any(
            child.name.casefold() == destination.name.casefold()
            for child in destination.parent.iterdir()
        ):
            raise UnsafeOrganizationPlan("Existe un archivo con nombre equivalente.")

    return OrganizationPlan(
        download_id=download.id,
        library=library,
        entries=tuple(entries),
    )
