"""Mensagens dos grupos dinâmicos por setor interno.

Revision ID: 0009_grupos_internos
Revises: 0008_papeis_leitura
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_grupos_internos"
down_revision = "0008_papeis_leitura"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("mensagens_internas", sa.Column("imagem_chave", sa.String(40)))
    op.create_index("uq_mensagens_internas_imagem_chave", "mensagens_internas", ["imagem_chave"], unique=True)
    op.create_table(
        "mensagens_grupo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("setor_id", sa.Integer(), sa.ForeignKey("setores_internos.id"), nullable=False),
        sa.Column("remetente_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("imagem_chave", sa.String(40), unique=True),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_mensagens_grupo_setor_id", "mensagens_grupo", ["setor_id"])
    op.create_index("ix_mensagens_grupo_remetente_id", "mensagens_grupo", ["remetente_id"])


def downgrade():
    op.drop_table("mensagens_grupo")
    op.drop_index("uq_mensagens_internas_imagem_chave", table_name="mensagens_internas")
    op.drop_column("mensagens_internas", "imagem_chave")
