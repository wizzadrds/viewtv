"""Añade metadatos de TMDB a los medios."""

from alembic import op
import sqlalchemy as sa


revision = "0003_metadatos_tmdb"
down_revision = "0002_medio_disponible_en_jellyfin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("medio") as batch_op:
        batch_op.add_column(sa.Column("tmdb_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("tmdb_sinopsis", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("tmdb_anio", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "tmdb_generos",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
        batch_op.add_column(
            sa.Column("tmdb_imagen_portada", sa.String(length=1000), nullable=True)
        )
        batch_op.add_column(
            sa.Column("tmdb_imagen_fondo", sa.String(length=1000), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "tmdb_estado",
                sa.String(length=20),
                nullable=False,
                server_default="pendiente",
            )
        )
        batch_op.add_column(
            sa.Column("tmdb_intentado_en", sa.DateTime(), nullable=True)
        )
        batch_op.create_index("ix_medio_tmdb_id", ["tmdb_id"])
        batch_op.create_index("ix_medio_tmdb_estado", ["tmdb_estado"])
        batch_op.create_check_constraint(
            "ck_medio_tmdb_estado",
            "tmdb_estado IN ('pendiente', 'asociado', 'revisar', "
            "'sin_resultado', 'error')",
        )


def downgrade() -> None:
    with op.batch_alter_table("medio") as batch_op:
        batch_op.drop_constraint("ck_medio_tmdb_estado", type_="check")
        batch_op.drop_index("ix_medio_tmdb_estado")
        batch_op.drop_index("ix_medio_tmdb_id")
        batch_op.drop_column("tmdb_intentado_en")
        batch_op.drop_column("tmdb_estado")
        batch_op.drop_column("tmdb_imagen_fondo")
        batch_op.drop_column("tmdb_imagen_portada")
        batch_op.drop_column("tmdb_generos")
        batch_op.drop_column("tmdb_anio")
        batch_op.drop_column("tmdb_sinopsis")
        batch_op.drop_column("tmdb_id")
