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
    # An older version attempted ALTER + FK outside batch and could have left
    # nullable columns in place before failing. Make this upgrade recoverable.
    inspector = sa.inspect(op.get_bind())
    colunas = {c["name"] for c in inspector.get_columns("acessos_remotos")}
    chaves = {
        tuple(c["constrained_columns"])
        for c in inspector.get_foreign_keys("acessos_remotos")
        if c["referred_table"] == "usuarios"
    }
    with op.batch_alter_table("acessos_remotos", recreate="always") as batch:
        if "respondido_por_id" not in colunas:
            batch.add_column(sa.Column("respondido_por_id", sa.Integer(), nullable=True))
        if "respondido_em" not in colunas:
            batch.add_column(sa.Column("respondido_em", sa.DateTime(timezone=True), nullable=True))
        if "encerrado_por_id" not in colunas:
            batch.add_column(sa.Column("encerrado_por_id", sa.Integer(), nullable=True))
        if ("respondido_por_id",) not in chaves:
            batch.create_foreign_key(
                "fk_acessos_remotos_respondido_por_id", "usuarios",
                ["respondido_por_id"], ["id"],
            )
        if ("encerrado_por_id",) not in chaves:
            batch.create_foreign_key(
                "fk_acessos_remotos_encerrado_por_id", "usuarios",
                ["encerrado_por_id"], ["id"],
            )


def downgrade():
    with op.batch_alter_table("acessos_remotos", recreate="always") as batch:
        batch.drop_constraint("fk_acessos_remotos_encerrado_por_id", type_="foreignkey")
        batch.drop_constraint("fk_acessos_remotos_respondido_por_id", type_="foreignkey")
        batch.drop_column("encerrado_por_id")
        batch.drop_column("respondido_em")
        batch.drop_column("respondido_por_id")
