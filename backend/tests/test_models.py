import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Descarga, Medio, Perfil, Solicitud


def make_session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_catalog_metadata_and_request_persist_independently():
    with make_session() as session:
        perfil = Perfil(nombre="Adultos", pin_hash="hash-de-prueba")
        session.add(perfil)
        session.commit()
        session.refresh(perfil)

        medio = Medio(jellyfin_id="jf-123", tipo="pelicula", titulo="Película de prueba")
        session.add(medio)
        session.commit()

        solicitud = Solicitud(
            perfil_id=perfil.id,
            jellyfin_item_id=medio.jellyfin_id,
            titulo=medio.titulo,
        )
        session.add(solicitud)
        session.commit()

        assert session.exec(select(Medio)).one().jellyfin_id == "jf-123"
        saved_request = session.exec(select(Solicitud)).one()
        assert saved_request.estado == "pendiente"
        assert saved_request.locked_until is None
        assert saved_request.heartbeat is None


def test_request_has_lease_fields():
    with make_session() as session:
        perfil = Perfil(nombre="Infantil", pin_hash="hash-de-prueba")
        session.add(perfil)
        session.commit()
        session.refresh(perfil)

        solicitud = Solicitud(
            perfil_id=perfil.id,
            jellyfin_item_id="jf-456",
            titulo="Otra prueba",
            estado="procesando",
            locked_by="worker-1",
        )
        session.add(solicitud)
        session.commit()
        session.refresh(solicitud)

        assert solicitud.locked_by == "worker-1"
        assert solicitud.locked_until is None


def make_request(session):
    perfil = Perfil(nombre="Pruebas", pin_hash="hash-de-prueba")
    session.add(perfil)
    session.commit()
    session.refresh(perfil)

    solicitud = Solicitud(
        perfil_id=perfil.id,
        jellyfin_item_id="jf-descarga",
        titulo="Vídeo de prueba",
    )
    session.add(solicitud)
    session.commit()
    session.refresh(solicitud)
    return solicitud


def test_download_persists_with_defaults_and_request_relation():
    with make_session() as session:
        solicitud = make_request(session)
        descarga = Descarga(
            solicitud_id=solicitud.id,
            titulo="Resultado de prueba",
            info_hash="a" * 40,
            indexador="indexador-autorizado",
        )
        session.add(descarga)
        session.commit()
        session.refresh(descarga)

        assert descarga.estado == "seleccionada"
        assert descarga.progreso == 0.0
        assert descarga.solicitud_id == solicitud.id
        assert descarga.qbittorrent_hash is None
        assert descarga.creado_en is not None
        assert descarga.actualizado_en is not None


def test_download_allows_multiple_null_hashes():
    with make_session() as session:
        solicitud = make_request(session)
        session.add_all(
            [
                Descarga(solicitud_id=solicitud.id, titulo="Resultado 1"),
                Descarga(solicitud_id=solicitud.id, titulo="Resultado 2"),
            ]
        )
        session.commit()

        assert len(session.exec(select(Descarga)).all()) == 2


def test_download_rejects_duplicate_info_hash():
    with make_session() as session:
        solicitud = make_request(session)
        session.add(
            Descarga(
                solicitud_id=solicitud.id,
                titulo="Primera",
                info_hash="b" * 40,
            )
        )
        session.commit()

        session.add(
            Descarga(
                solicitud_id=solicitud.id,
                titulo="Duplicada",
                info_hash="b" * 40,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    "estado",
    ["desconocido", "queued", "cancelada"],
)
def test_download_rejects_invalid_state(estado):
    with make_session() as session:
        solicitud = make_request(session)
        session.add(
            Descarga(
                solicitud_id=solicitud.id,
                titulo="Estado inválido",
                estado=estado,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize("progreso", [-0.01, 1.01])
def test_download_rejects_progress_out_of_range(progreso):
    with make_session() as session:
        solicitud = make_request(session)
        session.add(
            Descarga(
                solicitud_id=solicitud.id,
                titulo="Progreso inválido",
                progreso=progreso,
            )
        )
        with pytest.raises((IntegrityError, ValueError)):
            session.commit()

def test_download_has_retry_and_lease_defaults():
    with make_session() as session:
        solicitud = make_request(session)
        descarga = Descarga(
            solicitud_id=solicitud.id,
            titulo="Descarga con lease",
        )
        session.add(descarga)
        session.commit()
        session.refresh(descarga)

        assert descarga.intentos_envio == 0
        assert descarga.max_intentos_envio == 5
        assert descarga.disponible_desde is not None
        assert descarga.locked_by is None
        assert descarga.locked_until is None
        assert descarga.heartbeat is None


@pytest.mark.parametrize(
    ("intentos", "max_intentos"),
    [(-1, 5), (0, 0), (1, -1)],
)
def test_download_rejects_invalid_retry_limits(intentos, max_intentos):
    with make_session() as session:
        solicitud = make_request(session)
        session.add(
            Descarga(
                solicitud_id=solicitud.id,
                titulo="Reintentos inválidos",
                intentos_envio=intentos,
                max_intentos_envio=max_intentos,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
