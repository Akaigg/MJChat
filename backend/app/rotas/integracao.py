from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import servico
from app.rotas.comum import erro_http
from app.seguranca import validar_chave_integracao

roteador = APIRouter(prefix="/api/integracao", tags=["Integração"], dependencies=[Depends(validar_chave_integracao)])


class ClienteIntegracao(BaseModel):
    nome: str
    cpf: str | None = None
    telefone: str
    credor: str
    valor_divida: str
    data_vencimento: str


@roteador.post("/links")
def gerar_link(dados: ClienteIntegracao):
    try:
        cliente = servico.salvar_cliente(dados.model_dump(), reaproveitar=True)
    except servico.ErroNegocio as erro:
        raise erro_http(erro)
    return {"token": cliente["link"].rsplit("/", 1)[-1], "link": cliente["link"], "cliente_id": cliente["id"]}
