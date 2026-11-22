"""Historial de vistos por perfil y solicitudes de retirada sin borrado automático."""

import sqlalchemy as sa
from alembic import op

revision = "0015_gestion_espacio_vistas"
down_revision = "0014_identidad_tmdb_solicitud"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pelicula_vista",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("perfil_id", sa.Integer(), sa.ForeignKey("perfil.id"), nullable=False),
        sa.Column("medio_id", sa.Integer(), sa.ForeignKey("medio.id"), nullable=False),
        sa.Column("vista_en", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("perfil_id", "medio_id", name="uq_pelicula_vista_perfil_medio"),
    )
    op.create_index("ix_pelicula_vista_perfil_id", "pelicula_vista", ["perfil_id"])
    op.create_index("ix_pelicula_vista_medio_id", "pelicula_vista", ["medio_id"])

    op.create_table(
        "solicitud_retirada",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("perfil_id", sa.Integer(), sa.ForeignKey("perfil.id"), nullable=False),
        sa.Column("medio_id", sa.Integer(), sa.ForeignKey("medio.id"), nullable=False),
        sa.Column("estado", sa.String(24), nullable=False, server_default="pendiente_revision"),
        sa.Column("creada_en", sa.DateTime(), nullable=False),
        sa.Column("actualizada_en", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("perfil_id", "medio_id", name="uq_retirada_perfil_medio"),
        sa.CheckConstraint(
            "estado IN ('pendiente_revision', 'cancelada')",
            name="ck_retirada_estado",
        ),
    )
    op.create_index("ix_solicitud_retirada_perfil_id", "solicitud_retirada", ["perfil_id"])
    op.create_index("ix_solicitud_retirada_medio_id", "solicitud_retirada", ["medio_id"])


def downgrade() -> None:
    # No perder historial de visionado ni decisiones sin autorización.
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT COUNT(*) FROM pelicula_vista")).scalar_one():
        raise RuntimeError("Existen marcas de visionado; no se revierte automáticamente.")
    if conn.execute(sa.text("SELECT COUNT(*) FROM solicitud_retirada")).scalar_one():
        raise RuntimeError("Existen solicitudes de retirada; no se revierte automáticamente.")
    op.drop_index("ix_solicitud_retirada_medio_id", table_name="solicitud_retirada")
    op.drop_index("ix_solicitud_retirada_perfil_id", table_name="solicitud_retirada")
    op.drop_table("solicitud_retirada")
    op.drop_index("ix_pelicula_vista_medio_id", table_name="pelicula_vista")
    op.drop_index("ix_pelicula_vista_perfil_id", table_name="pelicula_vista")
    op.drop_table("pelicula_vista")
