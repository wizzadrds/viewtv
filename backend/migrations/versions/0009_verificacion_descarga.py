"""Añade seguimiento independiente de verificación de descargas."""

import sqlalchemy as sa
from alembic import op

revision = "0009_verificacion_descarga"
down_revision = "0008_solicitud_jellyfin_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "descarga",
        sa.Column(
            "estado_verificacion",
            sa.String(length=20),
            nullable=False,
            server_default="pendiente",
        ),
    )
    op.add_column(
        "descarga",
        sa.Column(
            "verificada_en",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "descarga",
        sa.Column(
            "error_verificacion",
            sa.Text(),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_descarga_estado_verificacion",
        "descarga",
        ["estado_verificacion"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    registros = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM descarga "
            "WHERE estado_verificacion != 'pendiente' "
            "OR verificada_en IS NOT NULL "
            "OR error_verificacion IS NOT NULL"
        )
    ).scalar_one()

    if registros:
        raise RuntimeError(
            "No se puede revertir: existen datos de verificación."
        )

    op.drop_index(
        "ix_descarga_estado_verificacion",
        table_name="descarga",
    )
    op.drop_column("descarga", "error_verificacion")
    op.drop_column("descarga", "verificada_en")
    op.drop_column("descarga", "estado_verificacion")
