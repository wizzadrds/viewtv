"""Aceptación de corto ficticio: organización de laboratorio -> Jellyfin.

No se abre ni modifica contenido real. El escaneo usa HTTP simulado,
la publicación solo admite carpetas pytest bajo /tmp marcadas.
"""

import hashlib
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select
from worker.organization_copy_sandbox import MARKER
from worker.organization_jellyfin_bridge_sandbox import (
    request_scan_for_published_sandbox_download,
    run_one_sandbox_organization_with_jellyfin,
)
from worker.organization_planner import UnsafeOrganizationPlan

from app.config import Settings
from app.jellyfin import JellyfinClient, JellyfinError, synchronize_catalog
from app.models import Descarga, Medio, Perfil, Solicitud


class SimulatedJellyfin:
    """Escaneo asíncrono ficticio; no expone contenido hasta marcarlo terminado."""

    def __init__(self, media_dir):
        self.media_dir = media_dir
        self.scan_requested = 0
        self.scan_finished = False

    def request_library_scan(self) -> None:
        self.scan_requested += 1

    def finish_scan(self) -> None:
        assert self.scan_requested > 0
        self.scan_finished = True

    def get_items(self, start_index: int, limit: int) -> dict:
        assert start_index == 0
        movie = self.media_dir / "Peliculas" / "Corto ficticio (2026)" / "Corto ficticio (2026).mkv"
        items = (
            [
                {
                    "Id": "pelicula-ficticia-1",
                    "Type": "Movie",
                    "Name": "Corto ficticio (2026)",
                    "ProductionYear": 2026,
                }
            ]
            if self.scan_finished and movie.is_file()
            else []
        )
        return {"Items": items, "TotalRecordCount": len(items)}


