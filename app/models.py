from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def agora() -> datetime:
    return datetime.now(UTC)


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint("role IN ('vendedor','responsavel','gestor')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    online: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ultima_atribuicao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Setor(Base):
    __tablename__ = "setores"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    ordem: Mapped[int] = mapped_column(Integer, unique=True)
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    responsavel: Mapped[Usuario | None] = relationship()


class Conversa(Base):
    __tablename__ = "conversas"
    __table_args__ = (Index("uq_conversa_aberta_numero", "numero", unique=True, sqlite_where=text("status = 'aberta'")),)
    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(30), index=True)
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
    setor: Mapped[Setor | None] = relationship()
    atribuido: Mapped[Usuario | None] = relationship()


class Mensagem(Base):
    __tablename__ = "mensagens"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas.id"), index=True)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    origem: Mapped[str] = mapped_column(String(20))
    texto: Mapped[str] = mapped_column(Text)
    provider_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    envio_status: Mapped[str | None] = mapped_column(String(20))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


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
    __table_args__ = (CheckConstraint("resultado IN ('aceito','recusado','cancelado','simulado')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chamado_id: Mapped[int] = mapped_column(ForeignKey("chamados.id"), index=True)
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    computador_id: Mapped[int] = mapped_column(ForeignKey("computadores.id"))
    inicio_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    fim_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    solicitante: Mapped[Usuario] = relationship()
    computador: Mapped[Computador] = relationship()
