"""Añade reclamaciones independientes para verificar descargas."""

import sqlalchemy as sa
from alembic import op

revision = "0010_leases_verificacion_descarga"
down_revision = "0009_verificacion_descarga"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "descarga",
        sa.Column(
            "verificacion_locked_by",
            sa.String(length=128),
            nullable=True,
        ),
    )
    op.add_column(
        "descarga",
        sa.Column(
            "verificacion_locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "descarga",
        sa.Column(
            "verificacion_heartbeat",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "descarga",
        sa.Column(
            "verificacion_disponible_desde",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    activos = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM descarga WHERE "
            "verificacion_locked_by IS NOT NULL OR "
            "verificacion_locked_until IS NOT NULL OR "
            "verificacion_heartbeat IS NOT NULL OR "
            "verificacion_disponible_desde IS NOT NULL"
        )
    ).scalar_one()

    if activos:
        raise RuntimeError(
            "No se puede revertir: existen datos de reclamación "
            "o programación de verificaciones."
        )

    op.drop_column("descarga", "verificacion_disponible_desde")
    op.drop_column("descarga", "verificacion_heartbeat")
    op.drop_column("descarga", "verificacion_locked_until")
    op.drop_column("descarga", "verificacion_locked_by")
