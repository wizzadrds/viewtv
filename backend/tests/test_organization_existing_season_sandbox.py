"""Pruebas de episodios aislados en temporadas ficticias preexistentes."""


import pytest
from worker.organization_copy_sandbox import MARKER
from worker.organization_existing_season_sandbox import publish_test_existing_episode
from worker.organization_planner import (
    OrganizationEntry,
    OrganizationPlan,
    UnsafeOrganizationPlan,
    plan_verified_media,
)

from app.models import Descarga, Solicitud


def prepare(tmp_path):
    media = tmp_path / "media"
    sources = media / "descargas_temporales"
    season = media / "Series" / "Serie ficticia" / "Temporada 01"
    sources.mkdir(parents=True)
    season.mkdir(parents=True)
    (media / "Peliculas").mkdir()
    (tmp_path / ".viewtv-organization-test-only").write_text(MARKER)
    video = sources / "Serie.S01E02.mkv"
    video.write_bytes(b"episodio de prueba" * 40)
    request = Solicitud(
        id=7, perfil_id=1, titulo="Serie ficticia",
        tipo_medio="serie", estado="completada",
    )
    download = Descarga(
        id=20, solicitud_id=7, titulo="Serie ficticia",
        estado="completada", progreso=1.0,
        estado_verificacion="verificada",
    )
    plan = plan_verified_media(download, request, [video], sources, media)
    return plan, video, season


def test_copies_episode_into_existing_season_without_changing_source(tmp_path):
    plan, source, season = prepare(tmp_path)
    previous = season / "Serie ficticia - S01E01.mkv"
    previous.write_bytes(b"otro episodio")
    original = source.read_bytes()

    result = publish_test_existing_episode(plan, tmp_path)
    assert result == plan.entries[0].destination
    assert result.read_bytes() == original
    assert previous.read_bytes() == b"otro episodio"
    assert source.read_bytes() == original
    assert not (season / ".viewtv-test-episode-20").exists()


def test_refuses_same_episode_twice(tmp_path):
    plan, source, season = prepare(tmp_path)
    published = publish_test_existing_episode(plan, tmp_path)
    snapshot = published.read_bytes()
    with pytest.raises(UnsafeOrganizationPlan, match="existe"):
        publish_test_existing_episode(plan, tmp_path)
    assert published.read_bytes() == snapshot
    assert source.exists()


def test_case_insensitive_existing_collision(tmp_path):
    plan, source, season = prepare(tmp_path)
    collision = season / plan.entries[0].destination.name.upper()
    collision.write_bytes(b"valor original")
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_existing_episode(plan, tmp_path)
    assert collision.read_bytes() == b"valor original"
    assert source.exists()


def test_refuses_staging_from_interrupted_operation(tmp_path):
    plan, source, season = prepare(tmp_path)
    staged = season / ".viewtv-test-episode-20"
    staged.mkdir()
    (staged / "revisar.txt").write_bytes(b"no borrar")
    with pytest.raises(UnsafeOrganizationPlan, match="revisión"):
        publish_test_existing_episode(plan, tmp_path)
    assert (staged / "revisar.txt").read_bytes() == b"no borrar"
    assert source.exists()


def test_missing_season_requires_review(tmp_path):
    plan, source, season = prepare(tmp_path)
    season.rmdir()
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_existing_episode(plan, tmp_path)
    assert source.exists()
    assert not season.exists()


def test_rejects_symlinked_season_after_plan(tmp_path):
    plan, source, season = prepare(tmp_path)
    outside = tmp_path / "otro-directorio"
    outside.mkdir()
    season.rmdir()
    season.symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        publish_test_existing_episode(plan, tmp_path)
    assert list(outside.iterdir()) == []
    assert source.exists()


def test_rejects_symlinked_show_after_plan(tmp_path):
    plan, source, season = prepare(tmp_path)
    outside = tmp_path / "serie-ajena"
    outside.mkdir()
    season.rmdir()
    season.parent.rmdir()
    season.parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        publish_test_existing_episode(plan, tmp_path)
    assert list(outside.iterdir()) == []
    assert source.exists()


def test_rejects_unmarked_sandbox_before_copy(tmp_path):
    plan, source, _ = prepare(tmp_path)
    (tmp_path / ".viewtv-organization-test-only").unlink()
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_existing_episode(plan, tmp_path)
    assert source.exists()


def test_rejects_outside_destination(tmp_path):
    plan, source, _ = prepare(tmp_path)
    forged = OrganizationPlan(
        download_id=20, library="Series",
        entries=(OrganizationEntry(
            source, tmp_path / "ajeno" / "Temporada 01" / "otro.mkv",
            source.stat().st_size,
        ),),
    )
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_existing_episode(forged, tmp_path)
    assert source.exists()
    assert not (tmp_path / "ajeno").exists()


def test_refuses_multiple_files_due_to_nonatomic_group(tmp_path):
    plan, source, season = prepare(tmp_path)
    forged = OrganizationPlan(
        download_id=20, library="Series",
        entries=(plan.entries[0], plan.entries[0]),
    )
    with pytest.raises(UnsafeOrganizationPlan, match="individuales"):
        publish_test_existing_episode(forged, tmp_path)
    assert source.exists()
    assert not any(season.iterdir())


def test_rejects_changed_source_size_after_plan(tmp_path):
    plan, source, season = prepare(tmp_path)
    source.write_bytes(b"alterado")
    with pytest.raises(UnsafeOrganizationPlan, match="cambiado"):
        publish_test_existing_episode(plan, tmp_path)
    assert source.read_bytes() == b"alterado"
    assert not plan.entries[0].destination.exists()
    assert (season / ".viewtv-test-episode-20").is_dir()


def test_interruption_leaves_staging_without_publishing(tmp_path):
    plan, source, season = prepare(tmp_path)

    def interrupt():
        raise RuntimeError("fallo simulado de I/O")

    with pytest.raises(RuntimeError, match="simulado"):
        publish_test_existing_episode(
            plan, tmp_path, progress_callback=interrupt,
        )
    assert not plan.entries[0].destination.exists()
    assert source.exists()
    assert (season / ".viewtv-test-episode-20").is_dir()


def test_race_at_publication_does_not_replace_episode(tmp_path, monkeypatch):
    import os

    import worker.organization_existing_season_sandbox as module

    plan, source, season = prepare(tmp_path)
    old_link = os.link

    def rival_link(path, target, **kwargs):
        real_target = season / target
        real_target.write_bytes(b"episodio colocado por otro proceso")
        return old_link(path, target, **kwargs)

    monkeypatch.setattr(module.os, "link", rival_link)
    with pytest.raises(UnsafeOrganizationPlan, match="apareció"):
        publish_test_existing_episode(plan, tmp_path)
    assert plan.entries[0].destination.read_bytes() == (
        b"episodio colocado por otro proceso"
    )
    assert source.exists()
    assert (season / ".viewtv-test-episode-20").is_dir()
