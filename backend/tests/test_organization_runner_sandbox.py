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
            verificada_en=datetime.now(UTC),
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


def _simulated_qbittorrent(root, download_id, *, tag=None, save_path=None):
    from types import SimpleNamespace

    from worker.organization_torrent_guard import EXPECTED_SAVE_PATH

    source = root / "media" / "descargas_temporales" / "Mi corto.mkv"
    calls = []
    expected_tag = f"viewtv-descarga-{download_id}"
    actual_tag = tag if tag is not None else expected_tag
    actual_path = save_path if save_path is not None else EXPECTED_SAVE_PATH

    def torrents_info(*, hashes):
        calls.append(("GET torrents", hashes))
        return [{
            "hash": "a" * 40,
            "tags": actual_tag,
            "save_path": actual_path,
            "state": "stoppedUP",
            "progress": 1.0,
            "total_size": source.stat().st_size,
        }]

    def torrent_files(torrent_hash):
        calls.append(("GET files", torrent_hash))
        return [{
            "name": source.name,
            "size": source.stat().st_size,
            "progress": 1.0,
            "priority": 1,
        }]

    return SimpleNamespace(
        torrents_info=torrents_info,
        torrent_files=torrent_files,
        calls=calls,
    )


def test_simulated_owned_torrent_completes_organization(setup):
    from worker.organization_torrent_guard import verify_organization_torrent_identity

    engine, root, source, download_id, _ = setup
    client = _simulated_qbittorrent(root, download_id)

    def provider(download):
        return verify_organization_torrent_identity(
            client, download, root / "media" / "descargas_temporales",
        )

    assert run_one_sandbox_organization(
        engine, root, "worker-a", provider
    ) == "organizada"
    assert client.calls == [
        ("GET torrents", ["a" * 40]),
        ("GET files", "a" * 40),
    ]
    assert _destination(root).is_dir()
    assert source.exists()
    assert _record(engine, download_id).organizacion_estado == "organizada"


def test_simulated_foreign_torrent_cannot_be_organized(setup):
    from worker.organization_torrent_guard import verify_organization_torrent_identity

    engine, root, source, download_id, _ = setup
    client = _simulated_qbittorrent(root, download_id, tag="viewtv-descarga-999")

    def provider(download):
        return verify_organization_torrent_identity(
            client, download, root / "media" / "descargas_temporales",
        )

    assert run_one_sandbox_organization(
        engine, root, "worker-a", provider
    ) == "requiere_revision"
    assert client.calls == [("GET torrents", ["a" * 40])]
    assert _record(engine, download_id).organizacion_ultimo_error == "archivo_invalido"
    assert not _destination(root).exists()
    assert source.exists()


def test_simulated_torrent_wrong_savepath_rejected_without_file_read(setup):
    from worker.organization_torrent_guard import verify_organization_torrent_identity

    engine, root, source, download_id, _ = setup
    client = _simulated_qbittorrent(
        root, download_id, save_path=r"C:\VIEWTV\media\Peliculas"
    )

    def provider(download):
        return verify_organization_torrent_identity(
            client, download, root / "media" / "descargas_temporales",
        )

    assert run_one_sandbox_organization(
        engine, root, "worker-a", provider
    ) == "requiere_revision"
    assert client.calls == [("GET torrents", ["a" * 40])]
    assert not _destination(root).exists()
    assert source.exists()


def test_simulated_qbittorrent_error_defers_without_staging(setup):
    from app.qbittorrent import QBittorrentError

    engine, root, source, download_id, _ = setup

    def disconnected(_download):
        raise QBittorrentError("Conexión simulada interrumpida")

    assert run_one_sandbox_organization(
        engine, root, "worker-a", disconnected
    ) == "aplazada"
    item = _record(engine, download_id)
    assert item.organizacion_estado == "pendiente"
    assert item.organizacion_disponible_desde is not None
    assert item.organizacion_locked_by is None
    assert item.organizacion_ultimo_error == "comunicacion"
    assert source.exists()
    assert not _destination(root).exists()
    assert not (
        root / "media" / "Peliculas" / f".viewtv-test-stage-{download_id}"
    ).exists()


def _existing_season_setup(setup):
    engine, root, old_video, download_id, _ = setup
    new_video = old_video.with_name("Serie.Ficticia.S01E03.mkv")
    old_video.rename(new_video)
    show = root / "media" / "Series" / "Serie ficticia"
    season = show / "Temporada 01"
    season.mkdir(parents=True)
    previous = season / "Serie ficticia - S01E02.mkv"
    previous.write_bytes(b"episodio previo, no alterar")
    with Session(engine) as session:
        row = session.get(Descarga, download_id)
        request = session.get(Solicitud, row.solicitud_id)
        request.tipo_medio = "serie"
        request.titulo = "Serie ficticia"
        row.titulo = "Serie ficticia"
        session.add(request)
        session.add(row)
        session.commit()

    def provider(download):
        assert download.id == download_id
        return [new_video]

    return engine, root, new_video, download_id, provider, season, previous


