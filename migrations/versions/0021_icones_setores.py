"""Ícones configuráveis para setores do WhatsApp e equipes internas."""

import sqlalchemy as sa
from alembic import op

revision = "0021_icones_setores"
down_revision = "0020_edicao_interno"
branch_labels = None
depends_on = None


def upgrade():
    for tabela in ("setores", "setores_internos"):
        with op.batch_alter_table(tabela) as batch:
            batch.add_column(sa.Column("icone", sa.String(24), nullable=False, server_default="equipe"))
    op.execute("UPDATE setores SET icone='vendas' WHERE ordem=1")
    op.execute("UPDATE setores SET icone='devolucao' WHERE ordem=2")
    op.execute("UPDATE setores SET icone='garantia' WHERE ordem=3")
    op.execute("UPDATE setores_internos SET icone='vendas' WHERE lower(nome) LIKE '%venda%'")
    op.execute("UPDATE setores_internos SET icone='estoque' WHERE lower(nome) LIKE '%estoque%'")
    op.execute("UPDATE setores_internos SET icone='garantia' WHERE lower(nome) LIKE '%garantia%'")
    op.execute("UPDATE setores_internos SET icone='administracao' WHERE lower(nome) LIKE '%administra%'")


def downgrade():
    for tabela in ("setores_internos", "setores"):
        with op.batch_alter_table(tabela) as batch:
            batch.drop_column("icone")
