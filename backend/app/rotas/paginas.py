from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

from app import configuracao

roteador = APIRouter(include_in_schema=False)


def pagina(nome: str) -> FileResponse:
    return FileResponse(configuracao.PASTA_FRONTEND / nome, headers={"Cache-Control": "no-cache"})


@roteador.get("/")
def inicio():
    return RedirectResponse("/login")


@roteador.get("/login")
def login():
    return pagina("login.html")


@roteador.get("/atendimento")
def atendimento():
    return pagina("atendimento.html")


@roteador.get("/admin")
def admin():
    return pagina("admin.html")


@roteador.get("/c/{token}")
def chat_cliente(token: str):
    return pagina("cliente.html")
