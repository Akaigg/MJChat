import asyncio

import socketio

from app import servico
from app.seguranca import carregar_usuario_do_token

SALA_OPERADORES = "operadores"

sio = socketio.AsyncServer(async_mode="asgi", max_http_buffer_size=64 * 1024)


def sala_conversa(conversa_id: int) -> str:
    return f"conversa_{conversa_id}"


async def executar(funcao, *argumentos):
    return await asyncio.to_thread(funcao, *argumentos)


async def difundir(conversa_id: int, mensagens: list[dict], conversa: dict | None = None):
    for mensagem in mensagens:
        await sio.emit("nova_mensagem", mensagem, room=sala_conversa(conversa_id))
    if conversa:
        await sio.emit("status_conversa", servico.serializar_status_cliente(conversa), room=sala_conversa(conversa_id))
        await sio.emit("conversa_atualizada", conversa, room=SALA_OPERADORES)


async def usuario_da_sessao(sid: str):
    sessao = await sio.get_session(sid)
    if sessao.get("tipo") != "usuario":
        return None
    return await executar(carregar_usuario_do_token, sessao["token"])


@sio.event
async def connect(sid, ambiente, autenticacao):
    autenticacao = autenticacao or {}
    token_cliente = autenticacao.get("cliente")
    if token_cliente:
        try:
            conversa_id = await executar(servico.conversa_ativa_do_cliente, token_cliente)
        except servico.ErroNegocio:
            raise ConnectionRefusedError("link_invalido")
        await sio.save_session(sid, {"tipo": "cliente", "token": token_cliente})
        if conversa_id:
            await sio.enter_room(sid, sala_conversa(conversa_id))
        return
    usuario = await executar(carregar_usuario_do_token, autenticacao.get("token") or "")
    if not usuario:
        raise ConnectionRefusedError("nao_autorizado")
    await sio.save_session(sid, {"tipo": "usuario", "token": autenticacao["token"], "conversa_id": None})
    await sio.enter_room(sid, SALA_OPERADORES)


@sio.event
async def abrir_conversa(sid, dados):
    usuario = await usuario_da_sessao(sid)
    if not usuario:
        return {"erro": "Sessão expirada"}
    try:
        conversa_id = int((dados or {}).get("conversa_id"))
        resultado = await executar(servico.obter_conversa, conversa_id, usuario)
    except (TypeError, ValueError):
        return {"erro": "Conversa inválida"}
    except servico.ErroNegocio as erro:
        return {"erro": erro.mensagem}
    sessao = await sio.get_session(sid)
    if sessao.get("conversa_id") and sessao["conversa_id"] != conversa_id:
        await sio.leave_room(sid, sala_conversa(sessao["conversa_id"]))
    sessao["conversa_id"] = conversa_id
    await sio.save_session(sid, sessao)
    await sio.enter_room(sid, sala_conversa(conversa_id))
    return resultado


@sio.event
async def fechar_conversa(sid, dados=None):
    sessao = await sio.get_session(sid)
    if sessao.get("tipo") == "usuario" and sessao.get("conversa_id"):
        await sio.leave_room(sid, sala_conversa(sessao["conversa_id"]))
        sessao["conversa_id"] = None
        await sio.save_session(sid, sessao)


@sio.event
async def enviar_mensagem(sid, dados):
    dados = dados or {}
    sessao = await sio.get_session(sid)
    try:
        if sessao.get("tipo") == "cliente":
            conversa_id, mensagens, conversa = await executar(
                servico.registrar_mensagem_cliente, sessao["token"], str(dados.get("conteudo") or "")
            )
            await sio.enter_room(sid, sala_conversa(conversa_id))
        else:
            usuario = await usuario_da_sessao(sid)
            if not usuario:
                return {"erro": "Sessão expirada"}
            boleto = dados.get("boleto") if isinstance(dados.get("boleto"), dict) else None
            conversa_id, mensagens, conversa = await executar(
                servico.registrar_mensagem_operador,
                int(dados.get("conversa_id")),
                usuario,
                str(dados.get("conteudo") or ""),
                boleto,
            )
    except (TypeError, ValueError):
        return {"erro": "Dados inválidos"}
    except servico.ErroNegocio as erro:
        return {"erro": erro.mensagem}
    await difundir(conversa_id, mensagens, conversa)
    return {"ok": True}


@sio.event
async def digitando(sid, dados=None):
    sessao = await sio.get_session(sid)
    if sessao.get("tipo") == "cliente":
        conversa_id = await executar(servico.conversa_ativa_do_cliente, sessao["token"])
        remetente = "cliente"
    else:
        conversa_id = sessao.get("conversa_id")
        remetente = "operador"
    if conversa_id:
        await sio.emit("digitando", {"conversa_id": conversa_id, "remetente": remetente}, room=sala_conversa(conversa_id), skip_sid=sid)
