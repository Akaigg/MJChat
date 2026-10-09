from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Unicode,
    UnicodeText,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import configuracao
from app.banco import Base

FUSO = ZoneInfo(configuracao.FUSO_HORARIO)


def agora():
    return datetime.now(FUSO).replace(tzinfo=None, microsecond=0)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    matricula: Mapped[str] = mapped_column(String(4), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(Unicode(120), nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    perfil: Mapped[str] = mapped_column(String(20), nullable=False, default="operador")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=agora)
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DateTime)


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(Unicode(150), nullable=False)
    cpf: Mapped[str | None] = mapped_column(String(14))
    telefone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    credor: Mapped[str] = mapped_column(Unicode(150), nullable=False)
    valor_divida: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    data_vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=agora)


class Conversa(Base):
    __tablename__ = "conversas"
    __table_args__ = {"implicit_returning": False}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), nullable=False, index=True)
    operador_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="iniciada", index=True)
    assunto: Mapped[str | None] = mapped_column(Unicode(500))
    iniciada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=agora)
    assumida_em: Mapped[datetime | None] = mapped_column(DateTime)
    encerrada_em: Mapped[datetime | None] = mapped_column(DateTime)
    ultima_mensagem_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=agora)
    retencao_ate: Mapped[date] = mapped_column(Date, nullable=False)

    cliente: Mapped[Cliente] = relationship(lazy="joined")
    operador: Mapped[Usuario | None] = relationship(lazy="joined")


class Mensagem(Base):
    __tablename__ = "mensagens"
    __table_args__ = {"implicit_returning": False}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas.id"), nullable=False, index=True)
    remetente: Mapped[str] = mapped_column(String(20), nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="texto")
    conteudo: Mapped[str | None] = mapped_column(UnicodeText)
    url_boleto: Mapped[str | None] = mapped_column(String(2000))
    valor_boleto: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    vencimento_boleto: Mapped[date | None] = mapped_column(Date)
    enviada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=agora)

    usuario: Mapped[Usuario | None] = relationship(lazy="joined")
    anexo: Mapped["Anexo | None"] = relationship(back_populates="mensagem", lazy="joined", uselist=False)


class Anexo(Base):
    __tablename__ = "anexos"
    __table_args__ = {"implicit_returning": False}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mensagem_id: Mapped[int] = mapped_column(ForeignKey("mensagens.id"), nullable=False, unique=True)
    nome_arquivo: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    tipo_mime: Mapped[str] = mapped_column(String(100), nullable=False)
    tamanho: Mapped[int] = mapped_column(Integer, nullable=False)
    dados: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)

    mensagem: Mapped[Mensagem] = relationship(back_populates="anexo")
