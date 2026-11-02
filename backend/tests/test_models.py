from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Medio, Perfil, Solicitud


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
