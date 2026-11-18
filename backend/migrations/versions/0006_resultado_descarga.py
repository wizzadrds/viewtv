"""Vincula cada descarga con el resultado de búsqueda seleccionado."""

import sqlalchemy as sa
from alembic import op


revision = "0006_resultado_descarga"
down_revision = "0005_resultados_busqueda"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # El cambio de columna y clave foránea se realiza mediante batch
    # para mantener la compatibilidad con SQLite.
    with op.batch_alter_table("descarga", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("resultado_busqueda_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_descarga_resultado_busqueda_id",
            "resultado_busqueda",
            ["resultado_busqueda_id"],
            ["id"],
        )

    op.create_index(
        "ix_descarga_resultado_busqueda_id",
        "descarga",
        ["resultado_busqueda_id"],
    )

    # Solo puede existir una descarga activa para cada info_hash.
    # Las descargas fallidas o completadas conservan su historial.
    op.drop_index("uq_descarga_info_hash", table_name="descarga")
    op.create_index(
        "uq_descarga_info_hash",
        "descarga",
        ["info_hash"],
        unique=True,
        sqlite_where=sa.text(
            "info_hash IS NOT NULL "
            "AND estado IN ('seleccionada', 'enviada', 'descargando', 'pausada')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_descarga_info_hash", table_name="descarga")
    op.drop_index(
        "ix_descarga_resultado_busqueda_id",
        table_name="descarga",
    )

    with op.batch_alter_table("descarga", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "fk_descarga_resultado_busqueda_id",
            type_="foreignkey",
        )
        batch_op.drop_column("resultado_busqueda_id")

    # Restaura la unicidad global original.
    # Puede fallar si existen hashes repetidos en el historial.
    op.create_index(
        "uq_descarga_info_hash",
        "descarga",
        ["info_hash"],
        unique=True,
        sqlite_where=sa.text("info_hash IS NOT NULL"),
    )
