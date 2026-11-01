"""Áudio enviado em mensagens do atendimento.

Revision ID: 0018_audio_mensagens
Revises: 0017_arquivamento_conversas
"""

import sqlalchemy as sa
from alembic import op

revision = "0018_audio_mensagens"
down_revision = "0017_arquivamento_conversas"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("conversas") as batch:
        batch.add_column(sa.Column("contato_optin_em", sa.DateTime(timezone=True)))
    with op.batch_alter_table("mensagens") as batch:
        batch.add_column(sa.Column("audio_chave", sa.String(40)))
        batch.create_unique_constraint("uq_mensagem_audio_chave", ["audio_chave"])


def downgrade():
    with op.batch_alter_table("mensagens") as batch:
        batch.drop_column("audio_chave")
    with op.batch_alter_table("conversas") as batch:
        batch.drop_column("contato_optin_em")
