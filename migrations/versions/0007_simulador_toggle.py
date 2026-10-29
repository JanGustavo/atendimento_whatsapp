"""Controle do simulador pelo gestor.

Revision ID: 0007_simulador_toggle
Revises: 0006_limites_bot
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_simulador_toggle"
down_revision = "0006_limites_bot"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "simulador_estado",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ativo", sa.Boolean(), nullable=False),
    )
    op.execute("INSERT INTO simulador_estado (id, ativo) VALUES (1, 0)")


def downgrade():
    op.drop_table("simulador_estado")
