from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app import configuracao


def montar_url(nome_banco=None):
    if configuracao.URL_BANCO:
        return configuracao.URL_BANCO
    parametros = {"driver": configuracao.DRIVER_ODBC, "TrustServerCertificate": "yes"}
    if not configuracao.USUARIO_BANCO:
        parametros["Trusted_Connection"] = "yes"
    return URL.create(
        "mssql+pyodbc",
        username=configuracao.USUARIO_BANCO or None,
        password=configuracao.SENHA_BANCO or None,
        host=configuracao.SERVIDOR_BANCO,
        port=configuracao.PORTA_BANCO,
        database=nome_banco or configuracao.NOME_BANCO,
        query=parametros,
    )


def usa_sql_server():
    return str(montar_url()).startswith("mssql")


def criar_motor(nome_banco=None, **opcoes):
    url = montar_url(nome_banco)
    argumentos = {"check_same_thread": False} if str(url).startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=argumentos, **opcoes)


motor = criar_motor()
FabricaSessao = sessionmaker(bind=motor, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@contextmanager
def abrir_sessao():
    sessao = FabricaSessao()
    try:
        yield sessao
        sessao.commit()
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()
