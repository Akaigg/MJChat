from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import servico
from app.eventos import esta_online, sala_usuario
from app.rotas.comum import erro_http
from app.seguranca import administrador, gerar_senha_aleatoria

roteador = APIRouter(prefix="/api/admin", tags=["Administração"], dependencies=[Depends(administrador)])


class NovoUsuario(BaseModel):
    matricula: str
    nome: str
    perfil: str = "operador"
    senha: str


class AlteracaoUsuario(BaseModel):
    nome: str | None = None
    perfil: str | None = None
    ativo: bool | None = None
    senha: str | None = None


class DadosCliente(BaseModel):
    nome: str
    cpf: str | None = None
    telefone: str
    credor: str
    valor_divida: str
    data_vencimento: str


@roteador.get("/usuarios")
def listar_usuarios():
    usuarios = servico.listar_usuarios()
    for usuario in usuarios:
        usuario["online"] = esta_online(sala_usuario(usuario["id"]))
    return usuarios


@roteador.post("/usuarios", status_code=201)
def criar_usuario(dados: NovoUsuario):
    try:
        return servico.criar_usuario(dados.model_dump())
    except servico.ErroNegocio as erro:
        raise erro_http(erro)


@roteador.patch("/usuarios/{usuario_id}")
def atualizar_usuario(usuario_id: int, dados: AlteracaoUsuario, admin: dict = Depends(administrador)):
    try:
        return servico.atualizar_usuario(admin, usuario_id, dados.model_dump())
    except servico.ErroNegocio as erro:
        raise erro_http(erro)


@roteador.get("/senha-aleatoria")
def senha_aleatoria():
    return {"senha": gerar_senha_aleatoria()}


@roteador.get("/clientes")
def listar_clientes(busca: str = ""):
    return servico.listar_clientes(busca)


@roteador.post("/clientes", status_code=201)
def criar_cliente(dados: DadosCliente):
    try:
        return servico.salvar_cliente(dados.model_dump())
    except servico.ErroNegocio as erro:
        raise erro_http(erro)


@roteador.put("/clientes/{cliente_id}")
def atualizar_cliente(cliente_id: int, dados: DadosCliente):
    try:
        return servico.atualizar_cliente(cliente_id, dados.model_dump())
    except servico.ErroNegocio as erro:
        raise erro_http(erro)
