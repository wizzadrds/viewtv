"""Permite solicitudes manuales sin identificador de Jellyfin."""

import sqlalchemy as sa
from alembic import op

revision = "0008_solicitud_jellyfin_nullable"
down_revision = "0007_leases_descarga"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("solicitud", recreate="always") as batch_op:
        batch_op.alter_column(
            "jellyfin_item_id",
            existing_type=sa.String(length=128),
            nullable=True,
        )


def downgrade() -> None:
    connection = op.get_bind()
    manuales = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM solicitud WHERE jellyfin_item_id IS NULL"
        )
    ).scalar_one()

    if manuales:
        raise RuntimeError(
            "No se puede revertir: existen solicitudes manuales sin Jellyfin ID."
        )

    with op.batch_alter_table("solicitud", recreate="always") as batch_op:
        batch_op.alter_column(
            "jellyfin_item_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )
