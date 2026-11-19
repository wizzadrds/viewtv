"""Cola de organización de medios, durable y desactivada en el worker."""

import sqlalchemy as sa
from alembic import op

revision = "0013_cola_organizacion"
down_revision = "0012_inicio_torrent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "descarga",
        sa.Column(
            "organizacion_estado",
            sa.String(length=20),
            nullable=False,
            server_default="no_requerida",
        ),
    )
    op.create_index(
        "ix_descarga_organizacion_estado",
        "descarga",
        ["organizacion_estado"],
    )
    op.add_column(
        "descarga",
        sa.Column("organizacion_locked_by", sa.String(length=128)),
    )
    op.add_column(
        "descarga",
        sa.Column("organizacion_locked_until", sa.DateTime()),
    )
    op.add_column(
        "descarga",
        sa.Column("organizacion_disponible_desde", sa.DateTime()),
    )
    op.add_column(
        "descarga",
        sa.Column("organizacion_intentos", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "descarga",
        sa.Column("organizacion_ultimo_error", sa.Text()),
    )


def downgrade() -> None:
    connection = op.get_bind()
    pending = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM descarga "
            "WHERE organizacion_estado != 'no_requerida' "
            "OR organizacion_locked_by IS NOT NULL "
            "OR organizacion_locked_until IS NOT NULL "
            "OR organizacion_disponible_desde IS NOT NULL "
            "OR organizacion_intentos != 0 "
            "OR organizacion_ultimo_error IS NOT NULL"
        )
    ).scalar_one()
    if pending:
        raise RuntimeError(
            "No se puede revertir: existen trabajos o incidencias "
            "de organización persistidos."
        )

    op.drop_column("descarga", "organizacion_ultimo_error")
    op.drop_column("descarga", "organizacion_intentos")
    op.drop_column("descarga", "organizacion_disponible_desde")
    op.drop_column("descarga", "organizacion_locked_until")
    op.drop_column("descarga", "organizacion_locked_by")
    op.drop_index(
        "ix_descarga_organizacion_estado",
        table_name="descarga",
    )
    op.drop_column("descarga", "organizacion_estado")
