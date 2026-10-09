import asyncio

import socketio

from app import servico
from app.seguranca import carregar_usuario_do_token

SALA_OPERADORES = "operadores"
ESPACO = "/"

sio = socketio.AsyncServer(async_mode="asgi", max_http_buffer_size=64 * 1024)


def sala_conversa(conversa_id: int) -> str:
    return f"conversa_{conversa_id}"


def sala_cliente(cliente_id: int) -> str:
    return f"cliente_{cliente_id}"


def sala_usuario(usuario_id: int) -> str:
    return f"usuario_{usuario_id}"


def esta_online(sala: str) -> bool:
    return any(sio.manager.is_connected(sid, ESPACO) for sid, _ in sio.manager.get_participants(ESPACO, sala))


def enriquecer(conversa: dict) -> dict:
    conversa["cliente"]["online"] = esta_online(sala_cliente(conversa["cliente"]["id"]))
    if conversa.get("operador"):
        conversa["operador"]["online"] = esta_online(sala_usuario(conversa["operador"]["id"]))
    return conversa


async def executar(funcao, *argumentos):
    return await asyncio.to_thread(funcao, *argumentos)


async def difundir(conversa_id: int, mensagens: list[dict], conversa: dict | None = None):
    for mensagem in mensagens:
        await sio.emit("nova_mensagem", mensagem, room=sala_conversa(conversa_id))
    if conversa:
        enriquecer(conversa)
        await sio.emit("status_conversa", servico.serializar_status_cliente(conversa), room=sala_conversa(conversa_id))
        await sio.emit("conversa_atualizada", conversa, room=SALA_OPERADORES)


async def difundir_confirmacoes(confirmacoes: list[dict]):
    for confirmacao in confirmacoes:
        await sio.emit("mensagens_confirmadas", confirmacao, room=sala_conversa(confirmacao["conversa_id"]))


async def avisar_presenca_cliente(cliente_id: int, online: bool):
    visto = await executar(servico.registrar_visto_cliente, cliente_id)
    dados = {"tipo": "cliente", "cliente_id": cliente_id, "online": online, "visto_por_ultimo": visto}
    await sio.emit("presenca", dados, room=SALA_OPERADORES)


async def avisar_presenca_usuario(usuario_id: int, online: bool):
    visto, conversas = await executar(servico.registrar_visto_usuario, usuario_id)
    dados = {"tipo": "operador", "operador_id": usuario_id, "online": online, "visto_por_ultimo": visto}
    for conversa_id in conversas:
        await sio.emit("presenca", dados, room=sala_conversa(conversa_id))


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
            dados = await executar(servico.identificar_cliente, token_cliente)
        except servico.ErroNegocio:
            raise ConnectionRefusedError("link_invalido")
        primeira_conexao = not esta_online(sala_cliente(dados["cliente_id"]))
        await sio.save_session(sid, {"tipo": "cliente", "token": token_cliente, "cliente_id": dados["cliente_id"]})
        await sio.enter_room(sid, sala_cliente(dados["cliente_id"]))
        if dados["conversa_id"]:
            await sio.enter_room(sid, sala_conversa(dados["conversa_id"]))
        if primeira_conexao:
            await avisar_presenca_cliente(dados["cliente_id"], True)
        return
    usuario = await executar(carregar_usuario_do_token, autenticacao.get("token") or "")
    if not usuario:
        raise ConnectionRefusedError("nao_autorizado")
    primeira_conexao = not esta_online(sala_usuario(usuario["id"]))
    await sio.save_session(
        sid, {"tipo": "usuario", "token": autenticacao["token"], "usuario_id": usuario["id"], "conversa_id": None}
    )
    await sio.enter_room(sid, SALA_OPERADORES)
    await sio.enter_room(sid, sala_usuario(usuario["id"]))
    if primeira_conexao:
        await avisar_presenca_usuario(usuario["id"], True)


@sio.event
async def disconnect(sid, *argumentos):
    sessao = await sio.get_session(sid)
    if sessao.get("tipo") == "cliente":
        if not esta_online(sala_cliente(sessao["cliente_id"])):
            await avisar_presenca_cliente(sessao["cliente_id"], False)
    elif sessao.get("tipo") == "usuario":
        if not esta_online(sala_usuario(sessao["usuario_id"])):
            await avisar_presenca_usuario(sessao["usuario_id"], False)


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
    enriquecer(resultado["conversa"])
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
async def confirmar(sid, dados):
    dados = dados or {}
    sessao = await sio.get_session(sid)
    try:
        conversa_id = int(dados.get("conversa_id"))
        ate_id = int(dados["ate"]) if dados.get("ate") else None
        tipo = str(dados.get("tipo") or "")
        if sessao.get("tipo") == "cliente":
            confirmacoes = await executar(servico.confirmar_pelo_cliente, sessao["token"], conversa_id, tipo, ate_id)
        else:
            usuario = await usuario_da_sessao(sid)
            if not usuario:
                return {"erro": "Sessão expirada"}
            confirmacoes = await executar(servico.confirmar_pelo_operador, usuario, conversa_id, tipo, ate_id)
    except (TypeError, ValueError):
        return {"erro": "Dados inválidos"}
    except servico.ErroNegocio as erro:
        return {"erro": erro.mensagem}
    await difundir_confirmacoes(confirmacoes)
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