def test_existing_season_single_episode_coordinated_without_overwrite(setup):
    engine, root, source, download_id, provider, season, previous = (
        _existing_season_setup(setup)
    )
    previous_content = previous.read_bytes()
    original = source.read_bytes()
    assert run_one_sandbox_organization(
        engine, root, "worker-a", provider
    ) == "organizada"

    episode = season / "Serie ficticia - S01E03.mkv"
    assert episode.read_bytes() == original
    assert previous.read_bytes() == previous_content
    assert source.read_bytes() == original
    assert _record(engine, download_id).organizacion_estado == "organizada"
    assert run_one_sandbox_organization(
        engine, root, "worker-b", provider
    ) == "sin_trabajos"


def test_existing_season_after_publish_crash_requires_review(setup, monkeypatch):
    import worker.organization_runner_sandbox as runner

    engine, root, source, download_id, provider, season, previous = (
        _existing_season_setup(setup)
    )
    old_data = previous.read_bytes()

    def crash(*_args, **_kwargs):
        raise RuntimeError("caída después de publicar episodio")

    with monkeypatch.context() as patch:
        patch.setattr(runner, "confirm_organization", crash)
        with pytest.raises(RuntimeError, match="publicar"):
            runner.run_one_sandbox_organization(engine, root, "w1", provider)

    episode = season / "Serie ficticia - S01E03.mkv"
    final_data = episode.read_bytes()
    _expire_lease(engine, download_id)
    assert runner.run_one_sandbox_organization(
        engine, root, "w2", provider
    ) == "requiere_revision"
    assert episode.read_bytes() == final_data
    assert previous.read_bytes() == old_data
    assert source.exists()


def test_existing_season_subtitle_group_requires_manual_review(setup):
    engine, root, source, download_id, provider, season, previous = (
        _existing_season_setup(setup)
    )
    subtitles = source.with_name("Serie.Ficticia.S01E03.es.srt")
    subtitles.write_bytes(b"subtitulo simulado")
    old_data = previous.read_bytes()

    def provider_with_subtitle(download):
        return provider(download) + [subtitles]

    assert run_one_sandbox_organization(
        engine, root, "w1", provider_with_subtitle
    ) == "requiere_revision"
    assert _record(engine, download_id).organizacion_estado == "requiere_revision"
    assert previous.read_bytes() == old_data
    assert not (season / "Serie ficticia - S01E03.mkv").exists()
    assert source.exists() and subtitles.exists()


def test_existing_season_preexisting_episode_blocked_without_cleanup(setup):
    engine, root, source, download_id, provider, season, previous = (
        _existing_season_setup(setup)
    )
    target = season / "Serie ficticia - S01E03.mkv"
    target.write_bytes(b"ya existe, no sobrescribir")
    assert run_one_sandbox_organization(
        engine, root, "w1", provider
    ) == "requiere_revision"
    assert target.read_bytes() == b"ya existe, no sobrescribir"
    assert previous.read_bytes() == b"episodio previo, no alterar"
    assert source.exists()



def test_independent_heartbeat_renews_during_slow_provider(setup):
    """El reloj del lease avanza aunque el proveedor no llame callbacks."""
    from time import sleep

    engine, root, source, download_id, _ = setup
    observed = []

    def slow_provider(_download):
        with Session(engine) as session:
            before = session.get(Descarga, download_id).organizacion_locked_until
        sleep(0.20)
        with Session(engine) as session:
            after = session.get(Descarga, download_id).organizacion_locked_until
        observed.append((before, after))
        return [source]

    assert run_one_sandbox_organization(
        engine, root, "worker-ficticio", slow_provider,
        independent_heartbeat=True, heartbeat_interval_seconds=0.02,
    ) == "organizada"
    assert observed and observed[0][1] > observed[0][0]
    assert source.is_file() and _destination(root).is_dir()
    assert _record(engine, download_id).organizacion_intentos == 1


