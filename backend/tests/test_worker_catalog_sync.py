"""Sincronización automática de Jellyfin: planificación y datos ficticios."""

from collections.abc import Iterator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from worker.catalog_sync import CatalogSyncScheduler

from app.jellyfin import JellyfinError, synchronize_catalog
from app.models import Medio


def test_catalog_sync_scheduled_every_30_minutes() -> None:
    now = [100.0]
    calls: list[str] = []

    def sync() -> int:
        calls.append("sincronizado")
        return 2

    scheduler = CatalogSyncScheduler(sync=sync, clock=lambda: now[0])
    assert scheduler.run_if_due() is None
    now[0] += 59
    assert scheduler.run_if_due() is None
    now[0] += 1
    assert scheduler.run_if_due() == 2
    assert scheduler.run_if_due() is None
    now[0] += 1799
    assert scheduler.run_if_due() is None
    now[0] += 1
    assert scheduler.run_if_due() == 2
    assert calls == ["sincronizado", "sincronizado"]


def test_catalog_sync_failure_retries_without_busy_loop() -> None:
    now = [0.0]
    calls = [0]

    def sync() -> int:
        calls[0] += 1
        if calls[0] == 1:
            raise JellyfinError("Jellyfin ficticio sin conexión")
        return 0

    scheduler = CatalogSyncScheduler(sync=sync, clock=lambda: now[0])
    now[0] = 60
    with pytest.raises(JellyfinError):
        scheduler.run_if_due()
    assert scheduler.run_if_due() is None
    now[0] = 359
    assert scheduler.run_if_due() is None
    now[0] = 360
    assert scheduler.run_if_due() == 0
    assert calls[0] == 2


@pytest.mark.parametrize("keyword", ["interval_seconds", "retry_seconds"])
def test_catalog_sync_rejects_nonpositive_intervals(keyword: str) -> None:
    with pytest.raises(ValueError):
        CatalogSyncScheduler(**{keyword: 0})


@pytest.fixture
def media_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_catalog_sync_reconciles_media_without_web_request(
    media_session: Session,
) -> None:
    class FakeJellyfin:
        def get_items(self, start_index: int, limit: int) -> dict:
            assert start_index == 0
            return {
                "Items": [{"Id": "new", "Type": "Movie", "Name": "Ficción nueva"}],
                "TotalRecordCount": 1,
            }

    media_session.add(Medio(jellyfin_id="old", titulo="Ficción antigua", tipo="pelicula"))
    media_session.commit()
    assert synchronize_catalog(media_session, client=FakeJellyfin()) == 1
    elements = media_session.exec(select(Medio)).all()
    available = [m for m in elements if m.disponible_en_jellyfin]
    assert [m.jellyfin_id for m in available] == ["new"]
    assert len(elements) == 2


def test_catalog_sync_rolls_back_if_jellyfin_fails_on_next_page(
    media_session: Session,
) -> None:
    class BrokenJellyfin:
        def get_items(self, start_index: int, limit: int) -> dict:
            if start_index == 0:
                return {
                    "Items": [
                        {"Id": f"new-{n}", "Type": "Movie", "Name": "Prueba"} for n in range(limit)
                    ],
                    "TotalRecordCount": limit + 1,
                }
            raise JellyfinError("Fallo de página ficticio")

    media_session.add(Medio(jellyfin_id="old", titulo="Antiguo", tipo="pelicula"))
    media_session.commit()
    with pytest.raises(JellyfinError):
        synchronize_catalog(media_session, client=BrokenJellyfin())
    elements = media_session.exec(select(Medio)).all()
    assert len(elements) == 1
    assert elements[0].jellyfin_id == "old"
    assert elements[0].disponible_en_jellyfin is True
