"""Añade leases y reintentos al procesamiento de descargas."""

import sqlalchemy as sa
from alembic import op

revision = "0007_leases_descarga"
down_revision = "0006_resultado_descarga"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("descarga", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "intentos_envio",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "max_intentos_envio",
                sa.Integer(),
                nullable=False,
                server_default="5",
            )
        )
        batch_op.add_column(
            sa.Column(
                "disponible_desde",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.current_timestamp(),
            )
        )
        batch_op.add_column(
            sa.Column("locked_by", sa.String(length=128), nullable=True)
        )
        batch_op.add_column(
            sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("heartbeat", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_descarga_intentos_envio",
            "intentos_envio >= 0 AND max_intentos_envio > 0",
        )

    op.create_index(
        "ix_descarga_disponible_desde",
        "descarga",
        ["disponible_desde"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_descarga_disponible_desde",
        table_name="descarga",
    )

    with op.batch_alter_table("descarga", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "ck_descarga_intentos_envio",
            type_="check",
        )
        batch_op.drop_column("heartbeat")
        batch_op.drop_column("locked_until")
        batch_op.drop_column("locked_by")
        batch_op.drop_column("disponible_desde")
        batch_op.drop_column("max_intentos_envio")
        batch_op.drop_column("intentos_envio")
