"""Entrega 0013: el organizador solo reclama la ID autorizada.

SQLite ficticia aislada. Sin publicación real, qBittorrent ni credenciales.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import Descarga, Perfil, Solicitud
from app.organization_queue import (
    LEASE_SECONDS,
    claim_next_organization,
    confirm_organization,
)


@pytest.fixture
def two_downloads(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'org-single.sqlite'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        profile = Perfil(nombre="Perfil simulado", pin_hash="clave-inexistente")
        s.add(profile)
        s.flush()
        req = Solicitud(
            perfil_id=profile.id,
            titulo="Corto sintético",
            tipo_medio="pelicula",
            estado="completada",
        )
        s.add(req)
        s.flush()
        ids = []
        for title, digit in (("Primero", "a"), ("Segundo", "b")):
            row = Descarga(
                solicitud_id=req.id,
                titulo=title,
                estado="completada",
                progreso=1,
                estado_verificacion="verificada",
                qbittorrent_hash=digit * 40,
                organizacion_estado="pendiente",
            )
            s.add(row)
            s.flush()
            ids.append(row.id)
        s.commit()
    yield engine, ids
    engine.dispose()


def row(engine, download_id):
    with Session(engine) as s:
        return s.get(Descarga, download_id)


def test_first_eligible_is_not_claimed_if_second_is_authorized(two_downloads):
    engine, (first, second) = two_downloads
    with Session(engine) as s:
        claimed = claim_next_organization(s, "organizador-identificado", allowed_download_id=second)
        assert claimed is not None
        assert claimed.id == second
        assert claimed.organizacion_intentos == 1
    earlier = row(engine, first)
    assert earlier.organizacion_estado == "pendiente"
    assert earlier.organizacion_intentos == 0
    assert earlier.organizacion_locked_by is None
    with Session(engine) as s:
        assert confirm_organization(s, second, "organizador-identificado")
    assert row(engine, second).organizacion_estado == "organizada"
    assert row(engine, first).organizacion_estado == "pendiente"


def test_missing_id_does_not_claim_another_download(two_downloads):
    engine, (first, second) = two_downloads
    with Session(engine) as s:
        assert claim_next_organization(s, "organizador", allowed_download_id=second + 9999) is None
    for did in (first, second):
        assert row(engine, did).organizacion_intentos == 0
        assert row(engine, did).organizacion_locked_by is None


@pytest.mark.parametrize("invalid", [True, False, 0, -1, "1", 1.5, 2**63])
def test_invalid_id_does_not_write_sqlite(two_downloads, invalid):
    engine, (first, second) = two_downloads
    with Session(engine) as s, pytest.raises(ValueError):
        claim_next_organization(s, "organizador", allowed_download_id=invalid)
    assert row(engine, first).organizacion_intentos == 0
    assert row(engine, second).organizacion_intentos == 0


def test_two_workers_competing_for_same_id_can_claim_once(two_downloads):
    engine, (first, second) = two_downloads
    now = datetime.now(UTC)
    with Session(engine) as s:
        assert claim_next_organization(s, "w1", now=now, allowed_download_id=second)
    with Session(engine) as s:
        assert claim_next_organization(s, "w2", now=now, allowed_download_id=second) is None
    assert row(engine, first).organizacion_locked_by is None
    assert row(engine, second).organizacion_locked_by == "w1"


def test_expired_target_reclaims_only_target_not_earlier_entry(two_downloads):
    engine, (first, second) = two_downloads
    now = datetime.now(UTC)
    with Session(engine) as s:
        assert claim_next_organization(s, "viejo", now=now, allowed_download_id=second)
    later = now + timedelta(seconds=LEASE_SECONDS + 1)
    with Session(engine) as s:
        claimed = claim_next_organization(s, "nuevo", now=later, allowed_download_id=second)
        assert claimed is not None
        assert claimed.organizacion_intentos == 2
    assert row(engine, first).organizacion_intentos == 0
    assert row(engine, second).organizacion_locked_by == "nuevo"


def test_legacy_unfiltered_claim_remains_compatible_but_not_used_by_bridge(
    two_downloads,
):
    engine, (first, second) = two_downloads
    with Session(engine) as s:
        claim = claim_next_organization(s, "legacy-test")
        assert claim is not None and claim.id == first
    assert row(engine, second).organizacion_intentos == 0
