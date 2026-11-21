"""El opt-in automático solo incluye nuevas selecciones explícitas."""
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models import Descarga, Perfil, ResultadoBusqueda, Solicitud
from worker.automatic_downloads import next_auto_download_id, parse_auto_floor


def make_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


def seed(session, *, estado="seleccionada", info_hash="auto"):
    if session.get(Perfil, 1) is None:
        session.add(Perfil(nombre="Test", pin_hash="dummy"))
        session.flush()
    req = Solicitud(perfil_id=1, titulo="Contenido autorizado de prueba", estado="completada")
    session.add(req)
    session.flush()
    result = ResultadoBusqueda(
        solicitud_id=req.id, clave=f"fixture-{req.id}", titulo="Archivo ficticio",
        indexador="ficticio", download_url="http://test.invalid/fixture",
    )
    session.add(result)
    session.flush()
    d = Descarga(
        solicitud_id=req.id, resultado_busqueda_id=result.id,
        titulo="Archivo ficticio",
        info_hash=(f"{req.id:040x}" if info_hash == "auto" else info_hash),
        estado=estado,
        qbittorrent_hash=("a" * 40 if estado != "seleccionada" else None),
    )
    session.add(d)
    session.commit()
    return d.id


@pytest.mark.parametrize("value,expected", [
    ("0", 0), ("1", 1), (" 7 ", 7),
    ("", None), ("-1", None), ("1.5", None),
    ("01", None), ("+2", None), ("abc", None),
    (str(2**63), None),
])
def test_parse_auto_floor(value, expected):
    assert parse_auto_floor(value) == expected


def test_auto_ignores_everything_before_opt_in():
    engine = make_engine()
    with Session(engine) as s:
        old = seed(s, estado="seleccionada")
        new = seed(s)
        assert next_auto_download_id(s, after_id=old) == new
        assert next_auto_download_id(s, after_id=new) is None


def test_auto_prioritizes_in_progress_and_never_skips_manual_pause():
    engine = make_engine()
    with Session(engine) as s:
        old = seed(s, estado="fallida")
        running = seed(s, estado="enviada")
        later = seed(s, estado="seleccionada")
        assert next_auto_download_id(s, after_id=old) == running
        s.get(Descarga, running).estado = "pausada"
        s.commit()
        assert next_auto_download_id(s, after_id=old) == running
        s.get(Descarga, running).estado = "completada"
        s.commit()
        assert next_auto_download_id(s, after_id=old) == later


def test_auto_ignores_invalid_or_unverified_selection():
    engine = make_engine()
    with Session(engine) as s:
        old = seed(s)
        invalid = seed(s, info_hash=None)
        valid = seed(s)
        assert next_auto_download_id(s, after_id=old) == valid
        assert next_auto_download_id(s, after_id=valid) is None
        assert invalid != valid


@pytest.mark.parametrize("floor", [-1, True, 3.5])
def test_auto_rejects_invalid_cutoff(floor):
    engine = make_engine()
    with Session(engine) as s:
        with pytest.raises(ValueError):
            next_auto_download_id(s, after_id=floor)
