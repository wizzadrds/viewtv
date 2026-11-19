"""Organizador en modo planificación: nunca mover ni borrar archivos reales."""

from pathlib import Path

import pytest
from worker.organization_planner import (
    UnsafeOrganizationPlan,
    plan_verified_media,
)

from app.models import Descarga, Solicitud


def context(tmp_path, *, kind="pelicula", title="Película de prueba", year=2025):
    media = tmp_path / "media"
    media.mkdir()
    downloads = media / "descargas_temporales"
    downloads.mkdir()
    (media / "Peliculas").mkdir()
    (media / "Series").mkdir()

    request = Solicitud(
        id=10,
        perfil_id=1,
        titulo=title,
        tipo_medio=kind,
        anio=year,
        estado="completada",
    )
    download = Descarga(
        id=20,
        solicitud_id=10,
        titulo=title,
        estado="completada",
        progreso=1.0,
        estado_verificacion="verificada",
    )
    return media, downloads, request, download


def source(root: Path, name: str, data=b"demo") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_movie_plan_is_read_only(tmp_path):
    media, downloads, request, download = context(tmp_path)
    video = source(downloads, "torrents/pelicula.mkv")

    result = plan_verified_media(download, request, [video], downloads, media)

    assert result.download_id == 20
    assert result.library == "Peliculas"
    assert result.entries[0].source == video.resolve()
    assert result.entries[0].destination == (
        media / "Peliculas" / "Película de prueba (2025)"
        / "Película de prueba (2025).mkv"
    )
    assert result.entries[0].size_bytes == 4
    assert video.read_bytes() == b"demo"
    assert not result.entries[0].destination.parent.exists()


def test_single_episode_with_subtitles(tmp_path):
    media, downloads, request, download = context(
        tmp_path, kind="serie", title="Mi serie", year=None,
    )
    video = source(downloads, "Mi.Serie.S02E03.mkv")
    subtitle = source(downloads, "Mi.Serie.S02E03.es.srt", b"subtitulo")

    plan = plan_verified_media(
        download, request, [video, subtitle], downloads, media,
    )

    assert plan.library == "Series"
    folder = media / "Series" / "Mi serie" / "Temporada 02"
    assert plan.entries[0].destination == folder / "Mi serie - S02E03.mkv"
    assert plan.entries[1].destination == folder / "Mi serie - S02E03.es.srt"
    assert not folder.exists()


@pytest.mark.parametrize(
    "state,progress,verification",
    [
        ("enviada", 1, "verificada"),
        ("descargando", 0.3, "verificada"),
        ("completada", 1, "pendiente"),
        ("completada", 1, "fallida"),
    ],
)
def test_rejects_unverified_download(tmp_path, state, progress, verification):
    media, downloads, request, download = context(tmp_path)
    video = source(downloads, "movie.mp4")
    download.estado = state
    download.progreso = progress
    download.estado_verificacion = verification

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


@pytest.mark.parametrize(
    "title", ["../Escape", "CON", "Peli/otra", r"Peli\otra", "Film:2025", "  "],
)
def test_rejects_unsafe_title(tmp_path, title):
    media, downloads, request, download = context(tmp_path, title=title)
    video = source(downloads, "movie.mp4")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


def test_rejects_wrong_request(tmp_path):
    media, downloads, request, download = context(tmp_path)
    video = source(downloads, "movie.mp4")
    request.id = 999

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


def test_rejects_unknown_media_kind(tmp_path):
    media, downloads, request, download = context(tmp_path, kind="temporada")
    video = source(downloads, "movie.mp4")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


def test_rejects_outside_source(tmp_path):
    media, downloads, request, download = context(tmp_path)
    video = source(tmp_path, "outside.mkv")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


def test_rejects_symlink_source(tmp_path):
    media, downloads, request, download = context(tmp_path)
    outside = source(tmp_path, "external.mkv")
    (downloads / "link.mkv").symlink_to(outside)

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(
            download, request, [downloads / "link.mkv"], downloads, media,
        )


def test_rejects_symlink_directory_in_source(tmp_path):
    media, downloads, request, download = context(tmp_path)
    outside = tmp_path / "elsewhere"
    source(outside, "video.mkv")
    (downloads / "linkdir").symlink_to(outside, target_is_directory=True)

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(
            download,
            request,
            [downloads / "linkdir" / "video.mkv"],
            downloads,
            media,
        )


def test_rejects_destination_folder_that_exists(tmp_path):
    media, downloads, request, download = context(tmp_path)
    video = source(downloads, "movie.mp4")
    (media / "Peliculas" / "Película de prueba (2025)").mkdir()

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


