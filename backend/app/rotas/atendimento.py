from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import servico
from app.eventos import difundir, enriquecer
from app.rotas.comum import erro_http, ler_arquivo, resposta_arquivo
from app.seguranca import usuario_autenticado

roteador = APIRouter(prefix="/api/atendimento", tags=["Atendimento"])


@roteador.get("/painel")
def painel(usuario: dict = Depends(usuario_autenticado)):
    dados = servico.listar_painel(usuario)
    for conversa in (*dados["fila"], *dados["meus"]):
        enriquecer(conversa)
    return dados


@roteador.get("/historico")
def historico(
    busca: str = "",
    status: str = "",
    data_inicio: str = "",
    data_fim: str = "",
    pagina: int = 1,
    usuario: dict = Depends(usuario_autenticado),
):
    try:
        return servico.listar_historico(usuario, busca, status, data_inicio, data_fim, pagina)
    except servico.ErroNegocio as erro:
        raise erro_http(erro)


@roteador.get("/conversas/{conversa_id}")
def obter_conversa(conversa_id: int, usuario: dict = Depends(usuario_autenticado)):
    try:
        return servico.obter_conversa(conversa_id, usuario)
    except servico.ErroNegocio as erro:
        raise erro_http(erro)


@roteador.post("/conversas/{conversa_id}/assumir")
async def assumir(conversa_id: int, usuario: dict = Depends(usuario_autenticado)):
    try:
        _, mensagens, conversa = await run_in_threadpool(servico.assumir_conversa, conversa_id, usuario)
    except servico.ErroNegocio as erro:
        raise erro_http(erro)
    await difundir(conversa_id, mensagens, conversa)
    return conversa


@roteador.post("/conversas/{conversa_id}/encerrar")
async def encerrar(conversa_id: int, usuario: dict = Depends(usuario_autenticado)):
    try:
        _, mensagens, conversa = await run_in_threadpool(servico.encerrar_conversa, conversa_id, usuario)
    except servico.ErroNegocio as erro:
        raise erro_http(erro)
    await difundir(conversa_id, mensagens, conversa)
    return conversa


@roteador.post("/conversas/{conversa_id}/anexos")
async def enviar_anexo(
    conversa_id: int,
    arquivo: UploadFile = File(...),
    legenda: str = Form(""),
    usuario: dict = Depends(usuario_autenticado),
):
    conteudo_arquivo = await ler_arquivo(arquivo)
    try:
        _, mensagens, conversa = await run_in_threadpool(
            servico.registrar_anexo_operador, conversa_id, usuario, conteudo_arquivo, legenda
        )
    except servico.ErroNegocio as erro:
        raise erro_http(erro)
    await difundir(conversa_id, mensagens, conversa)
    return {"ok": True}


@roteador.get("/anexos/{anexo_id}")
def baixar_anexo(anexo_id: int, usuario: dict = Depends(usuario_autenticado)):
    try:
        return resposta_arquivo(*servico.obter_anexo_usuario(usuario, anexo_id))
    except servico.ErroNegocio as erro:
        raise erro_http(erro)
