"""Pruebas del heartbeat de verificaciones."""

from threading import Event

import pytest
from worker import verification_heartbeat


def test_heartbeat_renews_lease(monkeypatch):
    renewed = Event()

    class FakeSession:
        def __init__(self, engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_renew(session, download_id, worker_id, **kwargs):
        renewed.set()
        return True

    monkeypatch.setattr(verification_heartbeat, "Session", FakeSession)
    monkeypatch.setattr(
        verification_heartbeat,
        "renew_verification_lease",
        fake_renew,
    )

    with verification_heartbeat.VerificationHeartbeat(
        object(), 1, "worker-a",
        lease_seconds=1, interval_seconds=0.01,
    ) as heartbeat:
        assert renewed.wait(timeout=1)

    assert not heartbeat.lease_lost
    assert not heartbeat._thread.is_alive()


def test_heartbeat_detects_lost_lease(monkeypatch):
    attempted = Event()

    class FakeSession:
        def __init__(self, engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_renew(session, download_id, worker_id, **kwargs):
        attempted.set()
        return False

    monkeypatch.setattr(verification_heartbeat, "Session", FakeSession)
    monkeypatch.setattr(
        verification_heartbeat,
        "renew_verification_lease",
        fake_renew,
    )

    with verification_heartbeat.VerificationHeartbeat(
        object(), 1, "worker-a",
        lease_seconds=1, interval_seconds=0.01,
    ) as heartbeat:
        assert attempted.wait(timeout=1)
        assert heartbeat._lost.wait(timeout=1)

    assert heartbeat.lease_lost
    assert not heartbeat._thread.is_alive()


def test_heartbeat_detects_database_error(monkeypatch):
    attempted = Event()

    class BrokenSession:
        def __init__(self, engine):
            pass

        def __enter__(self):
            attempted.set()
            raise RuntimeError("SQLite no disponible")

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(verification_heartbeat, "Session", BrokenSession)

    with verification_heartbeat.VerificationHeartbeat(
        object(), 1, "worker-a",
        lease_seconds=1, interval_seconds=0.01,
    ) as heartbeat:
        assert attempted.wait(timeout=1)
        assert heartbeat._lost.wait(timeout=1)

    assert heartbeat.lease_lost
    assert not heartbeat._thread.is_alive()


def test_heartbeat_rejects_invalid_intervals():
    with pytest.raises(ValueError):
        verification_heartbeat.VerificationHeartbeat(
            object(), 1, "worker-a",
            lease_seconds=1, interval_seconds=1,
        )

    with pytest.raises(ValueError):
        verification_heartbeat.VerificationHeartbeat(
            object(), 1, "worker-a",
            lease_seconds=0, interval_seconds=0.01,
        )
