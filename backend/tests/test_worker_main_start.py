"""Integración opcional del ejecutor de inicio en el worker."""

import pytest
import worker.main as worker_main


@pytest.mark.parametrize("enabled", [False, True])
def test_start_respects_feature_flag(monkeypatch, enabled):
    calls = []

    monkeypatch.setattr(worker_main, "START_ENABLED", enabled)
    monkeypatch.setattr(worker_main, "SUBMISSION_TARGET_ID", 7)
    monkeypatch.setattr(worker_main, "VERIFICATION_ENABLED", False)
    monkeypatch.setattr(
        worker_main,
        "process_one_download",
        lambda worker_id: False,
    )
    monkeypatch.setattr(
        worker_main,
        "process_one_request",
        lambda worker_id: False,
    )
    monkeypatch.setattr(
        worker_main,
        "monitor_downloads_once",
        lambda: 0,
    )
    monkeypatch.setattr(
        worker_main,
        "process_one_start",
        lambda worker_id, *, allowed_download_id, expected_save_path: (
            calls.append((worker_id, allowed_download_id, expected_save_path)) or True
        ),
    )
    monkeypatch.setattr(
        worker_main,
        "report_worker_status",
        lambda: None,
    )

    def finish_cycle(seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(worker_main.time, "sleep", finish_cycle)

    worker_main.main()

    assert len(calls) == int(enabled)
    if enabled:
        assert calls == [(worker_main.WORKER_ID, 7, worker_main.STAGING_PATH)]


def test_start_exception_does_not_stop_worker(monkeypatch):
    calls = []

    monkeypatch.setattr(worker_main, "START_ENABLED", True)
    monkeypatch.setattr(worker_main, "SUBMISSION_TARGET_ID", 7)
    monkeypatch.setattr(worker_main, "VERIFICATION_ENABLED", False)
    monkeypatch.setattr(
        worker_main,
        "process_one_download",
        lambda worker_id: False,
    )
    monkeypatch.setattr(
        worker_main,
        "process_one_request",
        lambda worker_id: False,
    )
    monkeypatch.setattr(
        worker_main,
        "monitor_downloads_once",
        lambda: 0,
    )
    monkeypatch.setattr(
        worker_main,
        "report_worker_status",
        lambda: calls.append("status"),
    )

    def failing_start(worker_id, *, allowed_download_id, expected_save_path):
        assert allowed_download_id == 7
        assert expected_save_path == worker_main.STAGING_PATH
        calls.append("start")
        raise RuntimeError("Fallo simulado")

    def finish_cycle(seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(worker_main, "process_one_start", failing_start)
    monkeypatch.setattr(worker_main.time, "sleep", finish_cycle)

    worker_main.main()

    assert calls == ["start", "status"]
