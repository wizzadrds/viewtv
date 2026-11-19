"""Persistencia del inicio controlado de torrents."""

import sqlalchemy as sa
from alembic import op

revision = "0012_inicio_torrent"
down_revision = "0011_reintentos_verificacion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "descarga",
        sa.Column(
            "inicio_estado",
            sa.String(length=20),
            nullable=False,
            server_default="no_requerido",
        ),
    )
    op.create_index(
        "ix_descarga_inicio_estado",
        "descarga",
        ["inicio_estado"],
    )
    op.add_column(
        "descarga",
        sa.Column("inicio_locked_by", sa.String(length=128)),
    )
    op.add_column(
        "descarga",
        sa.Column("inicio_locked_until", sa.DateTime()),
    )
    op.add_column(
        "descarga",
        sa.Column("inicio_disponible_desde", sa.DateTime()),
    )
    op.add_column(
        "descarga",
        sa.Column(
            "inicio_intentos",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    pending = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM descarga "
            "WHERE inicio_estado != 'no_requerido' "
            "OR inicio_locked_by IS NOT NULL "
            "OR inicio_locked_until IS NOT NULL "
            "OR inicio_disponible_desde IS NOT NULL "
            "OR inicio_intentos != 0"
        )
    ).scalar_one()

    if pending:
        raise RuntimeError(
            "No se puede revertir: existen operaciones "
            "de inicio de torrent registradas."
        )

    op.drop_column("descarga", "inicio_intentos")
    op.drop_column("descarga", "inicio_disponible_desde")
    op.drop_column("descarga", "inicio_locked_until")
    op.drop_column("descarga", "inicio_locked_by")
    op.drop_index(
        "ix_descarga_inicio_estado",
        table_name="descarga",
    )
    op.drop_column("descarga", "inicio_estado")
