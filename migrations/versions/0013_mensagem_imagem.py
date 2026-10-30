"""Imagem opcional na mensagem enviada ou recebida.

Revision ID: 0013_mensagem_imagem
Revises: 0012_foto_contato
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_mensagem_imagem"
down_revision = "0012_foto_contato"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("mensagens", sa.Column("imagem_chave", sa.String(40)))
    op.create_index("uq_mensagens_imagem_chave", "mensagens", ["imagem_chave"], unique=True)


def downgrade():
    op.drop_index("uq_mensagens_imagem_chave", table_name="mensagens")
    op.drop_column("mensagens", "imagem_chave")
