"""Data de encerramento para retenção de conversas."""

import sqlalchemy as sa
from alembic import op

revision = "0022_retencao_conversas"
down_revision = "0021_icones_setores"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("conversas") as batch:
        batch.add_column(sa.Column("encerrada_em", sa.DateTime(timezone=True)))
        batch.create_index("ix_conversas_encerrada_em", ["encerrada_em"])
    # Não se sabe a data real de fechamento dos registros antigos.
    # Começamos o prazo agora para evitar exclusão antecipada.
    op.execute("UPDATE conversas SET encerrada_em=CURRENT_TIMESTAMP WHERE status='encerrada'")


def downgrade():
    with op.batch_alter_table("conversas") as batch:
        batch.drop_index("ix_conversas_encerrada_em")
        batch.drop_column("encerrada_em")
