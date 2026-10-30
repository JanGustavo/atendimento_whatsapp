"""Leitura por chat, presença recente e foto de perfil.

Revision ID: 0010_conversas_presenca_fotos
Revises: 0009_grupos_internos
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_conversas_presenca_fotos"
down_revision = "0009_grupos_internos"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("ultima_atividade_em", sa.DateTime(timezone=True)))
    op.add_column("usuarios", sa.Column("foto_chave", sa.String(40)))
    op.create_index("uq_usuarios_foto_chave", "usuarios", ["foto_chave"], unique=True)
    op.create_index("ix_usuarios_setor_interno_id", "usuarios", ["setor_interno_id"])
    op.create_table(
        "leituras_internas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("alvo_id", sa.Integer(), nullable=False),
        sa.Column("ultima_mensagem_id", sa.Integer(), nullable=False),
        sa.Column("lida_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("tipo IN ('direta','grupo')"),
    )
    op.create_index("uq_leitura_interna_usuario_tipo_alvo", "leituras_internas", ["usuario_id", "tipo", "alvo_id"], unique=True)
    op.create_index("ix_mensagens_internas_destinatario_id_id", "mensagens_internas", ["destinatario_id", "id"])
    op.create_index("ix_mensagens_internas_remetente_id_id", "mensagens_internas", ["remetente_id", "id"])
    op.create_index("ix_mensagens_grupo_setor_id_id", "mensagens_grupo", ["setor_id", "id"])


def downgrade():
    op.drop_index("ix_mensagens_grupo_setor_id_id", table_name="mensagens_grupo")
    op.drop_index("ix_mensagens_internas_remetente_id_id", table_name="mensagens_internas")
    op.drop_index("ix_mensagens_internas_destinatario_id_id", table_name="mensagens_internas")
    op.drop_table("leituras_internas")
    op.drop_index("ix_usuarios_setor_interno_id", table_name="usuarios")
    op.drop_index("uq_usuarios_foto_chave", table_name="usuarios")
    op.drop_column("usuarios", "foto_chave")
    op.drop_column("usuarios", "ultima_atividade_em")
