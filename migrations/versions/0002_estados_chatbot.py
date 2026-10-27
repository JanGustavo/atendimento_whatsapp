"""Normaliza estados criados no M1.

Revision ID: 0002_estados_chatbot
Revises: 0001_inicial
"""
from alembic import op

revision = "0002_estados_chatbot"
down_revision = "0001_inicial"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE conversas SET etapa='menu_setor' WHERE etapa='setor'")
    op.execute("UPDATE conversas SET etapa='atribuida' WHERE etapa='humano'")


def downgrade():
    op.execute("UPDATE conversas SET etapa='setor' WHERE etapa='menu_setor'")
    op.execute("UPDATE conversas SET etapa='humano' WHERE etapa='atribuida'")
