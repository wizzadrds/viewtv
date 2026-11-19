"""Permiso de lectura 0013: jamás toca la base real ni ficheros multimedia."""

import sqlite3
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import Descarga, Perfil, Solicitud
from app.organization_publication_gate_sandbox import (
    check_sandbox_organization_lease as check,
)
from app.organization_queue import claim_next_organization


@pytest.fixture
def gate():
    # No tmp_path fixture: it may point outside /tmp or use a predictable name.
    root = Path("/tmp") / ("viewtv-lease-gate-" + uuid4().hex)
    root.mkdir(mode=0o700)
    (root / ".viewtv-lease-gate-sandbox-only").write_text(
        "VIEWTV_LEASE_GATE_SANDBOX_V1\n", encoding="utf-8"
    )
    db = root / "organization.sqlite3"
    engine = create_engine(f"sqlite:///{db}")
    SQLModel.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session:
        profile = Perfil(nombre="Persona ficticia", pin_hash="hash-ficticio")
        session.add(profile)
        session.flush()
        request = Solicitud(
            perfil_id=profile.id,
            titulo="Corto ficticio",
            tipo_medio="pelicula",
            estado="completada",
        )
        session.add(request)
        session.flush()
        download = Descarga(
            solicitud_id=request.id,
            titulo="Corto ficticio",
            estado="completada",
            progreso=1,
            estado_verificacion="verificada",
            verificada_en=now,
            qbittorrent_hash="a" * 40,
            organizacion_estado="pendiente",
        )
        session.add(download)
        session.commit()
        session.refresh(download)
        did = download.id
        assert claim_next_organization(session, "organizador-ficticio", now=now)
    yield engine, db, did, now
    engine.dispose()
    # Only remove our own verified, unique test root, never another user's files.
    if (
        root.parent == Path("/tmp")
        and root.name.startswith("viewtv-lease-gate-")
        and (root / ".viewtv-lease-gate-sandbox-only").read_text() ==
        "VIEWTV_LEASE_GATE_SANDBOX_V1\n"
    ):
        for name in ("organization.sqlite3", ".viewtv-lease-gate-sandbox-only"):
            (root / name).unlink(missing_ok=True)
        root.rmdir()


def decide(gate, **kwargs):
    _, db, did, now = gate
    args = dict(
        database=db,
        download_id=did,
        worker_id="organizador-ficticio",
        expected_attempt=1,
        expected_torrent_hash="a" * 40,
        now=now + timedelta(seconds=1),
    )
    args.update(kwargs)
    return check(**args)


def test_correct_lease_only_reads_the_database(gate):
    _, db, _, _ = gate
    before = sha256(db.read_bytes()).hexdigest()
    result = decide(gate)
    assert result.allowed and result.code == "lease_vigente_en_consulta"
    assert sha256(db.read_bytes()).hexdigest() == before


@pytest.mark.parametrize(
    "patch, reason",
    [
        ({"worker_id": "otro"}, "trabajo_o_identidad_no_vigente"),
        ({"expected_attempt": 2}, "trabajo_o_identidad_no_vigente"),
        ({"expected_torrent_hash": "b" * 40}, "trabajo_o_identidad_no_vigente"),
        ({"download_id": 999999}, "sin_trabajo"),
    ],
)
def test_identity_and_attempt_are_bound_to_claim(gate, patch, reason):
    result = decide(gate, **patch)
    assert not result.allowed and result.code == reason


def test_expiration_is_exclusive_and_never_renewed_by_read(gate):
    _, _, _, now = gate
    assert decide(gate, now=now + timedelta(seconds=179)).allowed
    for delta in (180, 181):
        result = decide(gate, now=now + timedelta(seconds=delta))
        assert not result.allowed and result.code == "lease_no_vigente"


def test_old_attempt_denied_even_if_same_worker_reclaims(gate):
    engine, _, did, now = gate
    with Session(engine) as session:
        claim = claim_next_organization(
            session, "organizador-ficticio", now=now + timedelta(seconds=181)
        )
        assert claim is not None and claim.id == did
        assert claim.organizacion_intentos == 2
    assert not decide(gate, now=now + timedelta(seconds=182)).allowed
    assert decide(
        gate, expected_attempt=2, now=now + timedelta(seconds=182)
    ).allowed


@pytest.mark.parametrize(
    "field,value",
    [
        ("estado", "descargando"),
        ("progreso", 0.9),
        ("estado_verificacion", "fallida"),
        ("verificada_en", None),
        ("organizacion_estado", "requiere_revision"),
        ("organizacion_locked_by", "otro"),
        ("qbittorrent_hash", "b" * 40),
        ("organizacion_intentos", 3),
    ],
)
def test_invalid_download_state_fails_closed(gate, field, value):
    engine, _, did, _ = gate
    with Session(engine) as session:
        row = session.get(Descarga, did)
        setattr(row, field, value)
        session.add(row)
        session.commit()
    assert not decide(gate).allowed


@pytest.mark.parametrize(
    "patch",
    [
        {"download_id": True},
        {"download_id": 0},
        {"worker_id": ""},
        {"worker_id": " "},
        {"expected_attempt": True},
        {"expected_attempt": 0},
        {"expected_attempt": 4},
        {"expected_torrent_hash": "a" * 39},
        {"expected_torrent_hash": "not-a-hash"},
        {"now": datetime.now()},
    ],
)
def test_invalid_arguments_never_grant_permission(gate, patch):
    assert not decide(gate, **patch).allowed


def test_missing_or_changed_marker_denied(gate):
    _, db, _, _ = gate
    marker = db.parent / ".viewtv-lease-gate-sandbox-only"
    try:
        marker.write_text("INVALIDO")
        assert not decide(gate).allowed
    finally:
        marker.write_text("VIEWTV_LEASE_GATE_SANDBOX_V1\n", encoding="utf-8")


def test_outside_root_and_database_symlink_denied(gate, tmp_path):
    _, db, _, _ = gate
    assert not decide(gate, database=tmp_path / "organization.sqlite3").allowed
    # El nombre aprobado debe seguir siendo organization.sqlite3, pero
    # nunca puede convertirse en un symlink hacia otra base.
    backing = db.parent / "backing.sqlite3"
    db.rename(backing)
    try:
        db.symlink_to(backing)
        assert not decide(gate).allowed
    finally:
        db.unlink()
        backing.rename(db)


def test_database_error_fails_closed(gate):
    _, db, _, _ = gate
    db.unlink()
    db.write_bytes(b"not a sqlite database")
    assert decide(gate).code == "fuente_no_verificable"


def test_unparseable_lease_fails_closed(gate):
    _, db, did, _ = gate
    with sqlite3.connect(db) as conn:
        conn.execute(
            "UPDATE descarga SET organizacion_locked_until = ? WHERE id = ?",
            ("fecha_invalida", did),
        )
    result = decide(gate)
    assert not result.allowed and result.code == "lease_no_vigente"
