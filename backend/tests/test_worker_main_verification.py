"""Integración de la verificación en el ciclo del worker."""

import importlib

import pytest


@pytest.fixture
def worker_cycle(monkeypatch):
    module = importlib.import_module("worker.main")

    calls = {
        "download": 0,
        "request": 0,
        "monitor": 0,
        "verify": 0,
        "report": 0,
    }

    def download(_worker_id):
        calls["download"] += 1
        return False

    def request(_worker_id):
        calls["request"] += 1
        return False

    def monitor():
        calls["monitor"] += 1
        return 0

    def report():
        calls["report"] += 1

    def verify(_worker_id):
        calls["verify"] += 1
        return True

    def stop_after_cycle(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(module, "process_one_download", download)
    monkeypatch.setattr(module, "process_one_request", request)
    monkeypatch.setattr(module, "monitor_downloads_once", monitor)
    monkeypatch.setattr(module, "report_worker_status", report)
    monkeypatch.setattr(module, "process_one_verification", verify)
    monkeypatch.setattr(module.time, "sleep", stop_after_cycle)

    return module, calls


def test_verification_disabled(worker_cycle, monkeypatch):
    module, calls = worker_cycle
    monkeypatch.setattr(module, "VERIFICATION_ENABLED", False)

    module.main()

    assert calls == {
        "download": 1,
        "request": 1,
        "monitor": 1,
        "verify": 0,
        "report": 1,
    }


def test_successful_verification_counts_as_activity(
    worker_cycle, monkeypatch
):
    module, calls = worker_cycle
    monkeypatch.setattr(module, "VERIFICATION_ENABLED", True)

    module.main()

    assert calls["verify"] == 1
    assert calls["report"] == 0
    assert calls["download"] == 1
    assert calls["request"] == 1


def test_no_verification_reports_idle(worker_cycle, monkeypatch):
    module, calls = worker_cycle
    monkeypatch.setattr(module, "VERIFICATION_ENABLED", True)

    def no_work(_worker_id):
        calls["verify"] += 1
        return False

    monkeypatch.setattr(module, "process_one_verification", no_work)

    module.main()

    assert calls["verify"] == 1
    assert calls["report"] == 1


def test_verification_error_does_not_interrupt_cycle(
    worker_cycle, monkeypatch, caplog
):
    module, calls = worker_cycle
    monkeypatch.setattr(module, "VERIFICATION_ENABLED", True)

    def failing_verify(_worker_id):
        calls["verify"] += 1
        raise RuntimeError("Error simulado")

    monkeypatch.setattr(
        module, "process_one_verification", failing_verify
    )

    module.main()

    assert calls["download"] == 1
    assert calls["request"] == 1
    assert calls["monitor"] == 1
    assert calls["verify"] == 1
    assert calls["report"] == 1
    assert "Error procesando verificación" in caplog.text
