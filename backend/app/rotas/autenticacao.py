from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app import servico
from app.rotas.comum import erro_http
from app.seguranca import usuario_autenticado

roteador = APIRouter(prefix="/api/autenticacao", tags=["Autenticação"])


class DadosLogin(BaseModel):
    matricula: str
    senha: str


@roteador.post("/login")
async def entrar(dados: DadosLogin):
    try:
        return await run_in_threadpool(servico.autenticar, dados.matricula, dados.senha)
    except servico.ErroNegocio as erro:
        raise erro_http(erro)


@roteador.get("/eu")
def usuario_logado(usuario: dict = Depends(usuario_autenticado)):
    return usuario