@pytest.fixture
def lab(tmp_path):
    media = tmp_path / "media"
    stage = media / "descargas_temporales"
    stage.mkdir(parents=True)
    (media / "Peliculas").mkdir()
    (media / "Series").mkdir()
    (tmp_path / ".viewtv-organization-test-only").write_text(MARKER)
    video = stage / "Corto original.mkv"
    video.write_bytes(b"obra audiovisual ficticia / sin contenido real" * 300)
    engine = create_engine(f"sqlite:///{tmp_path / 'test-organization.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        profile = Perfil(nombre="Perfil ficticio", pin_hash="hash-sintetico")
        session.add(profile)
        session.flush()
        request = Solicitud(
            perfil_id=profile.id,
            titulo="Corto ficticio",
            tipo_medio="pelicula",
            anio=2026,
            estado="completada",
        )
        session.add(request)
        session.flush()
        download = Descarga(
            solicitud_id=request.id,
            titulo=request.titulo,
            estado="completada",
            progreso=1,
            estado_verificacion="verificada",
            verificada_en=datetime.now(UTC),
            organizacion_estado="pendiente",
            qbittorrent_hash="a" * 40,
        )
        session.add(download)
        session.commit()
        session.refresh(download)
        download_id = download.id
    assert download_id is not None

    def source(download):
        assert download.id == download_id
        return [video]

    yield engine, tmp_path, video, download_id, source
    engine.dispose()


def state(engine: Engine, download_id: int) -> Descarga | None:
    with Session(engine) as session:
        return session.get(Descarga, download_id)


def test_publish_requests_scan_and_catalog_shows_media_only_after_scan(lab):
    engine, root, source, download_id, provider = lab
    jellyfin = SimulatedJellyfin(root / "media")
    original = source.read_bytes()
    assert (
        run_one_sandbox_organization_with_jellyfin(
            engine,
            root,
            "worker-ficticio",
            provider,
            expected_download_id=download_id,
            jellyfin=jellyfin,
        )
        == "escaneo_solicitado"
    )
    assert jellyfin.scan_requested == 1
    assert state(engine, download_id).organizacion_estado == "organizada"
    dest = root / "media" / "Peliculas" / "Corto ficticio (2026)" / "Corto ficticio (2026).mkv"
    assert dest.is_file()
    assert hashlib.sha256(dest.read_bytes()).digest() == hashlib.sha256(original).digest()
    assert source.read_bytes() == original

    # HTTP 204 de escaneo no implica que Jellyfin haya indexado la película.
    with Session(engine) as session:
        assert synchronize_catalog(session, client=jellyfin) == 0
        assert session.exec(select(Medio)).all() == []

    jellyfin.finish_scan()
    with Session(engine) as session:
        assert synchronize_catalog(session, client=jellyfin) == 1
        media = session.exec(select(Medio)).all()
        assert len(media) == 1
        assert media[0].titulo == "Corto ficticio (2026)"
        assert media[0].disponible_en_jellyfin

    assert (
        run_one_sandbox_organization_with_jellyfin(
            engine,
            root,
            "otro-worker",
            provider,
            expected_download_id=download_id,
            jellyfin=jellyfin,
        )
        == "sin_trabajos"
    )
    assert jellyfin.scan_requested == 1


def test_jellyfin_http_client_accepts_204_without_response_body():
    observed = []

    def handler(request: httpx.Request):
        observed.append(request)
        assert request.method == "POST"
        assert request.url.path == "/Library/Refresh"
        assert request.headers["authorization"] == 'MediaBrowser Token="clave-ficticia"'
        return httpx.Response(204, content=b"", request=request)

    settings = Settings(
        _env_file=None,
        jellyfin_base_url="http://jellyfin-ficticio.invalid:8096",
        jellyfin_api_key="clave-ficticia",
    )
    client = JellyfinClient(settings, transport=httpx.MockTransport(handler))
    assert client.request_library_scan() is None
    assert len(observed) == 1


@pytest.mark.parametrize("status", [401, 403, 500])
def test_scan_failure_is_sanitized_without_logging_secrets(status):
    def handler(request: httpx.Request):
        return httpx.Response(
            status,
            content=b"clave-prohibida/ubicacion-privada",
            request=request,
        )

    settings = Settings(
        _env_file=None,
        jellyfin_base_url="http://jellyfin-ficticio.invalid:8096",
        jellyfin_api_key="clave-ficticia",
    )
    client = JellyfinClient(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(JellyfinError) as exc:
        client.request_library_scan()
    assert "clave-prohibida" not in str(exc.value)
    assert "ubicacion-privada" not in str(exc.value)
    assert "No se pudo solicitar" in str(exc.value)


def test_failed_scan_can_be_retried_without_copy_again(lab):
    engine, root, source, download_id, provider = lab

    class OneFailure(SimulatedJellyfin):
        def request_library_scan(self):
            self.scan_requested += 1
            if self.scan_requested == 1:
                raise JellyfinError("Fallo simulado")

    jellyfin = OneFailure(root / "media")
    original = source.read_bytes()
    assert (
        run_one_sandbox_organization_with_jellyfin(
            engine,
            root,
            "w1",
            provider,
            expected_download_id=download_id,
            jellyfin=jellyfin,
        )
        == "publicada_escaneo_pendiente"
    )
    assert state(engine, download_id).organizacion_estado == "organizada"
    assert jellyfin.scan_requested == 1

    assert (
        request_scan_for_published_sandbox_download(
            engine,
            root,
            download_id,
            jellyfin,
        )
        == "escaneo_solicitado"
    )
    assert jellyfin.scan_requested == 2
    assert source.read_bytes() == original
    assert state(engine, download_id).organizacion_intentos == 1
    assert (root / "media" / "Peliculas" / "Corto ficticio (2026)").is_dir()


def test_collision_or_review_never_requests_scan(lab):
    engine, root, source, download_id, provider = lab
    jellyfin = SimulatedJellyfin(root / "media")
    (root / "media" / "Peliculas" / "Corto ficticio (2026)").mkdir()

    assert (
        run_one_sandbox_organization_with_jellyfin(
            engine,
            root,
            "w1",
            provider,
            expected_download_id=download_id,
            jellyfin=jellyfin,
        )
        == "requiere_revision"
    )
    assert jellyfin.scan_requested == 0
    assert state(engine, download_id).organizacion_estado == "requiere_revision"
    assert source.exists()


def test_bad_sandbox_or_database_does_not_claim_or_scan(lab):
    engine, root, source, download_id, provider = lab
    jellyfin = SimulatedJellyfin(root / "media")
    other = create_engine("sqlite://")
    try:
        with pytest.raises(UnsafeOrganizationPlan):
            run_one_sandbox_organization_with_jellyfin(
                other,
                root,
                "w1",
                provider,
                expected_download_id=download_id,
                jellyfin=jellyfin,
            )
        with pytest.raises(UnsafeOrganizationPlan):
            run_one_sandbox_organization_with_jellyfin(
                engine,
                root / "media",
                "w1",
                provider,
                expected_download_id=download_id,
                jellyfin=jellyfin,
            )
    finally:
        other.dispose()
    assert state(engine, download_id).organizacion_intentos == 0
    assert jellyfin.scan_requested == 0
    assert source.is_file()


def test_bad_id_or_unconfirmed_publish_cannot_request_scan(lab):
    engine, root, source, download_id, provider = lab
    jellyfin = SimulatedJellyfin(root / "media")
    for value in [True, 0, -1, "1"]:
        with pytest.raises(ValueError):
            request_scan_for_published_sandbox_download(
                engine,
                root,
                value,
                jellyfin,
            )
    with pytest.raises(UnsafeOrganizationPlan):
        request_scan_for_published_sandbox_download(
            engine,
            root,
            download_id,
            jellyfin,
        )
    assert jellyfin.scan_requested == 0


def test_two_eligible_downloads_publish_only_expected_id(lab):
    engine, root, source, download_id, provider = lab
    jellyfin = SimulatedJellyfin(root / "media")
    with Session(engine) as session:
        request = session.exec(select(Solicitud)).one()
        second = Descarga(
            solicitud_id=request.id,
            titulo="Otra descarga ficticia",
            estado="completada",
            progreso=1,
            estado_verificacion="verificada",
            verificada_en=datetime.now(UTC),
            organizacion_estado="pendiente",
            qbittorrent_hash="b" * 40,
        )
        session.add(second)
        session.commit()
        session.refresh(second)
        second_id = second.id

    assert (
        run_one_sandbox_organization_with_jellyfin(
            engine,
            root,
            "w1",
            provider,
            expected_download_id=download_id,
            jellyfin=jellyfin,
        )
        == "escaneo_solicitado"
    )
    assert jellyfin.scan_requested == 1
    assert state(engine, download_id).organizacion_estado == "organizada"
    assert state(engine, second_id).organizacion_estado == "pendiente"
    assert state(engine, second_id).organizacion_intentos == 0
    assert state(engine, second_id).organizacion_locked_by is None
    assert source.exists()


def test_lost_lease_after_publication_never_requests_scan(lab, monkeypatch):
    import worker.organization_runner_sandbox as runner

    engine, root, source, download_id, provider = lab
    jellyfin = SimulatedJellyfin(root / "media")

    def crash(*args, **kwargs):
        raise RuntimeError("fallo ficticio tras publicar")

    monkeypatch.setattr(runner, "confirm_organization", crash)
    with pytest.raises(RuntimeError, match="publicar"):
        run_one_sandbox_organization_with_jellyfin(
            engine,
            root,
            "w1",
            provider,
            expected_download_id=download_id,
            jellyfin=jellyfin,
        )
    assert jellyfin.scan_requested == 0
    assert state(engine, download_id).organizacion_estado == "pendiente"
