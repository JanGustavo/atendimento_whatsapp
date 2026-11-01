"""Áudio e exclusão lógica no chat interno.

Revision ID: 0019_audio_exclusao_interno
Revises: 0018_audio_mensagens
"""

import sqlalchemy as sa
from alembic import op

revision = "0019_audio_exclusao_interno"
down_revision = "0018_audio_mensagens"
branch_labels = None
depends_on = None


def upgrade():
    for tabela in ("mensagens_internas", "mensagens_grupo"):
        with op.batch_alter_table(tabela) as batch:
            batch.add_column(sa.Column("audio_chave", sa.String(40)))
            batch.add_column(sa.Column("apagada_em", sa.DateTime(timezone=True)))
            batch.create_unique_constraint(f"uq_{tabela}_audio_chave", ["audio_chave"])


def downgrade():
    for tabela in ("mensagens_grupo", "mensagens_internas"):
        with op.batch_alter_table(tabela) as batch:
            batch.drop_constraint(f"uq_{tabela}_audio_chave", type_="unique")
            batch.drop_column("apagada_em")
            batch.drop_column("audio_chave")
