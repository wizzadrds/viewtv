"""Conservar la identidad de la carátula TMDB en solicitudes nuevas."""

import sqlalchemy as sa
from alembic import op

revision = "0014_identidad_tmdb_solicitud"
down_revision = "0013_cola_organizacion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Aditivo y nullable: solicitudes antiguas conservan título y año.
    op.add_column("solicitud", sa.Column("tmdb_id", sa.Integer(), nullable=True))
    op.create_index("ix_solicitud_tmdb_id", "solicitud", ["tmdb_id"])


def downgrade() -> None:
    # Nunca perder vínculos de carátula que ya estén en uso.
    connection = op.get_bind()
    active = connection.execute(
        sa.text("SELECT COUNT(*) FROM solicitud WHERE tmdb_id IS NOT NULL")
    ).scalar_one()
    if active:
        raise RuntimeError("No se puede revertir: hay solicitudes vinculadas a TMDB.")
    op.drop_index("ix_solicitud_tmdb_id", table_name="solicitud")
    op.drop_column("solicitud", "tmdb_id")
