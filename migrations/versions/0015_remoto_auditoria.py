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
    # SQLite requires batch recreation to add foreign key constraints.
    with op.batch_alter_table("acessos_remotos", recreate="always") as batch:
        batch.add_column(sa.Column(
            "respondido_por_id", sa.Integer(),
            sa.ForeignKey("usuarios.id", name="fk_acessos_remotos_respondido_por_id"),
            nullable=True,
        ))
        batch.add_column(sa.Column("respondido_em", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column(
            "encerrado_por_id", sa.Integer(),
            sa.ForeignKey("usuarios.id", name="fk_acessos_remotos_encerrado_por_id"),
            nullable=True,
        ))


def downgrade():
    with op.batch_alter_table("acessos_remotos", recreate="always") as batch:
        batch.drop_constraint("fk_acessos_remotos_encerrado_por_id", type_="foreignkey")
        batch.drop_constraint("fk_acessos_remotos_respondido_por_id", type_="foreignkey")
        batch.drop_column("encerrado_por_id")
        batch.drop_column("respondido_em")
        batch.drop_column("respondido_por_id")
