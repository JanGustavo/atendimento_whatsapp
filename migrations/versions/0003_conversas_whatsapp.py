"""Permite nova conversa após encerramento e registra envio.

Revision ID: 0003_conversas_whatsapp
Revises: 0002_estados_chatbot
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_conversas_whatsapp"
down_revision = "0002_estados_chatbot"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("ix_conversas_numero", table_name="conversas")
    op.create_index("ix_conversas_numero", "conversas", ["numero"])
    op.create_index("uq_conversa_aberta_numero", "conversas", ["numero"], unique=True,
                    sqlite_where=sa.text("status = 'aberta'"))
    op.add_column("mensagens", sa.Column("envio_status", sa.String(20), nullable=True))
    op.execute("UPDATE mensagens SET envio_status='enviada' WHERE origem IN ('humano', 'bot')")


def downgrade():
    op.drop_column("mensagens", "envio_status")
    op.drop_index("uq_conversa_aberta_numero", table_name="conversas")
    op.drop_index("ix_conversas_numero", table_name="conversas")
    op.create_index("ix_conversas_numero", "conversas", ["numero"], unique=True)
