
"""Añade resultados de búsqueda persistentes y estados de selección."""

import sqlalchemy as sa
from alembic import op

revision = "0005_resultados_busqueda"
down_revision = "0004_descarga"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite necesita reconstruir la tabla para modificar sus restricciones.
    with op.batch_alter_table("solicitud", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_solicitud_estado", type_="check")
        batch_op.add_column(
            sa.Column("tipo_medio", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("anio", sa.Integer(), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_solicitud_estado",
            "estado IN ('pendiente', 'procesando', 'completada', "
            "'fallida', 'cancelada', 'vigilando', "
            "'esperando_seleccion', 'sin_resultados')",
        )
        batch_op.create_check_constraint(
            "ck_solicitud_tipo_medio",
            "tipo_medio IS NULL OR tipo_medio IN "
            "('pelicula', 'serie', 'temporada', 'episodio')",
        )

    op.create_table(
        "resultado_busqueda",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("solicitud_id", sa.Integer(), nullable=False),
        sa.Column("clave", sa.String(length=64), nullable=False),
        sa.Column("info_hash", sa.String(length=128), nullable=True),
        sa.Column("titulo", sa.String(length=500), nullable=False),
        sa.Column("indexador", sa.String(length=128), nullable=False),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.Column("magnet_url", sa.Text(), nullable=True),
        sa.Column("seeders", sa.Integer(), nullable=True),
        sa.Column("peers", sa.Integer(), nullable=True),
        sa.Column("tamano_bytes", sa.Integer(), nullable=True),
        sa.Column("categorias", sa.JSON(), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["solicitud_id"], ["solicitud.id"]),
        sa.UniqueConstraint(
            "solicitud_id",
            "clave",
            name="uq_resultado_solicitud_clave",
        ),
        sa.CheckConstraint(
            "tamano_bytes IS NULL OR tamano_bytes >= 0",
            name="ck_resultado_tamano_bytes",
        ),
        sa.CheckConstraint(
            "(download_url IS NOT NULL AND length(trim(download_url)) > 0) "
            "OR (magnet_url IS NOT NULL AND length(trim(magnet_url)) > 0)",
            name="ck_resultado_url",
        ),
    )

    op.create_index(
        "ix_resultado_busqueda_solicitud_id",
        "resultado_busqueda",
        ["solicitud_id"],
    )
    op.create_index(
        "ix_resultado_busqueda_info_hash",
        "resultado_busqueda",
        ["info_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_resultado_busqueda_info_hash",
        table_name="resultado_busqueda",
    )
    op.drop_index(
        "ix_resultado_busqueda_solicitud_id",
        table_name="resultado_busqueda",
    )
    op.drop_table("resultado_busqueda")

    with op.batch_alter_table("solicitud", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_solicitud_tipo_medio", type_="check")
        batch_op.drop_constraint("ck_solicitud_estado", type_="check")
        batch_op.drop_column("anio")
        batch_op.drop_column("tipo_medio")
        batch_op.create_check_constraint(
            "ck_solicitud_estado",
            "estado IN ('pendiente', 'procesando', 'completada', "
            "'fallida', 'cancelada', 'vigilando')",
        )
