"""Papéis genéricos e leitura persistente.

Revision ID: 0008_papeis_leitura
Revises: 0007_simulador_toggle
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_papeis_leitura"
down_revision = "0007_simulador_toggle"
branch_labels = None
depends_on = None


def _recriar_usuarios(papeis: str, conversao: str):
    # O CHECK inicial do SQLite não tem nome. Recriar preserva IDs e todas as FKs.
    op.execute(f"""CREATE TABLE usuarios_novos (
        id INTEGER PRIMARY KEY, nome VARCHAR(120) NOT NULL, email VARCHAR(255) NOT NULL,
        senha_hash VARCHAR(255) NOT NULL, role VARCHAR(20) NOT NULL,
        ativo BOOLEAN NOT NULL, online BOOLEAN NOT NULL,
        ultima_atribuicao_em DATETIME, setor_interno_id INTEGER,
        CHECK (role IN ({papeis}))
    )""")
    op.execute(f"""INSERT INTO usuarios_novos
        (id,nome,email,senha_hash,role,ativo,online,ultima_atribuicao_em,setor_interno_id)
        SELECT id,nome,email,senha_hash,{conversao},ativo,online,ultima_atribuicao_em,setor_interno_id
        FROM usuarios""")
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_table("usuarios")
    op.rename_table("usuarios_novos", "usuarios")
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)


def upgrade():
    _recriar_usuarios("'colaborador','supervisor','gestor'",
                     "CASE role WHEN 'vendedor' THEN 'colaborador' WHEN 'responsavel' THEN 'supervisor' ELSE role END")
    op.add_column("mensagens", sa.Column("lida_em", sa.DateTime(timezone=True)))
    op.create_table("leituras_conversas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversa_id", sa.Integer(), sa.ForeignKey("conversas.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("ultima_mensagem_id", sa.Integer(), nullable=False),
        sa.Column("lida_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_leituras_conversas_conversa_id", "leituras_conversas", ["conversa_id"])
    op.create_index("ix_leituras_conversas_usuario_id", "leituras_conversas", ["usuario_id"])
    op.create_index("uq_leitura_conversa_usuario", "leituras_conversas", ["conversa_id", "usuario_id"], unique=True)


def downgrade():
    op.drop_table("leituras_conversas")
    op.drop_column("mensagens", "lida_em")
    _recriar_usuarios("'vendedor','responsavel','gestor'",
                     "CASE role WHEN 'colaborador' THEN 'vendedor' WHEN 'supervisor' THEN 'responsavel' ELSE role END")
