"""Orquestación completa en tmp_path: nunca se usan medios reales."""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine
from worker.organization_copy_sandbox import MARKER
from worker.organization_planner import UnsafeOrganizationPlan
from worker.organization_runner_sandbox import run_one_sandbox_organization

from app.models import Descarga, Perfil, Solicitud


@pytest.fixture
def setup(tmp_path):
    media = tmp_path / "media"
    downloads = media / "descargas_temporales"
    downloads.mkdir(parents=True)
    (media / "Peliculas").mkdir()
    (media / "Series").mkdir()
    (tmp_path / ".viewtv-organization-test-only").write_text(MARKER)

    video = downloads / "Mi corto.mkv"
    video.write_bytes(b"contenido legal de prueba" * 500)
    engine = create_engine(f"sqlite:///{tmp_path / 'test-organization.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Perfil(nombre="Prueba", pin_hash="hash-sin-valor")
        session.add(profile)
        session.flush()
        request = Solicitud(
            perfil_id=profile.id, titulo="Corto ficticio",
            tipo_medio="pelicula", anio=2026, estado="completada",
        )
        session.add(request)
        session.flush()
        download = Descarga(
            solicitud_id=request.id, titulo=request.titulo,
            estado="completada", progreso=1,
            estado_verificacion="verificada",
            organizacion_estado="pendiente",
            qbittorrent_hash="a" * 40,
        )
        session.add(download)
        session.commit()
        session.refresh(download)
        download_id = download.id

    def provider(download):
        assert download.id == download_id
        return [video]

    yield engine, tmp_path, video, download_id, provider
    engine.dispose()


def _record(engine, download_id):
    with Session(engine) as session:
        return session.get(Descarga, download_id)


def _expire_lease(engine, download_id):
    with Session(engine) as session:
        item = session.get(Descarga, download_id)
        item.organizacion_locked_until = datetime.now(UTC) - timedelta(seconds=1)
        session.add(item)
        session.commit()


def _destination(root):
    return root / "media" / "Peliculas" / "Corto ficticio (2026)"


def test_success_updates_database_and_preserves_original(setup):
    engine, root, source, download_id, provider = setup
    original = source.read_bytes()
    result = run_one_sandbox_organization(engine, root, "worker-a", provider)
    assert result == "organizada"
    dest_file = _destination(root) / "Corto ficticio (2026).mkv"
    assert hashlib.sha256(dest_file.read_bytes()).digest() == hashlib.sha256(original).digest()
    assert source.read_bytes() == original

    entry = _record(engine, download_id)
    assert entry.organizacion_estado == "organizada"
    assert entry.organizacion_intentos == 1
    assert entry.organizacion_locked_by is None
    assert run_one_sandbox_organization(engine, root, "worker-b", provider) == "sin_trabajos"


def test_bad_sandbox_rejected_before_claim(setup):
    engine, root, source, download_id, provider = setup
    (root / ".viewtv-organization-test-only").unlink()
    with pytest.raises(UnsafeOrganizationPlan):
        run_one_sandbox_organization(engine, root, "worker-a", provider)
    item = _record(engine, download_id)
    assert item.organizacion_intentos == 0
    assert item.organizacion_estado == "pendiente"
    assert source.exists()


def test_rejects_production_path_without_claiming(setup):
    engine, root, source, download_id, provider = setup
    with pytest.raises(UnsafeOrganizationPlan):
        run_one_sandbox_organization(engine, Path("/media"), "worker-a", provider)
    assert _record(engine, download_id).organizacion_intentos == 0
    assert source.exists()


def test_missing_or_foreign_source_goes_to_review(setup):
    engine, root, source, download_id, _ = setup
    foreign = root / "unrelated.mkv"
    foreign.write_bytes(b"fuera de la carpeta")
    result = run_one_sandbox_organization(
        engine, root, "worker-a", lambda _download: [foreign]
    )
    assert result == "requiere_revision"
    item = _record(engine, download_id)
    assert item.organizacion_estado == "requiere_revision"
    assert item.organizacion_ultimo_error == "archivo_invalido"
    assert source.exists() and foreign.exists()
    assert not _destination(root).exists()


def test_existing_destination_goes_to_review_without_writing(setup):
    engine, root, source, download_id, provider = setup
    destination = _destination(root)
    destination.mkdir()
    existing = destination / "material.txt"
    existing.write_text("material ajeno")
    assert run_one_sandbox_organization(engine, root, "worker-a", provider) == "requiere_revision"
    assert existing.read_text() == "material ajeno"
    assert source.exists()
    assert _record(engine, download_id).organizacion_estado == "requiere_revision"


def test_existing_staging_goes_to_review_without_deleting(setup):
    engine, root, source, download_id, provider = setup
    staging = root / "media" / "Peliculas" / f".viewtv-test-stage-{download_id}"
    staging.mkdir()
    (staging / "parcial.txt").write_text("no borrar")
    assert run_one_sandbox_organization(engine, root, "worker-a", provider) == "requiere_revision"
    assert (staging / "parcial.txt").read_text() == "no borrar"
    assert _record(engine, download_id).organizacion_estado == "requiere_revision"
    assert source.exists()


def test_crash_during_copy_does_not_publish_or_autoretry(setup, monkeypatch):
    import worker.organization_copy_sandbox as copier

    engine, root, source, download_id, provider = setup

    def crash(*_args, **_kwargs):
        raise RuntimeError("corte de energía simulado")

    monkeypatch.setattr(copier, "_copy_one", crash)
    with pytest.raises(RuntimeError, match="corte"):
        run_one_sandbox_organization(engine, root, "worker-a", provider)

    staging = root / "media" / "Peliculas" / f".viewtv-test-stage-{download_id}"
    assert staging.is_dir()
    assert not _destination(root).exists()
    assert source.exists()
    assert _record(engine, download_id).organizacion_estado == "pendiente"

    _expire_lease(engine, download_id)
    assert run_one_sandbox_organization(engine, root, "worker-b", provider) == "requiere_revision"
    assert staging.is_dir()
    assert not _destination(root).exists()


def test_crash_after_atomic_publish_stops_unsafe_retry(setup, monkeypatch):
    import worker.organization_runner_sandbox as runner

    engine, root, source, download_id, provider = setup

    def crash(*_args, **_kwargs):
        raise RuntimeError("corte después de publicación")

    with monkeypatch.context() as context:
        context.setattr(runner, "confirm_organization", crash)
        with pytest.raises(RuntimeError, match="después"):
            runner.run_one_sandbox_organization(engine, root, "worker-a", provider)

    published = _destination(root) / "Corto ficticio (2026).mkv"
    digest = hashlib.sha256(published.read_bytes()).hexdigest()
    assert source.exists()
    assert _record(engine, download_id).organizacion_estado == "pendiente"

    _expire_lease(engine, download_id)
    assert run_one_sandbox_organization(engine, root, "worker-b", provider) == "requiere_revision"
    assert hashlib.sha256(published.read_bytes()).hexdigest() == digest
    assert source.exists()


def test_lost_lease_during_copy_does_not_publish(setup, monkeypatch):
    import worker.organization_runner_sandbox as runner

    engine, root, source, download_id, provider = setup
    count = 0
    real_renew = runner.renew_organization_lease

    def fail_after_two_renewals(*args, **kwargs):
        nonlocal count
        count += 1
        if count >= 3:
            return False
        return real_renew(*args, **kwargs)

    monkeypatch.setattr(runner, "renew_organization_lease", fail_after_two_renewals)
    assert (
        runner.run_one_sandbox_organization(engine, root, "worker-a", provider)
        == "lease_perdido"
    )
    assert not _destination(root).exists()
    assert source.exists()
    assert _record(engine, download_id).organizacion_estado == "pendiente"
    assert (root / "media" / "Peliculas" / f".viewtv-test-stage-{download_id}").is_dir()


def test_provider_unexpected_crash_does_not_corrupt_db(setup):
    engine, root, source, download_id, _ = setup

    def crash(_):
        raise RuntimeError("falló proveedor de prueba")

    with pytest.raises(RuntimeError, match="proveedor"):
        run_one_sandbox_organization(engine, root, "worker-a", crash)
    assert _record(engine, download_id).organizacion_estado == "pendiente"
    assert source.exists()
    assert not _destination(root).exists()


def test_missing_provider_rejected_before_claim(setup):
    engine, root, source, download_id, _ = setup
    with pytest.raises(TypeError):
        run_one_sandbox_organization(engine, root, "worker-a", None)
    assert _record(engine, download_id).organizacion_intentos == 0
    assert source.exists()


def test_two_workers_concurrent_never_publish_twice(setup):
    from concurrent.futures import ThreadPoolExecutor

    engine, root, source, download_id, provider = setup

    def work(name):
        return run_one_sandbox_organization(engine, root, name, provider)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(work, ("worker-a", "worker-b")))

    assert sorted(results) == ["organizada", "sin_trabajos"]
    assert _record(engine, download_id).organizacion_intentos == 1
    assert len(list(_destination(root).glob("*.mkv"))) == 1
    assert source.exists()


def test_verification_revoked_during_source_lookup_prevents_copy(setup):
    engine, root, source, download_id, _ = setup

    def revoke(_download):
        with Session(engine) as session:
            record = session.get(Descarga, download_id)
            record.estado_verificacion = "fallida"
            session.add(record)
            session.commit()
        return [source]

    assert (
        run_one_sandbox_organization(engine, root, "worker-a", revoke)
        == "lease_perdido"
    )
    assert _record(engine, download_id).estado_verificacion == "fallida"
    assert not _destination(root).exists()
    assert source.exists()


def test_unverified_work_is_never_processed(setup):
    engine, root, source, download_id, provider = setup
    with Session(engine) as session:
        row = session.get(Descarga, download_id)
        row.estado_verificacion = "pendiente"
        session.add(row)
        session.commit()

    assert (
        run_one_sandbox_organization(engine, root, "worker-a", provider)
        == "sin_trabajos"
    )
    assert _record(engine, download_id).organizacion_intentos == 0
    assert source.exists()