def test_independent_heartbeat_renews_during_blocked_copy(setup, monkeypatch):
    """El hilo sigue renovando mientras una escritura del copiador duerme."""
    from time import sleep

    import worker.organization_copy_sandbox as copier

    engine, root, source, download_id, provider = setup
    original_write = copier._write_chunk
    observed = []

    def delayed_write(fd, data):
        if not observed:
            with Session(engine) as session:
                before = session.get(Descarga, download_id).organizacion_locked_until
            sleep(0.20)
            with Session(engine) as session:
                after = session.get(Descarga, download_id).organizacion_locked_until
            observed.append((before, after))
        return original_write(fd, data)

    monkeypatch.setattr(copier, "_write_chunk", delayed_write)
    assert run_one_sandbox_organization(
        engine, root, "worker-ficticio", provider,
        independent_heartbeat=True, heartbeat_interval_seconds=0.02,
    ) == "organizada"
    assert observed and observed[0][1] > observed[0][0]
    assert source.is_file() and _destination(root).is_dir()


def test_independent_lease_lost_during_write_never_publishes(setup, monkeypatch):
    """Si el propietario cambia durante I/O, staging queda para revisión."""
    from time import sleep

    import worker.organization_copy_sandbox as copier

    engine, root, source, download_id, provider = setup
    original_write = copier._write_chunk
    injected = False

    def revoke_during_write(fd, data):
        nonlocal injected
        if not injected:
            injected = True
            with Session(engine) as session:
                row = session.get(Descarga, download_id)
                row.organizacion_locked_by = "otro-worker"
                session.add(row)
                session.commit()
            sleep(0.10)
        return original_write(fd, data)

    monkeypatch.setattr(copier, "_write_chunk", revoke_during_write)
    assert run_one_sandbox_organization(
        engine, root, "worker-ficticio", provider,
        independent_heartbeat=True, heartbeat_interval_seconds=0.02,
    ) == "lease_perdido"
    assert injected and source.is_file()
    assert not _destination(root).exists()
    stage = root / "media" / "Peliculas" / f".viewtv-test-stage-{download_id}"
    assert stage.is_dir()
    assert _record(engine, download_id).organizacion_estado == "pendiente"


def test_independent_same_worker_new_attempt_never_publishes(setup, monkeypatch):
    """Otra reclamación del mismo nombre deja sin permiso al intento viejo."""
    from time import sleep

    import worker.organization_copy_sandbox as copier

    engine, root, source, download_id, provider = setup
    original_write = copier._write_chunk
    injected = False

    def supersede_attempt(fd, data):
        nonlocal injected
        if not injected:
            injected = True
            with Session(engine) as session:
                row = session.get(Descarga, download_id)
                assert row.organizacion_intentos == 1
                row.organizacion_intentos = 2
                session.add(row)
                session.commit()
            sleep(0.10)
        return original_write(fd, data)

    monkeypatch.setattr(copier, "_write_chunk", supersede_attempt)
    assert run_one_sandbox_organization(
        engine, root, "worker-ficticio", provider,
        independent_heartbeat=True, heartbeat_interval_seconds=0.02,
    ) == "lease_perdido"
    assert injected and source.is_file()
    assert not _destination(root).exists()
    row = _record(engine, download_id)
    assert row.organizacion_intentos == 2
    assert row.organizacion_estado == "pendiente"


def test_independent_provider_crash_terminates_heartbeat(setup):
    from threading import enumerate as active_threads

    engine, root, source, download_id, _ = setup

    def fail(_download):
        raise RuntimeError("proveedor ficticio interrumpido")

    with pytest.raises(RuntimeError, match="interrumpido"):
        run_one_sandbox_organization(
            engine, root, "worker-ficticio", fail,
            independent_heartbeat=True, heartbeat_interval_seconds=0.02,
        )
    assert not any(thread.name == "viewtv-lease-sandbox" for thread in active_threads())
    assert source.is_file()
    assert not _destination(root).exists()
    assert _record(engine, download_id).organizacion_estado == "pendiente"


def test_independent_rejects_foreign_database_before_claim(setup):
    engine, root, source, download_id, provider = setup
    alien = create_engine(f"sqlite:///{root / 'otro.db'}")
    try:
        with pytest.raises(UnsafeOrganizationPlan):
            run_one_sandbox_organization(
                alien, root, "worker-ficticio", provider,
                independent_heartbeat=True,
            )
    finally:
        alien.dispose()
    assert _record(engine, download_id).organizacion_intentos == 0
    assert source.is_file() and not _destination(root).exists()



@pytest.mark.parametrize("interval", [0, 31, True, "0.02"])
def test_independent_invalid_interval_refused_before_claim(setup, interval):
    engine, root, source, download_id, provider = setup
    with pytest.raises(ValueError):
        run_one_sandbox_organization(
            engine, root, "worker-ficticio", provider,
            independent_heartbeat=True,
            heartbeat_interval_seconds=interval,
        )
    assert _record(engine, download_id).organizacion_intentos == 0
    assert source.is_file() and not _destination(root).exists()
