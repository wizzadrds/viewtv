"""Evita interpretar un inicio pendiente como pausa manual."""

import worker.download_monitor as monitor
from sqlmodel import Session, SQLModel, create_engine

from app.models import Descarga, Perfil, Solicitud


class ForbiddenQBittorrent:
    def torrents_info(self, *args, **kwargs):
        raise AssertionError(
            "No debe consultarse un inicio todavía pendiente."
        )


def test_monitor_ignores_download_waiting_for_first_start(
    tmp_path, monkeypatch
):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'monitor-start.sqlite3'}"
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(monitor, "engine", engine)

    with Session(engine) as session:
        profile = Perfil(
            nombre="Inicio pendiente",
            pin_hash="hash-de-prueba",
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)

        request = Solicitud(
            perfil_id=profile.id,
            titulo="Prueba de inicio",
            tipo_medio="pelicula",
            estado="completada",
        )
        session.add(request)
        session.commit()
        session.refresh(request)

        download = Descarga(
            solicitud_id=request.id,
            titulo="Prueba de inicio",
            estado="enviada",
            qbittorrent_hash="a" * 40,
            inicio_estado="pendiente",
        )
        session.add(download)
        session.commit()
        session.refresh(download)
        download_id = download.id

    updated = monitor.monitor_downloads_once(
        client=ForbiddenQBittorrent()
    )

    assert updated == 0

    with Session(engine) as session:
        download = session.get(Descarga, download_id)
        assert download.estado == "enviada"
        assert download.inicio_estado == "pendiente"

    engine.dispose()
