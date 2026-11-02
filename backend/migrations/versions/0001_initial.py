"""Esquema inicial de perfiles, catálogo y cola durable."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "perfil",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(length=40), nullable=False),
        sa.Column("pin_hash", sa.String(length=255), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("nombre", name="uq_perfil_nombre"),
    )
    op.create_index("ix_perfil_nombre", "perfil", ["nombre"], unique=True)
    op.create_index("ix_perfil_activo", "perfil", ["activo"])

    op.create_table(
        "medio",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jellyfin_id", sa.String(length=128), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("titulo", sa.String(length=500), nullable=False),
        sa.Column("sinopsis", sa.String(), nullable=True),
        sa.Column("anio", sa.Integer(), nullable=True),
        sa.Column("imagen_portada", sa.String(length=1000), nullable=True),
        sa.Column("imagen_fondo", sa.String(length=1000), nullable=True),
        sa.Column("generos", sa.JSON(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("jellyfin_id", name="uq_medio_jellyfin_id"),
        sa.CheckConstraint("tipo IN ('pelicula', 'serie', 'temporada', 'episodio')", name="ck_medio_tipo"),
    )
    for column in ("jellyfin_id", "tipo", "titulo", "actualizado_en"):
        op.create_index(f"ix_medio_{column}", "medio", [column])

    op.create_table(
        "solicitud",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("perfil_id", sa.Integer(), nullable=False),
        sa.Column("jellyfin_item_id", sa.String(length=128), nullable=False),
        sa.Column("titulo", sa.String(length=500), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("prioridad", sa.Integer(), nullable=False),
        sa.Column("intentos", sa.Integer(), nullable=False),
        sa.Column("max_intentos", sa.Integer(), nullable=False),
        sa.Column("disponible_desde", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_error", sa.String(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["perfil_id"], ["perfil.id"]),
        sa.CheckConstraint("estado IN ('pendiente', 'procesando', 'completada', 'fallida', 'cancelada', 'vigilando')", name="ck_solicitud_estado"),
        sa.CheckConstraint("intentos >= 0 AND max_intentos > 0", name="ck_solicitud_intentos"),
        sa.CheckConstraint("prioridad BETWEEN 0 AND 100", name="ck_solicitud_prioridad"),
    )
    for column in ("perfil_id", "jellyfin_item_id", "estado", "prioridad", "disponible_desde", "locked_by", "locked_until", "creado_en"):
        op.create_index(f"ix_solicitud_{column}", "solicitud", [column])

def downgrade() -> None:
    op.drop_table("solicitud")
    op.drop_table("medio")
    op.drop_table("perfil")