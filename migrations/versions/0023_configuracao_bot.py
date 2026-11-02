"""Horários e textos automáticos configuráveis pelo gestor."""

import sqlalchemy as sa
from alembic import op

revision = "0023_configuracao_bot"
down_revision = "0022_retencao_conversas"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "configuracao_bot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("horarios", sa.JSON(), nullable=False),
        sa.Column("dias_fechados", sa.JSON(), nullable=False),
        sa.Column("mensagem_fora_expediente", sa.Text(), nullable=False),
        sa.Column("mensagem_reabertura", sa.Text(), nullable=False),
        sa.Column("mensagem_standby", sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table("configuracao_bot")
