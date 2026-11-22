"""La publicación automática continúa disponible tras las migraciones aditivas."""
import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine
from worker import organization_windows_cli as cli


@pytest.mark.parametrize("revision", [
    "0013_cola_organizacion",
    "0014_identidad_tmdb_solicitud",
    "0015_gestion_espacio_vistas",
])
def test_publicador_acepta_solo_revisiones_compatibles(monkeypatch, revision):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num TEXT)"))
        connection.execute(
            text("INSERT INTO alembic_version VALUES (:rev)"),
            {"rev": revision},
        )
    monkeypatch.setattr(cli, "engine", engine)
    cli._schema_0013()
    with engine.connect() as connection:
        actual = connection.execute(
            text("SELECT version_num FROM alembic_version"),
        ).scalar_one()
    assert actual == revision
    engine.dispose()


def test_revision_desconocida_bloquea_publicacion(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num TEXT)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('0016_desconocida')"))
    monkeypatch.setattr(cli, "engine", engine)
    with pytest.raises(ValueError, match="revisión"):
        cli._schema_0013()
    engine.dispose()


def test_tabla_incompleta_bloquea_sin_reparacion(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num TEXT)"))
        connection.execute(
            text("INSERT INTO alembic_version VALUES ('0015_gestion_espacio_vistas')"),
        )
        connection.execute(text("CREATE TABLE descarga (id INTEGER PRIMARY KEY)"))
    monkeypatch.setattr(cli, "engine", engine)
    with pytest.raises(ValueError, match="contrato"):
        cli._schema_0013()
    engine.dispose()
