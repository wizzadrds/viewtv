"""Pruebas del ciclo principal del worker."""

import worker.main as worker_main


def test_monitor_error_does_not_stop_worker(monkeypatch):
    llamadas = []

    def process_download(worker_id):
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
