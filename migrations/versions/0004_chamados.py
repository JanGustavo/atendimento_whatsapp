"""Chamados de suporte e auditoria remota.

Revision ID: 0004_chamados
Revises: 0003_conversas_whatsapp
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_chamados"
down_revision = "0003_conversas_whatsapp"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "computadores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("dono_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("mesh_node_id", sa.String(255)),
        sa.Column("grupo", sa.String(20), nullable=False),
        sa.CheckConstraint("grupo IN ('empresa','dono')"),
    )
    op.create_index("ix_computadores_nome", "computadores", ["nome"], unique=True)
    op.create_table(
        "chamados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("computador_id", sa.Integer(), sa.ForeignKey("computadores.id"), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("solucao", sa.Text()),
        sa.CheckConstraint("status IN ('aberto','em_atendimento','fechado')"),
    )
    op.create_index("ix_chamados_computador_id", "chamados", ["computador_id"])
    op.create_table(
        "acessos_remotos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chamado_id", sa.Integer(), sa.ForeignKey("chamados.id"), nullable=False),
        sa.Column("solicitante_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("computador_id", sa.Integer(), sa.ForeignKey("computadores.id"), nullable=False),
        sa.Column("inicio_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fim_em", sa.DateTime(timezone=True)),
        sa.Column("resultado", sa.String(20), nullable=False),
        sa.CheckConstraint("resultado IN ('aceito','recusado','cancelado','simulado')"),
    )
    op.create_index("ix_acessos_remotos_chamado_id", "acessos_remotos", ["chamado_id"])


def downgrade():
    op.drop_table("acessos_remotos")
    op.drop_table("chamados")
    op.drop_table("computadores")
