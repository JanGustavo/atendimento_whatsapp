"""Nome do perfil do cliente recebido pelo webhook da Meta.

Revision ID: 0011_nome_contato_whatsapp
Revises: 0010_conversas_presenca_fotos
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_nome_contato_whatsapp"
down_revision = "0010_conversas_presenca_fotos"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversas", sa.Column("nome_contato", sa.String(120)))


def downgrade():
    op.drop_column("conversas", "nome_contato")
