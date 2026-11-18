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

    monkeypatch.setattr(
        worker_main, "process_one_download", process_download
    )
    monkeypatch.setattr(
        worker_main, "process_one_request", process_request
    )
    monkeypatch.setattr(
        worker_main, "monitor_downloads_once", failing_monitor
    )
    monkeypatch.setattr(
        worker_main, "report_worker_status", report_status
    )
    monkeypatch.setattr(
        worker_main.time, "sleep", stop_after_one_cycle
    )

    worker_main.main()

    assert llamadas == [
        "descarga",
        "solicitud",
        "monitor",
        "estado",
        "espera",
    ]