def test_rejects_existing_destination_symlink(tmp_path):
    media, downloads, request, download = context(tmp_path)
    video = source(downloads, "movie.mp4")
    other = tmp_path / "other"
    other.mkdir()
    (media / "Peliculas" / "Película de prueba (2025)").symlink_to(
        other, target_is_directory=True,
    )

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


def test_rejects_multiple_videos(tmp_path):
    media, downloads, request, download = context(tmp_path)
    one = source(downloads, "one.mp4")
    two = source(downloads, "two.mkv")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [one, two], downloads, media)


def test_rejects_non_media_file(tmp_path):
    media, downloads, request, download = context(tmp_path)
    one = source(downloads, "one.mp4")
    extra = source(downloads, "install.exe")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [one, extra], downloads, media)


def test_rejects_orphan_subtitle(tmp_path):
    media, downloads, request, download = context(tmp_path)
    one = source(downloads, "one.mp4")
    extra = source(downloads, "other.es.srt")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [one, extra], downloads, media)


def test_rejects_subtitle_in_different_subdirectory(tmp_path):
    media, downloads, request, download = context(tmp_path)
    one = source(downloads, "a/video.mp4")
    extra = source(downloads, "b/video.es.srt")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [one, extra], downloads, media)


def test_rejects_series_without_episode_pattern(tmp_path):
    media, downloads, request, download = context(
        tmp_path, kind="serie", title="Mi Serie", year=None,
    )
    video = source(downloads, "mi_serie.mkv")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


def test_rejects_series_zero_episode(tmp_path):
    media, downloads, request, download = context(
        tmp_path, kind="serie", title="Mi Serie", year=None,
    )
    video = source(downloads, "Mi.Serie.S01E00.mkv")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


def test_rejects_duplicate_source(tmp_path):
    media, downloads, request, download = context(tmp_path)
    video = source(downloads, "one.mp4")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video, video], downloads, media)


def test_rejects_missing_source(tmp_path):
    media, downloads, request, download = context(tmp_path)
    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(
            download, request, [downloads / "not-here.mp4"], downloads, media,
        )


def test_series_can_use_existing_safe_season_directory(tmp_path):
    media, downloads, request, download = context(
        tmp_path, kind="serie", title="Mi serie", year=None,
    )
    video = source(downloads, "Mi.Serie.S01E02.mkv")
    (media / "Series" / "Mi serie" / "Temporada 01").mkdir(parents=True)

    plan = plan_verified_media(download, request, [video], downloads, media)
    assert plan.entries[0].destination.name == "Mi serie - S01E02.mkv"


def test_series_rejects_existing_episode(tmp_path):
    media, downloads, request, download = context(
        tmp_path, kind="serie", title="Mi serie", year=None,
    )
    video = source(downloads, "Mi.Serie.S01E02.mkv")
    target = media / "Series" / "Mi serie" / "Temporada 01"
    target.mkdir(parents=True)
    (target / "Mi serie - S01E02.mkv").write_bytes(b"present")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


def test_movie_rejects_case_insensitive_collision(tmp_path):
    media, downloads, request, download = context(tmp_path)
    video = source(downloads, "film.mkv")
    (media / "Peliculas" / "película de prueba (2025)").mkdir()

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


def test_series_rejects_symlinked_season_directory(tmp_path):
    media, downloads, request, download = context(
        tmp_path, kind="serie", title="Mi serie", year=None,
    )
    video = source(downloads, "Mi.Serie.S01E02.mkv")
    show_folder = media / "Series" / "Mi serie"
    show_folder.mkdir()
    outside = tmp_path / "external-season"
    outside.mkdir()
    (show_folder / "Temporada 01").symlink_to(outside, target_is_directory=True)

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


def test_series_rejects_case_insensitive_episode_collision(tmp_path):
    media, downloads, request, download = context(
        tmp_path, kind="serie", title="Mi serie", year=None,
    )
    video = source(downloads, "Mi.Serie.S01E02.mkv")
    season = media / "Series" / "Mi serie" / "Temporada 01"
    season.mkdir(parents=True)
    (season / "MI SERIE - s01e02.mkv").write_bytes(b"existing")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, media)


def test_case_insensitive_duplicate_subtitles_rejected(tmp_path):
    media, downloads, request, download = context(tmp_path)
    video = source(downloads, "Video.mp4")
    one = source(downloads, "Video.es.srt", b"subtitle 1")
    two = source(downloads, "Video.ES.srt", b"subtitle 2")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video, one, two], downloads, media)


def test_does_not_accept_download_folder_as_library_root(tmp_path):
    media, downloads, request, download = context(tmp_path)
    video = source(downloads, "Video.mp4")

    with pytest.raises(UnsafeOrganizationPlan):
        plan_verified_media(download, request, [video], downloads, downloads)
