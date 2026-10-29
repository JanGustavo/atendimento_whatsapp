"""Limite de tentativas automáticas do bot.

Revision ID: 0006_limites_bot
Revises: 0005_chat_interno
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_limites_bot"
down_revision = "0005_chat_interno"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversas", sa.Column("tentativas_timer", sa.Integer(), nullable=False, server_default="0"))
    op.execute("""UPDATE conversas SET tentativas_timer = CASE
        WHEN (SELECT COUNT(*) FROM atribuicoes WHERE atribuicoes.conversa_id = conversas.id) >= 2 THEN 2
        ELSE 1 END
        WHERE status = 'aberta' AND setor_id IN (SELECT id FROM setores WHERE ordem = 1)
        AND atribuido_id IS NOT NULL AND primeira_resposta_em IS NULL""")


def downgrade():
    op.drop_column("conversas", "tentativas_timer")
