"""Añade contador persistente de errores temporales de verificación."""

import sqlalchemy as sa
from alembic import op

revision = "0011_reintentos_verificacion"
down_revision = "0010_leases_verificacion_descarga"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "descarga",
        sa.Column(
            "verificacion_intentos_temporales",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    registros = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM descarga "
            "WHERE verificacion_intentos_temporales != 0"
        )
    ).scalar_one()

    if registros:
        raise RuntimeError(
            "No se puede revertir: existen contadores "
            "de reintentos temporales."
        )

    op.drop_column(
        "descarga",
        "verificacion_intentos_temporales",
    )
