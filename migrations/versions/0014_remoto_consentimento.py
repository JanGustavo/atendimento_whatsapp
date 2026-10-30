"""Estados de consentimento e validade para solicitacoes remotas.

Revision ID: 0014_remoto_consentimento
Revises: 0013_mensagem_imagem
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_remoto_consentimento"
down_revision = "0013_mensagem_imagem"
branch_labels = None
depends_on = None

RESULTADOS = "resultado IN ('pendente','autorizado','recusado','expirado','encerrado','cancelado','simulado','aceito')"
ANTIGOS = "resultado IN ('aceito','recusado','cancelado','simulado')"


def upgrade():
    # batch_alter_table recria a tabela no SQLite para atualizar CHECK.
    with op.batch_alter_table("acessos_remotos", recreate="always") as batch:
        batch.add_column(sa.Column("expira_em", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("autorizado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id")))
        batch.add_column(sa.Column("autorizado_em", sa.DateTime(timezone=True)))
    with op.batch_alter_table("acessos_remotos", recreate="always") as batch:
        batch.create_check_constraint("ck_acessos_remotos_resultado_novo", RESULTADOS)


def downgrade():
    op.execute("UPDATE acessos_remotos SET resultado='cancelado', fim_em=COALESCE(fim_em, inicio_em) WHERE resultado IN ('pendente','autorizado','expirado','encerrado')")
    with op.batch_alter_table("acessos_remotos", recreate="always") as batch:
        batch.drop_constraint("ck_acessos_remotos_resultado_novo", type_="check")
        batch.drop_column("autorizado_em")
        batch.drop_column("autorizado_por_id")
        batch.drop_column("expira_em")
