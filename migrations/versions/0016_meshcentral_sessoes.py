"""MeshCentral real relay sessions and mapped operator identity.

Revision ID: 0016_meshcentral_sessoes
Revises: 0015_remoto_auditoria
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_meshcentral_sessoes"
down_revision = "0015_remoto_auditoria"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuarios") as batch:
        batch.add_column(sa.Column("mesh_user_id", sa.String(length=255), nullable=True))
        batch.create_unique_constraint("uq_usuarios_mesh_user_id", ["mesh_user_id"])
    op.create_table(
        "sessoes_meshcentral",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mesh_session_id", sa.String(length=255), nullable=False),
        sa.Column("mesh_node_id", sa.String(length=255), nullable=False),
        sa.Column("mesh_user_id", sa.String(length=255), nullable=False),
        sa.Column("mesh_username", sa.String(length=120), nullable=False),
        sa.Column("computador_id", sa.Integer(), sa.ForeignKey("computadores.id"), nullable=False),
        sa.Column("acesso_id", sa.Integer(), sa.ForeignKey("acessos_remotos.id"), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("inicio_em", sa.DateTime(timezone=True)),
        sa.Column("fim_em", sa.DateTime(timezone=True)),
        sa.Column("observado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("estado IN ('ativa','encerrada','desconhecida')"),
    )
    op.create_index("uq_mesh_sessao_node", "sessoes_meshcentral", ["mesh_node_id", "mesh_session_id"], unique=True)
    op.create_index("ix_sessoes_meshcentral_computador_id", "sessoes_meshcentral", ["computador_id"])
    op.create_index("ix_sessoes_meshcentral_acesso_id", "sessoes_meshcentral", ["acesso_id"])


def downgrade():
    op.drop_index("ix_sessoes_meshcentral_acesso_id", table_name="sessoes_meshcentral")
    op.drop_index("ix_sessoes_meshcentral_computador_id", table_name="sessoes_meshcentral")
    op.drop_index("uq_mesh_sessao_node", table_name="sessoes_meshcentral")
    op.drop_table("sessoes_meshcentral")
    with op.batch_alter_table("usuarios") as batch:
        batch.drop_constraint("uq_usuarios_mesh_user_id", type_="unique")
        batch.drop_column("mesh_user_id")
