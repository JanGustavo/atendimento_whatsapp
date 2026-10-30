"""Foto opcional de contato adicionada pela equipe.

Revision ID: 0012_foto_contato
Revises: 0011_nome_contato_whatsapp
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_foto_contato"
down_revision = "0011_nome_contato_whatsapp"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversas", sa.Column("foto_chave", sa.String(40)))


def downgrade():
    op.drop_column("conversas", "foto_chave")
