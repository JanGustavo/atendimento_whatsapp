"""Data de edição de mensagens internas.

Revision ID: 0020_edicao_interno
Revises: 0019_audio_exclusao_interno
"""

import sqlalchemy as sa
from alembic import op

revision = "0020_edicao_interno"
down_revision = "0019_audio_exclusao_interno"
branch_labels = None
depends_on = None


def upgrade():
    for tabela in ("mensagens_internas", "mensagens_grupo"):
        with op.batch_alter_table(tabela) as batch:
            batch.add_column(sa.Column("editada_em", sa.DateTime(timezone=True)))


def downgrade():
    for tabela in ("mensagens_grupo", "mensagens_internas"):
        with op.batch_alter_table(tabela) as batch:
            batch.drop_column("editada_em")
