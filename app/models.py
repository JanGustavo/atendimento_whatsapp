from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import now as agora  # agora() → now() centralizado


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint("role IN ('colaborador','supervisor','gestor')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    online: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ultima_atividade_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mesh_user_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    foto_chave: Mapped[str | None] = mapped_column(String(40), unique=True)
    ultima_atribuicao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    setor_interno_id: Mapped[int | None] = mapped_column(Integer)


class Setor(Base):
    __tablename__ = "setores"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    ordem: Mapped[int] = mapped_column(Integer, unique=True)
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    responsavel: Mapped[Usuario | None] = relationship()


class SetorInterno(Base):
    __tablename__ = "setores_internos"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)


class MensagemInterna(Base):
    __tablename__ = "mensagens_internas"
    id: Mapped[int] = mapped_column(primary_key=True)
    remetente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    destinatario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    imagem_chave: Mapped[str | None] = mapped_column(String(40), unique=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class MensagemGrupo(Base):
    __tablename__ = "mensagens_grupo"
    id: Mapped[int] = mapped_column(primary_key=True)
    setor_id: Mapped[int] = mapped_column(ForeignKey("setores_internos.id"), index=True)
    remetente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    imagem_chave: Mapped[str | None] = mapped_column(String(40), unique=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class LeituraInterna(Base):
    __tablename__ = "leituras_internas"
    __table_args__ = (
        CheckConstraint("tipo IN ('direta','grupo')"),
        Index("uq_leitura_interna_usuario_tipo_alvo", "usuario_id", "tipo", "alvo_id", unique=True),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    alvo_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ultima_mensagem_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SimuladorEstado(Base):
    __tablename__ = "simulador_estado"
    id: Mapped[int] = mapped_column(primary_key=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Conversa(Base):
    __tablename__ = "conversas"
    __table_args__ = (
        Index(
            "uq_conversa_aberta_numero",
            "numero",
            unique=True,
            sqlite_where=text("status = 'aberta'"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(30), index=True)
    nome_contato: Mapped[str | None] = mapped_column(String(120))
    foto_chave: Mapped[str | None] = mapped_column(String(40))
    setor_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id"))
    atribuido_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="aberta", nullable=False)
    etapa: Mapped[str] = mapped_column(String(30), default="menu_setor", nullable=False)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    primeira_resposta_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timer_inicio_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timer_prazo_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timer_aviso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timer_extensoes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tentativas_timer: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    setor: Mapped[Setor | None] = relationship()
    atribuido: Mapped[Usuario | None] = relationship()


class Mensagem(Base):
    __tablename__ = "mensagens"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas.id"), index=True)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    origem: Mapped[str] = mapped_column(String(20))
    texto: Mapped[str] = mapped_column(Text)
    imagem_chave: Mapped[str | None] = mapped_column(String(40), unique=True)
    provider_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    envio_status: Mapped[str | None] = mapped_column(String(20))
    lida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class LeituraConversa(Base):
    __tablename__ = "leituras_conversas"
    __table_args__ = (
        Index("uq_leitura_conversa_usuario", "conversa_id", "usuario_id", unique=True),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas.id"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    ultima_mensagem_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Atribuicao(Base):
    __tablename__ = "atribuicoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas.id"), index=True)
    de_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    para_usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    motivo: Mapped[str] = mapped_column(String(80))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Computador(Base):
    __tablename__ = "computadores"
    __table_args__ = (CheckConstraint("grupo IN ('empresa','dono')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    dono_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    mesh_node_id: Mapped[str | None] = mapped_column(String(255))
    grupo: Mapped[str] = mapped_column(String(20), nullable=False)
    dono: Mapped[Usuario | None] = relationship()


class Chamado(Base):
    __tablename__ = "chamados"
    __table_args__ = (CheckConstraint("status IN ('aberto','em_atendimento','fechado')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    computador_id: Mapped[int] = mapped_column(ForeignKey("computadores.id"), index=True)
    descricao: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="aberto", nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    solucao: Mapped[str | None] = mapped_column(Text)
    computador: Mapped[Computador] = relationship()


class AcessoRemoto(Base):
    __tablename__ = "acessos_remotos"
    __table_args__ = (CheckConstraint("resultado IN ('pendente','autorizado','recusado','expirado','encerrado','cancelado','simulado','aceito')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chamado_id: Mapped[int] = mapped_column(ForeignKey("chamados.id"), index=True)
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    computador_id: Mapped[int] = mapped_column(ForeignKey("computadores.id"))
    inicio_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    fim_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    expira_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    autorizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    autorizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    respondido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    respondido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    encerrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    solicitante: Mapped[Usuario] = relationship(foreign_keys=[solicitante_id])
    computador: Mapped[Computador] = relationship()


class SessaoMeshCentral(Base):
    """Sessao real observada no relay MeshCentral (nao uma autorizacao)."""

    __tablename__ = "sessoes_meshcentral"
    __table_args__ = (
        Index("uq_mesh_sessao_node", "mesh_node_id", "mesh_session_id", unique=True),
        CheckConstraint("estado IN ('ativa','encerrada','desconhecida')"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    mesh_session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    mesh_node_id: Mapped[str] = mapped_column(String(255), nullable=False)
    mesh_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    mesh_username: Mapped[str] = mapped_column(String(120), nullable=False)
    computador_id: Mapped[int] = mapped_column(ForeignKey("computadores.id"), index=True)
    acesso_id: Mapped[int | None] = mapped_column(ForeignKey("acessos_remotos.id"), index=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    inicio_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fim_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
