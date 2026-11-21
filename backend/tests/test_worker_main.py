"""Pruebas del ciclo principal del worker."""

import worker.main as worker_main


def test_monitor_error_does_not_stop_worker(monkeypatch):
    llamadas = []

    def process_download(worker_id, *, allowed_download_id, save_path):
        assert allowed_download_id == 7
        assert save_path == worker_main.STAGING_PATH
        llamadas.append("descarga")
        return False

    def process_request(worker_id):
        llamadas.append("solicitud")
        return False

    def failing_monitor():
        llamadas.append("monitor")
        raise RuntimeError("Fallo simulado")

    def report_status():
        llamadas.append("estado")

    def stop_after_one_cycle(seconds):
        llamadas.append("espera")
        raise KeyboardInterrupt

    monkeypatch.setattr(worker_main, "SUBMISSION_ENABLED", True)
    monkeypatch.setattr(worker_main, "SUBMISSION_TARGET_ID", 7)
    monkeypatch.setattr(worker_main, "process_one_download", process_download)
    monkeypatch.setattr(worker_main, "process_one_request", process_request)
    monkeypatch.setattr(worker_main, "monitor_downloads_once", failing_monitor)
    monkeypatch.setattr(worker_main, "report_worker_status", report_status)
    monkeypatch.setattr(worker_main.time, "sleep", stop_after_one_cycle)

    worker_main.main()

    assert llamadas == [
        "descarga",
        "solicitud",
        "monitor",
        "estado",
        "espera",
    ]


def test_submission_disabled_keeps_search_but_never_calls_qbittorrent(monkeypatch):
    """La selección no manda torrents reales en el modo de salida segura."""
    events = []

    def forbidden_submission(_worker_id):
        raise AssertionError("El worker intentó añadir un torrent sin permiso")

    def search(_worker_id):
        events.append("busqueda")
        return True

    def monitor():
        events.append("supervision")
        return 0

    def finish_cycle(_seconds):
        events.append("espera")
        raise KeyboardInterrupt

    monkeypatch.setattr(worker_main, "SUBMISSION_ENABLED", False)
    monkeypatch.setattr(worker_main, "START_ENABLED", False)
    monkeypatch.setattr(worker_main, "VERIFICATION_ENABLED", False)
    monkeypatch.setattr(worker_main, "process_one_download", forbidden_submission)
    monkeypatch.setattr(worker_main, "process_one_request", search)
    monkeypatch.setattr(worker_main, "monitor_downloads_once", monitor)
    monkeypatch.setattr(worker_main.time, "sleep", finish_cycle)

    worker_main.main()

    assert events == ["busqueda", "supervision", "espera"]



def test_automatic_worker_only_processes_new_selected_id(monkeypatch):
    """La ejecución real recibe UNA ID positiva y staging, nunca cola global."""
    from sqlmodel import Session
    from worker.automatic_downloads import next_auto_download_id
    from test_worker_automatic_downloads import make_engine, seed

    db = make_engine()
    with Session(db) as session:
        old = seed(session, estado="fallida")
        new = seed(session)
        assert next_auto_download_id(session, after_id=old) == new

    events = []
    monkeypatch.setattr(worker_main, "engine", db)
    monkeypatch.setattr(worker_main, "AUTO_DOWNLOAD_ENABLED", True)
    monkeypatch.setattr(worker_main, "AUTO_DOWNLOAD_AFTER_ID", old)
    monkeypatch.setattr(worker_main, "SUBMISSION_ENABLED", False)
    monkeypatch.setattr(worker_main, "START_ENABLED", False)
    monkeypatch.setattr(worker_main, "VERIFICATION_ENABLED", False)
    monkeypatch.setattr(worker_main.CatalogSyncScheduler, "run_if_due", lambda self: None)
    def fake_submission(worker_id, *, allowed_download_id, save_path, protect_unrelated=False):
        assert allowed_download_id == new
        assert save_path == worker_main.STAGING_PATH
        assert protect_unrelated is True
        events.append("envio")
        return True
    def fake_start(worker_id, *, allowed_download_id, expected_save_path):
        assert allowed_download_id == new
        assert expected_save_path == worker_main.STAGING_PATH
        events.append("inicio")
        return True
    monkeypatch.setattr(worker_main, "process_one_download", fake_submission)
    monkeypatch.setattr(worker_main, "process_one_start", fake_start)
    monkeypatch.setattr(worker_main, "process_one_request", lambda wid: events.append("buscar") or False)
    monkeypatch.setattr(worker_main, "monitor_downloads_once", lambda: events.append("supervisar") or 0)
    def stop(_seconds):
        raise KeyboardInterrupt()
    monkeypatch.setattr(worker_main.time, "sleep", stop)

    worker_main.main()

    assert events == ["envio", "inicio", "buscar", "supervisar"]


def test_automatic_worker_without_valid_cutoff_cannot_submit(monkeypatch):
    events = []
    monkeypatch.setattr(worker_main, "AUTO_DOWNLOAD_ENABLED", True)
    monkeypatch.setattr(worker_main, "AUTO_DOWNLOAD_AFTER_ID", None)
    monkeypatch.setattr(worker_main, "SUBMISSION_ENABLED", False)
    monkeypatch.setattr(worker_main, "START_ENABLED", False)
    monkeypatch.setattr(worker_main, "VERIFICATION_ENABLED", False)
    monkeypatch.setattr(worker_main.CatalogSyncScheduler, "run_if_due", lambda self: None)
    monkeypatch.setattr(worker_main, "process_one_download", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("no debe enviar torrents")))
    monkeypatch.setattr(worker_main, "process_one_start", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("no debe iniciar torrents")))
    monkeypatch.setattr(worker_main, "process_one_request", lambda wid: events.append("buscar") or True)
    monkeypatch.setattr(worker_main, "monitor_downloads_once", lambda: 0)
    monkeypatch.setattr(worker_main.time, "sleep", lambda _s: (_ for _ in ()).throw(KeyboardInterrupt()))
    worker_main.main()
    assert events == ["buscar"]
