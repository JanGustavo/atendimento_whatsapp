"""Tabelas iniciais do atendimento.

Revision ID: 0001_inicial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_inicial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("online", sa.Boolean(), nullable=False),
        sa.Column("ultima_atribuicao_em", sa.DateTime(timezone=True)),
        sa.CheckConstraint("role IN ('vendedor','responsavel','gestor')"),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)
    op.create_table("setores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(80), nullable=False, unique=True),
        sa.Column("ordem", sa.Integer(), nullable=False, unique=True),
        sa.Column("responsavel_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
    )
    op.create_table("conversas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero", sa.String(30), nullable=False),
        sa.Column("setor_id", sa.Integer(), sa.ForeignKey("setores.id")),
        sa.Column("atribuido_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("etapa", sa.String(20), nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("primeira_resposta_em", sa.DateTime(timezone=True)),
        sa.Column("timer_inicio_em", sa.DateTime(timezone=True)),
        sa.Column("timer_prazo_em", sa.DateTime(timezone=True)),
        sa.Column("timer_aviso_em", sa.DateTime(timezone=True)),
        sa.Column("timer_extensoes", sa.Integer(), nullable=False),
    )
    op.create_index("ix_conversas_numero", "conversas", ["numero"], unique=True)
    op.create_index("ix_conversas_atribuido_id", "conversas", ["atribuido_id"])
    op.create_table("mensagens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversa_id", sa.Integer(), sa.ForeignKey("conversas.id"), nullable=False),
        sa.Column("autor_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("origem", sa.String(20), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.String(255), unique=True),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_mensagens_conversa_id", "mensagens", ["conversa_id"])
    op.create_table("atribuicoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversa_id", sa.Integer(), sa.ForeignKey("conversas.id"), nullable=False),
        sa.Column("de_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("para_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("motivo", sa.String(80), nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_atribuicoes_conversa_id", "atribuicoes", ["conversa_id"])


def downgrade():
    op.drop_table("atribuicoes")
    op.drop_table("mensagens")
    op.drop_table("conversas")
    op.drop_table("setores")
    op.drop_table("usuarios")
