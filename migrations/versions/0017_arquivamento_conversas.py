"""Arquivamento local de conversas sem alterar o estado do atendimento.

Revision ID: 0017_arquivamento_conversas
Revises: 0016_meshcentral_sessoes
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_arquivamento_conversas"
down_revision = "0016_meshcentral_sessoes"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("conversas") as batch:
        batch.add_column(sa.Column("arquivada_em", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("arquivada_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", name="fk_conversa_arquivada_por")))


def downgrade():
    with op.batch_alter_table("conversas") as batch:
        batch.drop_column("arquivada_por_id")
        batch.drop_column("arquivada_em")
