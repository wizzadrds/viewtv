"""Contrato del futuro publicador Windows: solo lectura, sin tocar medios reales."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlmodel import Session, SQLModel, create_engine
from worker.organization_planner import UnsafeOrganizationPlan
from worker.organization_windows_authority import (
    BROKER_ID,
    build_windows_publication_intent,
    claim_for_windows,
    publication_policy,
    verify_windows_publication_sources,
)

from app.models import Descarga, Perfil, Solicitud

HASH = "a" * 40


def test_publication_policy_fails_closed():
    assert publication_policy({}).mode == "disabled"
    assert publication_policy({"VIEWTV_WINDOWS_PUBLICATION_MODE": "disabled"}).mode == "disabled"
    with pytest.raises(ValueError):
        publication_policy({"VIEWTV_WINDOWS_PUBLICATION_MODE": "general",
                            "VIEWTV_WINDOWS_PUBLICATION_AFTER_ID": "1"})
    with pytest.raises(ValueError):
        publication_policy({"VIEWTV_WINDOWS_PUBLICATION_MODE": "single",
                            "VIEWTV_WINDOWS_PUBLICATION_AFTER_ID": "1",
                            "VIEWTV_WINDOWS_PUBLICATION_DOWNLOAD_ID": "1"})
    with pytest.raises(ValueError):
        publication_policy({"VIEWTV_WINDOWS_PUBLICATION_MODE": "single",
                            "VIEWTV_WINDOWS_PUBLICATION_AFTER_ID": "1",
                            "VIEWTV_WINDOWS_PUBLICATION_DOWNLOAD_ID": "-2"})
    assert publication_policy({
        "VIEWTV_WINDOWS_PUBLICATION_MODE": "single",
        "VIEWTV_WINDOWS_PUBLICATION_AFTER_ID": "1",
        "VIEWTV_WINDOWS_PUBLICATION_DOWNLOAD_ID": "3",
    }).allowed_id == 3
    assert publication_policy({
        "VIEWTV_WINDOWS_PUBLICATION_MODE": "general",
        "VIEWTV_WINDOWS_PUBLICATION_AFTER_ID": "1",
        "VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED": "true",
    }).after_id == 1


def test_claim_respects_single_id_and_general_floor(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'selection.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        profile = Perfil(nombre="Ficticio", pin_hash="solo-prueba")
        s.add(profile)
        s.flush()
        request = Solicitud(perfil_id=profile.id, titulo="Ficticia",
                            tipo_medio="pelicula", estado="completada")
        s.add(request)
        s.flush()
        for download_id in (1, 2, 3):
            s.add(Descarga(id=download_id, solicitud_id=request.id,
                           titulo=f"Vídeo {download_id}", estado="completada",
                           progreso=1, estado_verificacion="verificada",
                           organizacion_estado="pendiente", qbittorrent_hash=HASH))
        s.commit()
    single = publication_policy({
        "VIEWTV_WINDOWS_PUBLICATION_MODE": "single",
        "VIEWTV_WINDOWS_PUBLICATION_AFTER_ID": "1",
        "VIEWTV_WINDOWS_PUBLICATION_DOWNLOAD_ID": "3",
    })
    with Session(engine) as s:
        claimed = claim_for_windows(s, single)
        assert claimed is not None and claimed.id == 3
        assert claimed.organizacion_locked_by == BROKER_ID
    general = publication_policy({
        "VIEWTV_WINDOWS_PUBLICATION_MODE": "general",
        "VIEWTV_WINDOWS_PUBLICATION_AFTER_ID": "1",
        "VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED": "true",
    })
    with Session(engine) as s:
        claimed = claim_for_windows(s, general)
        assert claimed is not None and claimed.id == 2
        assert s.get(Descarga, 1).organizacion_intentos == 0
        assert s.get(Descarga, 3).organizacion_intentos == 1
    engine.dispose()


def example(tmp_path, *, expiry=None):
    media = tmp_path / "media"
    staging = media / "descargas_temporales"
    staging.mkdir(parents=True)
    (media / "Peliculas").mkdir()
    folder = staging / "Nadie 2 [Esp]"
    folder.mkdir()
    (folder / "Nadie 2 (2025).mkv").write_bytes(b"video")
    (folder / "Anuncio.url").write_bytes(b"url")
    download = Descarga(
        id=8, solicitud_id=12, titulo="Nadie 2", estado="completada",
        progreso=1, estado_verificacion="verificada", verificada_en=datetime.now(UTC),
        organizacion_estado="pendiente", organizacion_intentos=1,
        organizacion_locked_by=BROKER_ID,
        organizacion_locked_until=expiry or datetime.now(UTC) + timedelta(seconds=170),
        qbittorrent_hash=HASH,
    )
    request = Solicitud(id=12, perfil_id=1, titulo="Nadie 2", tipo_medio="pelicula")
    calls = []

    def info(*, hashes):
        calls.append("info")
        assert hashes == [HASH]
        return [{"hash": HASH, "tags": "viewtv-descarga-8", "state": "stoppedUP",
                 "save_path": r"C:\VIEWTV\media\descargas_temporales", "progress": 1.0,
                 "total_size": 8}]

    def files(torrent_hash):
        calls.append("files")
        assert torrent_hash == HASH
        return [
            {"name": "Nadie 2 [Esp]/Nadie 2 (2025).mkv", "size": 5, "progress": 1.0,
             "priority": 1},
            {"name": "Nadie 2 [Esp]/Anuncio.url", "size": 3, "progress": 1.0,
             "priority": 1},
        ]

    client = SimpleNamespace(torrents_info=info, torrent_files=files)
    return download, request, client, staging, media, calls


def test_intent_only_contains_verified_movie_without_url(tmp_path):
    download, request, client, staging, media, calls = example(tmp_path)
    intent = build_windows_publication_intent(
        download, request, client, staging_root=staging, media_root=media
    )
    assert intent["worker_id"] == BROKER_ID
    assert intent["attempt"] == 1
    assert intent["download_id"] == 8
    assert intent["files"] == [{
        "source_relative": "Nadie 2 [Esp]/Nadie 2 (2025).mkv",
        "destination_relative": "Peliculas/Nadie 2 (2025)/Nadie 2 (2025).mkv",
        "size_bytes": 5,
    }]
    assert calls == ["info", "files"]


def test_expired_lease_rejects_without_qbittorrent(tmp_path):
    download, request, client, staging, media, calls = example(
        tmp_path, expiry=datetime.now(UTC) - timedelta(seconds=1)
    )
    with pytest.raises(UnsafeOrganizationPlan):
        build_windows_publication_intent(
            download, request, client, staging_root=staging, media_root=media
        )
    assert calls == []


def test_reconciliation_sources_allow_existing_destination_but_no_lease_loss(tmp_path):
    download, request, client, staging, media, calls = example(tmp_path)
    target = media / "Peliculas" / "Nadie 2 (2025)"
    target.mkdir()
    (target / "Nadie 2 (2025).mkv").write_bytes(b"video")
    checked = verify_windows_publication_sources(
        download, client, staging_root=staging
    )
    assert checked == [
        {"source_relative": "Nadie 2 [Esp]/Nadie 2 (2025).mkv", "size_bytes": 5},
        {"source_relative": "Nadie 2 [Esp]/Anuncio.url", "size_bytes": 3},
    ]
    assert calls == ["info", "files"]
    with pytest.raises(UnsafeOrganizationPlan):
        build_windows_publication_intent(
            download, request, client, staging_root=staging, media_root=media
        )


def test_unowned_lease_rejects_without_qbittorrent(tmp_path):
    download, request, client, staging, media, calls = example(tmp_path)
    download.organizacion_locked_by = "otro-worker"
    with pytest.raises(UnsafeOrganizationPlan):
        build_windows_publication_intent(
            download, request, client, staging_root=staging, media_root=media
        )
    assert calls == []
