"""Auditoria de respostas e encerramentos do consentimento remoto.

Revision ID: 0015_remoto_auditoria
Revises: 0014_remoto_consentimento
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_remoto_auditoria"
down_revision = "0014_remoto_consentimento"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("acessos_remotos", sa.Column("respondido_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True))
    op.add_column("acessos_remotos", sa.Column("respondido_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("acessos_remotos", sa.Column("encerrado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True))


def downgrade():
    with op.batch_alter_table("acessos_remotos") as batch:
        batch.drop_column("encerrado_por_id")
        batch.drop_column("respondido_em")
        batch.drop_column("respondido_por_id")
