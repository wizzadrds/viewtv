"""Añade el estado de disponibilidad de los medios en Jellyfin."""

from alembic import op
import sqlalchemy as sa

revision = "0002_medio_disponible_en_jellyfin"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "medio",
        sa.Column(
            "disponible_en_jellyfin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.create_index(
        "ix_medio_disponible_en_jellyfin",
        "medio",
        ["disponible_en_jellyfin"],
    )


def downgrade() -> None:
    op.drop_index("ix_medio_disponible_en_jellyfin", table_name="medio")
    op.drop_column("medio", "disponible_en_jellyfin")
