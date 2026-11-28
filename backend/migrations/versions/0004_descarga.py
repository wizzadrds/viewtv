"""Añade el seguimiento durable de descargas."""

import sqlalchemy as sa
from alembic import op

revision = "0004_descarga"
down_revision = "0003_metadatos_tmdb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "descarga",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("solicitud_id", sa.Integer(), nullable=False),
        sa.Column("info_hash", sa.String(length=128), nullable=True),
        sa.Column("titulo", sa.String(length=500), nullable=False),
        sa.Column("indexador", sa.String(length=128), nullable=True),
        sa.Column("qbittorrent_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default="seleccionada",
        ),
        sa.Column("progreso", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tamano_bytes", sa.Integer(), nullable=True),
        sa.Column("ultimo_error", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["solicitud_id"], ["solicitud.id"]),
        sa.CheckConstraint(
            "estado IN ('seleccionada', 'enviada', 'descargando', "
            "'pausada', 'completada', 'fallida')",
            name="ck_descarga_estado",
        ),
        sa.CheckConstraint(
            "progreso >= 0.0 AND progreso <= 1.0",
            name="ck_descarga_progreso",
        ),
        sa.CheckConstraint(
            "tamano_bytes IS NULL OR tamano_bytes >= 0",
            name="ck_descarga_tamano_bytes",
        ),
    )
    op.create_index(
        "ix_descarga_solicitud_id",
        "descarga",
        ["solicitud_id"],
    )
    op.create_index(
        "ix_descarga_estado",
        "descarga",
        ["estado"],
    )
    op.create_index(
        "uq_descarga_info_hash",
        "descarga",
        ["info_hash"],
        unique=True,
        sqlite_where=sa.text("info_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_descarga_info_hash", table_name="descarga")
    op.drop_index("ix_descarga_estado", table_name="descarga")
    op.drop_index("ix_descarga_solicitud_id", table_name="descarga")
    op.drop_table("descarga")

