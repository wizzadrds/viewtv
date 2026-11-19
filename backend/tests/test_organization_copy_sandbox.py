"""Solo /tmp: simula copias atómicas, sin usar bibliotecas de producción."""

from pathlib import Path

import pytest
from worker.organization_copy_sandbox import (
    MARKER,
    UnsafeOrganizationPlan,
    publish_test_plan,
)
from worker.organization_planner import (
    OrganizationEntry,
    OrganizationPlan,
    plan_verified_media,
)

from app.models import Descarga, Solicitud


def environment(tmp_path: Path, kind="pelicula"):
    media = tmp_path / "media"
    download_root = media / "descargas_temporales"
    download_root.mkdir(parents=True)
    (media / "Peliculas").mkdir()
    (media / "Series").mkdir()
    (tmp_path / ".viewtv-organization-test-only").write_text(MARKER)
    request = Solicitud(
        id=10, perfil_id=1, titulo="Prueba de copia",
        tipo_medio=kind, anio=2025 if kind == "pelicula" else None,
        estado="completada",
    )
    download = Descarga(
        id=14, solicitud_id=10, titulo="Prueba de copia",
        estado="completada", progreso=1,
        estado_verificacion="verificada",
    )
    return media, download_root, request, download


def make_plan(tmp_path, *, kind="pelicula", subtitle=False):
    media, download_root, request, download = environment(tmp_path, kind)
    video_name = "Test.S01E02.mkv" if kind == "serie" else "Test.mkv"
    video = download_root / video_name
    video.write_bytes(b"contenido temporal propio de prueba" * 24)
    files = [video]
    if subtitle:
        sub = download_root / ("Test.S01E02.es.srt" if kind == "serie" else "Test.es.srt")
        sub.write_bytes(b"1\n00:00:00,000 --> 00:00:01,000\nPrueba\n")
        files.append(sub)
    return plan_verified_media(download, request, files, download_root, media), files


@pytest.mark.parametrize("kind", ["pelicula", "serie"])
@pytest.mark.parametrize("subtitle", [False, True])
def test_publishes_copies_without_altering_originals(tmp_path, kind, subtitle):
    plan, sources = make_plan(tmp_path, kind=kind, subtitle=subtitle)
    originals = [p.read_bytes() for p in sources]
    destination = publish_test_plan(plan, tmp_path)
    assert destination.is_dir()
    assert all(
        entry.destination.read_bytes() == content
        for entry, content in zip(plan.entries, originals)
    )
    assert [p.read_bytes() for p in sources] == originals
    assert not (tmp_path / "media" / plan.library / ".viewtv-test-stage-14").exists()
    assert len(list(destination.rglob("*.*"))) == len(plan.entries)


def test_fails_closed_without_marker(tmp_path):
    plan, sources = make_plan(tmp_path)
    (tmp_path / ".viewtv-organization-test-only").unlink()
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(plan, tmp_path)
    assert sources[0].exists()
    assert not plan.entries[0].destination.exists()


def test_rejects_modified_marker(tmp_path):
    plan, _ = make_plan(tmp_path)
    (tmp_path / ".viewtv-organization-test-only").write_text("not a test")
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(plan, tmp_path)


def test_rejects_real_media_root_outside_tmp(tmp_path):
    plan, _ = make_plan(tmp_path)
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(plan, Path("/media"))


def test_refuses_second_run_and_never_overwrites(tmp_path):
    plan, sources = make_plan(tmp_path)
    target = publish_test_plan(plan, tmp_path)
    snapshot = [p.read_bytes() for p in target.iterdir()]
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(plan, tmp_path)
    assert [p.read_bytes() for p in target.iterdir()] == snapshot
    assert sources[0].exists()


def test_rejects_source_modified_after_plan(tmp_path):
    plan, sources = make_plan(tmp_path)
    sources[0].write_bytes(b"changed")
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(plan, tmp_path)
    assert not plan.entries[0].destination.exists()
    assert sources[0].read_bytes() == b"changed"


def test_rejects_source_symlink_replacement(tmp_path):
    plan, sources = make_plan(tmp_path)
    sources[0].unlink()
    outside = tmp_path / "other.mkv"
    outside.write_bytes(b"not allowed")
    sources[0].symlink_to(outside)
    with pytest.raises(OSError):
        publish_test_plan(plan, tmp_path)
    assert outside.read_bytes() == b"not allowed"
    assert not plan.entries[0].destination.exists()


