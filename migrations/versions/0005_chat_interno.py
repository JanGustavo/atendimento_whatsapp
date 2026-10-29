"""Setores e mensagens da comunicação interna.

Revision ID: 0005_chat_interno
Revises: 0004_chamados
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_chat_interno"
down_revision = "0004_chamados"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "setores_internos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(80), nullable=False, unique=True),
    )
    op.add_column("usuarios", sa.Column("setor_interno_id", sa.Integer()))
    op.create_table(
        "mensagens_internas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("remetente_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("destinatario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_mensagens_internas_remetente_id", "mensagens_internas", ["remetente_id"])
    op.create_index("ix_mensagens_internas_destinatario_id", "mensagens_internas", ["destinatario_id"])
    setores = sa.table("setores_internos", sa.column("id", sa.Integer), sa.column("nome", sa.String))
    op.bulk_insert(setores, [
        {"id": 1, "nome": "Vendas"}, {"id": 2, "nome": "Estoque"},
        {"id": 3, "nome": "Garantia"}, {"id": 4, "nome": "Administração"},
    ])
    op.execute("UPDATE usuarios SET setor_interno_id = CASE role WHEN 'vendedor' THEN 1 WHEN 'responsavel' THEN 3 ELSE 4 END")


def downgrade():
    op.drop_table("mensagens_internas")
    op.drop_column("usuarios", "setor_interno_id")
    op.drop_table("setores_internos")
