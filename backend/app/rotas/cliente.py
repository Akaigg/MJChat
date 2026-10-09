from fastapi import APIRouter, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import servico
from app.eventos import difundir, esta_online, sala_usuario
from app.rotas.comum import erro_http, ler_arquivo, resposta_arquivo

roteador = APIRouter(prefix="/api/cliente", tags=["Cliente"])


@roteador.get("/{token}")
def abrir_atendimento(token: str):
    try:
        dados = servico.abrir_atendimento_cliente(token)
    except servico.ErroNegocio as erro:
        raise erro_http(erro)
    operador_id = dados["conversa"]["operador_id"]
    dados["conversa"]["operador_online"] = bool(operador_id) and esta_online(sala_usuario(operador_id))
    return dados


@roteador.post("/{token}/anexos")
async def enviar_anexo(token: str, arquivo: UploadFile = File(...), legenda: str = Form("")):
    conteudo_arquivo = await ler_arquivo(arquivo)
    try:
        conversa_id, mensagens, conversa = await run_in_threadpool(
            servico.registrar_mensagem_cliente, token, legenda, conteudo_arquivo
        )
    except servico.ErroNegocio as erro:
        raise erro_http(erro)
    await difundir(conversa_id, mensagens, conversa)
    return {"ok": True}


@roteador.get("/{token}/anexos/{anexo_id}")
def baixar_anexo(token: str, anexo_id: int):
    try:
        return resposta_arquivo(*servico.obter_anexo_cliente(token, anexo_id))
    except servico.ErroNegocio as erro:
        raise erro_http(erro)