def test_rejects_source_directory_symlink_replacement(tmp_path):
    plan, sources = make_plan(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    outside_file = outside / "Test.mkv"
    outside_file.write_bytes(sources[0].read_bytes())
    sources[0].unlink()
    source_root = sources[0].parent
    source_root.rmdir()
    source_root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(plan, tmp_path)
    assert not plan.entries[0].destination.exists()


def test_rejects_preexisting_staging_without_cleanup(tmp_path):
    plan, sources = make_plan(tmp_path)
    staged = tmp_path / "media" / plan.library / ".viewtv-test-stage-14"
    staged.mkdir()
    (staged / "precious.txt").write_text("keep")
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(plan, tmp_path)
    assert (staged / "precious.txt").read_text() == "keep"
    assert sources[0].exists()


def test_crash_while_copying_leaves_staging_for_review(tmp_path, monkeypatch):
    import worker.organization_copy_sandbox as copier

    plan, sources = make_plan(tmp_path)
    def crash(*args, **kwargs):
        raise RuntimeError("simulated power loss")
    monkeypatch.setattr(copier, "_copy_one", crash)
    with pytest.raises(RuntimeError, match="power loss"):
        copier.publish_test_plan(plan, tmp_path)
    assert not plan.entries[0].destination.exists()
    assert sources[0].exists()
    staged = tmp_path / "media" / plan.library / ".viewtv-test-stage-14"
    assert staged.is_dir()
    with pytest.raises(UnsafeOrganizationPlan):
        copier.publish_test_plan(plan, tmp_path)
    assert staged.is_dir()


def test_rejects_destination_outside_test_library(tmp_path):
    plan, sources = make_plan(tmp_path)
    forged = OrganizationPlan(
        download_id=plan.download_id,
        library=plan.library,
        entries=(OrganizationEntry(
            source=sources[0], destination=tmp_path / "other" / "unsafe.mkv",
            size_bytes=sources[0].stat().st_size,
        ),),
    )
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(forged, tmp_path)
    assert not (tmp_path / "other").exists()


def test_rejects_case_insensitive_destination_collision(tmp_path):
    plan, sources = make_plan(tmp_path)
    destination = plan.entries[0].destination.parent
    alternate = destination.parent / destination.name.upper()
    alternate.mkdir()
    (alternate / "safe.txt").write_text("existing")
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(plan, tmp_path)
    assert (alternate / "safe.txt").read_text() == "existing"
    assert sources[0].exists()


def test_does_not_reuse_existing_series_folder(tmp_path):
    plan, sources = make_plan(tmp_path, kind="serie")
    destination = plan.entries[0].destination.parent.parent
    destination.mkdir()
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(plan, tmp_path)
    assert sources[0].exists()


def test_rejects_oversized_test_source(tmp_path):
    plan, sources = make_plan(tmp_path)
    forged = OrganizationPlan(
        download_id=plan.download_id,
        library=plan.library,
        entries=(OrganizationEntry(
            source=sources[0], destination=plan.entries[0].destination,
            size_bytes=33 * 1024 * 1024,
        ),),
    )
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(forged, tmp_path)
    assert sources[0].exists()
    assert not plan.entries[0].destination.exists()


def test_atomic_publish_refuses_race_with_new_destination(tmp_path, monkeypatch):
    import worker.organization_copy_sandbox as copier

    plan, originals = make_plan(tmp_path)
    original_publish = copier._publish_noreplace
    final = plan.entries[0].destination.parent

    def concurrent_directory(fd, staged, final_name):
        (final.parent / final_name).mkdir()
        (final.parent / final_name / "important.txt").write_text("existing")
        return original_publish(fd, staged, final_name)

    monkeypatch.setattr(copier, "_publish_noreplace", concurrent_directory)
    with pytest.raises(UnsafeOrganizationPlan, match="Ya existe"):
        copier.publish_test_plan(plan, tmp_path)
    assert (final / "important.txt").read_text() == "existing"
    assert originals[0].exists()
    assert (final.parent / ".viewtv-test-stage-14").is_dir()


def test_rejects_symlink_library_after_planning(tmp_path):
    plan, files = make_plan(tmp_path)
    category = tmp_path / "media" / plan.library
    category.rmdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    category.symlink_to(outside, target_is_directory=True)
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(plan, tmp_path)
    assert list(outside.iterdir()) == []
    assert files[0].exists()


def test_rejects_zero_length_file_in_forged_plan(tmp_path):
    plan, sources = make_plan(tmp_path)
    sources[0].write_bytes(b"")
    forged = OrganizationPlan(
        download_id=plan.download_id,
        library=plan.library,
        entries=(
            OrganizationEntry(
                source=sources[0],
                destination=plan.entries[0].destination,
                size_bytes=0,
            ),
        ),
    )
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(forged, tmp_path)
    assert not plan.entries[0].destination.exists()


def test_rejects_symlinked_marker(tmp_path):
    plan, files = make_plan(tmp_path)
    marker = tmp_path / ".viewtv-organization-test-only"
    marker.unlink()
    real_marker = tmp_path / "marker.txt"
    real_marker.write_text(MARKER)
    marker.symlink_to(real_marker)
    with pytest.raises(UnsafeOrganizationPlan):
        publish_test_plan(plan, tmp_path)
    assert files[0].exists()


def test_detects_destination_corruption_and_never_publishes(tmp_path, monkeypatch):
    import os

    import worker.organization_copy_sandbox as copier

    plan, sources = make_plan(tmp_path)
    original = sources[0].read_bytes()

    def damaged_write(fd, data):
        corrupted = b"X" * len(data)
        return os.write(fd, corrupted)

    monkeypatch.setattr(copier, "_write_chunk", damaged_write)
    with pytest.raises(UnsafeOrganizationPlan, match="copiado no coincide"):
        copier.publish_test_plan(plan, tmp_path)

    assert sources[0].read_bytes() == original
    assert not plan.entries[0].destination.exists()
    stage = tmp_path / "media" / plan.library / ".viewtv-test-stage-14"
    assert stage.is_dir()
    assert any(stage.iterdir())
