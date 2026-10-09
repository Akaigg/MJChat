from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_, select, update

from app import configuracao, seguranca
from app.banco import abrir_sessao
from app.modelos import FUSO, Anexo, Cliente, Conversa, Mensagem, Usuario, agora
from app.utilitarios import calcular_retencao, extrair_boleto, somente_digitos, url_valida

STATUS_ATIVOS = ("iniciada", "aguardando", "em_atendimento")
STATUS_VALIDOS = (*STATUS_ATIVOS, "encerrada")
PERFIS = ("admin", "operador")
ITENS_POR_PAGINA = 30

MENSAGEM_BOAS_VINDAS = (
    "Olá, {nome}! Bem-vindo(a) ao atendimento da {empresa}. "
    "Para começarmos, escreva abaixo o assunto que deseja tratar. "
    "Em seguida, aguarde: um de nossos operadores assumirá a conversa em instantes."
)
MENSAGEM_ASSUNTO_RECEBIDO = "Recebemos o seu assunto. Por favor, aguarde: um operador assumirá a conversa em breve."
MENSAGEM_ASSUMIDA = "{operador} assumiu o atendimento."
MENSAGEM_ENCERRADA = (
    "Atendimento encerrado. Obrigado pelo contato! "
    "Se precisar, acesse novamente o link recebido no WhatsApp."
)


class ErroNegocio(Exception):
    def __init__(self, mensagem: str, codigo: int = 400):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo


def iso(momento: datetime | None) -> str | None:
    return momento.replace(tzinfo=FUSO).isoformat() if momento else None


def link_cliente(cliente: Cliente) -> str:
    return f"{configuracao.URL_PUBLICA}/c/{cliente.token}"


def serializar_cliente(cliente: Cliente, completo: bool = True) -> dict:
    dados = {
        "nome": cliente.nome,
        "credor": cliente.credor,
        "valor_divida": float(cliente.valor_divida),
        "data_vencimento": cliente.data_vencimento.isoformat(),
    }
    if completo:
        dados.update(
            {
                "id": cliente.id,
                "cpf": cliente.cpf,
                "telefone": cliente.telefone,
                "link": link_cliente(cliente),
            }
        )
    return dados


def serializar_usuario(usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "matricula": usuario.matricula,
        "nome": usuario.nome,
        "perfil": usuario.perfil,
        "ativo": usuario.ativo,
        "criado_em": iso(usuario.criado_em),
        "ultimo_acesso": iso(usuario.ultimo_acesso),
    }


def serializar_mensagem(mensagem: Mensagem) -> dict:
    dados = {
        "id": mensagem.id,
        "conversa_id": mensagem.conversa_id,
        "remetente": mensagem.remetente,
        "nome_remetente": mensagem.usuario.nome if mensagem.usuario else None,
        "tipo": mensagem.tipo,
        "conteudo": mensagem.conteudo,
        "enviada_em": iso(mensagem.enviada_em),
        "boleto": None,
        "anexo": None,
    }
    if mensagem.url_boleto:
        dados["boleto"] = {
            "url": mensagem.url_boleto,
            "valor": float(mensagem.valor_boleto) if mensagem.valor_boleto is not None else None,
            "vencimento": mensagem.vencimento_boleto.isoformat() if mensagem.vencimento_boleto else None,
        }
    if mensagem.anexo:
        dados["anexo"] = {
            "id": mensagem.anexo.id,
            "nome": mensagem.anexo.nome_arquivo,
            "tipo_mime": mensagem.anexo.tipo_mime,
            "tamanho": mensagem.anexo.tamanho,
        }
    return dados


def serializar_conversa(conversa: Conversa, previa: str | None = None) -> dict:
    return {
        "id": conversa.id,
        "status": conversa.status,
        "assunto": conversa.assunto,
        "iniciada_em": iso(conversa.iniciada_em),
        "assumida_em": iso(conversa.assumida_em),
        "encerrada_em": iso(conversa.encerrada_em),
        "ultima_mensagem_em": iso(conversa.ultima_mensagem_em),
        "retencao_ate": conversa.retencao_ate.isoformat(),
        "operador": {"id": conversa.operador.id, "nome": conversa.operador.nome} if conversa.operador else None,
        "cliente": serializar_cliente(conversa.cliente),
        "previa": previa,
    }


def serializar_status_cliente(conversa: dict) -> dict:
    operador = conversa.get("operador")
    return {"id": conversa["id"], "status": conversa["status"], "operador_nome": operador["nome"] if operador else None}


def texto_previa(mensagem: Mensagem) -> str:
    if mensagem.tipo == "boleto":
        return "Boleto enviado"
    if mensagem.anexo:
        return f"Anexo: {mensagem.anexo.nome_arquivo}"
    return (mensagem.conteudo or "")[:120]


def _previas(sessao, ids: list[int]) -> dict:
    if not ids:
        return {}
    ultimas = (
        select(func.max(Mensagem.id))
        .where(Mensagem.conversa_id.in_(ids), Mensagem.remetente != "sistema")
        .group_by(Mensagem.conversa_id)
    )
    mensagens = sessao.scalars(select(Mensagem).where(Mensagem.id.in_(ultimas))).unique().all()
    return {mensagem.conversa_id: texto_previa(mensagem) for mensagem in mensagens}


def _listar_mensagens(sessao, conversa_id: int) -> list[dict]:
    consulta = select(Mensagem).where(Mensagem.conversa_id == conversa_id).order_by(Mensagem.id)
    return [serializar_mensagem(mensagem) for mensagem in sessao.scalars(consulta).unique().all()]


def _adicionar_mensagem(sessao, conversa, remetente, conteudo=None, usuario_id=None, tipo="texto", boleto=None):
    momento = agora()
    mensagem = Mensagem(
        conversa_id=conversa.id,
        remetente=remetente,
        usuario_id=usuario_id,
        tipo=tipo,
        conteudo=conteudo,
        enviada_em=momento,
    )
    if boleto:
        mensagem.url_boleto = boleto["url"]
        mensagem.valor_boleto = boleto["valor"]
        mensagem.vencimento_boleto = boleto["vencimento"]
    conversa.ultima_mensagem_em = momento
    sessao.add(mensagem)
    sessao.flush()
    return mensagem


def _adicionar_anexo(sessao, conversa, remetente, usuario_id, arquivo, legenda):
    nome, tipo_mime, dados = arquivo
    mensagem = _adicionar_mensagem(sessao, conversa, remetente, legenda or None, usuario_id=usuario_id, tipo="anexo")
    mensagem.anexo = Anexo(nome_arquivo=nome, tipo_mime=tipo_mime, tamanho=len(dados), dados=dados)
    sessao.flush()
    return mensagem


def _cliente_por_token(sessao, token: str) -> Cliente:
    cliente = sessao.scalar(select(Cliente).where(Cliente.token == (token or "")[:64]))
    if not cliente:
        raise ErroNegocio("Link inválido ou expirado", 404)
    return cliente


def _conversa_ativa(sessao, cliente_id: int):
    consulta = (
        select(Conversa)
        .where(Conversa.cliente_id == cliente_id, Conversa.status.in_(STATUS_ATIVOS))
        .order_by(Conversa.id.desc())
    )
    return sessao.scalars(consulta).unique().first()


def _pode_ler(conversa: Conversa, usuario: dict) -> bool:
    if usuario["perfil"] == "admin":
        return True
    return conversa.status in ("iniciada", "aguardando") or conversa.operador_id == usuario["id"]


def _carregar_conversa(sessao, conversa_id: int, usuario: dict) -> Conversa:
    conversa = sessao.get(Conversa, conversa_id)
    if not conversa or not _pode_ler(conversa, usuario):
        raise ErroNegocio("Conversa não encontrada", 404)
    return conversa


def _carregar_para_escrita(sessao, conversa_id: int, usuario: dict) -> Conversa:
    conversa = _carregar_conversa(sessao, conversa_id, usuario)
    if conversa.status == "encerrada":
        raise ErroNegocio("Esta conversa já foi encerrada", 409)
    if conversa.status != "em_atendimento" or conversa.operador_id != usuario["id"]:
        raise ErroNegocio("Assuma a conversa antes de enviar mensagens", 409)
    return conversa


def _converter_valor(valor) -> Decimal:
    try:
        convertido = Decimal(str(valor).strip().replace("R$", "").strip())
    except (InvalidOperation, ValueError):
        raise ErroNegocio("Valor inválido")
    if convertido <= 0 or convertido >= Decimal("10000000000"):
        raise ErroNegocio("Valor inválido")
    return convertido.quantize(Decimal("0.01"))


def _converter_data(valor) -> date:
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        raise ErroNegocio("Data inválida")


def _validar_boleto(boleto: dict, cliente: Cliente) -> dict:
    url = str(boleto.get("url") or "").strip()
    if not url_valida(url):
        raise ErroNegocio("Informe um link de boleto válido (http ou https)")
    valor = boleto.get("valor")
    vencimento = boleto.get("vencimento")
    return {
        "url": url,
        "valor": _converter_valor(valor) if valor not in (None, "") else cliente.valor_divida,
        "vencimento": _converter_data(vencimento) if vencimento else cliente.data_vencimento,
    }


def autenticar(matricula: str, senha: str) -> dict:
    matricula = (matricula or "").strip()
    if seguranca.matricula_bloqueada(matricula):
        raise ErroNegocio("Muitas tentativas inválidas. Aguarde 5 minutos.", 429)
    with abrir_sessao() as sessao:
        usuario = sessao.scalar(select(Usuario).where(Usuario.matricula == matricula))
        if not usuario or not usuario.ativo or not seguranca.verificar_senha(senha or "", usuario.senha_hash):
            seguranca.registrar_falha(matricula)
            raise ErroNegocio("Matrícula ou senha inválida", 401)
        seguranca.limpar_falhas(matricula)
        usuario.ultimo_acesso = agora()
        return {"token": seguranca.criar_token_acesso(usuario), "usuario": serializar_usuario(usuario)}


def abrir_atendimento_cliente(token: str) -> dict:
    with abrir_sessao() as sessao:
        cliente = _cliente_por_token(sessao, token)
        conversa = _conversa_ativa(sessao, cliente.id)
        nova = conversa is None
        if nova:
            momento = agora()
            conversa = Conversa(
                cliente_id=cliente.id,
                status="iniciada",
                iniciada_em=momento,
                ultima_mensagem_em=momento,
                retencao_ate=calcular_retencao(momento.date()),
            )
            sessao.add(conversa)
            sessao.flush()
            primeiro_nome = cliente.nome.split()[0].title()
            texto = MENSAGEM_BOAS_VINDAS.format(nome=primeiro_nome, empresa=configuracao.NOME_EMPRESA)
            _adicionar_mensagem(sessao, conversa, "sistema", texto)
        return {
            "empresa": configuracao.NOME_EMPRESA,
            "cliente": serializar_cliente(cliente, completo=False),
            "conversa": serializar_status_cliente(serializar_conversa(conversa)),
            "mensagens": _listar_mensagens(sessao, conversa.id),
        }


def conversa_ativa_do_cliente(token: str):
    with abrir_sessao() as sessao:
        cliente = _cliente_por_token(sessao, token)
        conversa = _conversa_ativa(sessao, cliente.id)
        return conversa.id if conversa else None


def registrar_mensagem_cliente(token: str, conteudo: str | None = None, arquivo=None):
    conteudo = (conteudo or "").strip()[:4000]
    if not conteudo and not arquivo:
        raise ErroNegocio("Mensagem vazia")
    with abrir_sessao() as sessao:
        cliente = _cliente_por_token(sessao, token)
        conversa = _conversa_ativa(sessao, cliente.id)
        if not conversa:
            raise ErroNegocio("Este atendimento foi encerrado", 409)
        if arquivo:
            mensagem = _adicionar_anexo(sessao, conversa, "cliente", None, arquivo, conteudo)
        else:
            mensagem = _adicionar_mensagem(sessao, conversa, "cliente", conteudo)
        mensagens = [serializar_mensagem(mensagem)]
        if conversa.status == "iniciada":
            conversa.assunto = (conteudo or f"Anexo: {arquivo[0]}")[:500]
            conversa.status = "aguardando"
            aviso = _adicionar_mensagem(sessao, conversa, "sistema", MENSAGEM_ASSUNTO_RECEBIDO)
            mensagens.append(serializar_mensagem(aviso))
        return conversa.id, mensagens, serializar_conversa(conversa, texto_previa(mensagem))


def registrar_mensagem_operador(conversa_id: int, usuario: dict, conteudo: str | None = None, boleto: dict | None = None):
    conteudo = (conteudo or "").strip()[:4000]
    with abrir_sessao() as sessao:
        conversa = _carregar_para_escrita(sessao, conversa_id, usuario)
        dados_boleto = _validar_boleto(boleto, conversa.cliente) if boleto else None
        if not dados_boleto and conteudo:
            restante, url = extrair_boleto(conteudo)
            if url:
                conteudo = restante
                dados_boleto = {
                    "url": url,
                    "valor": conversa.cliente.valor_divida,
                    "vencimento": conversa.cliente.data_vencimento,
                }
        if not conteudo and not dados_boleto:
            raise ErroNegocio("Mensagem vazia")
        mensagem = _adicionar_mensagem(
            sessao,
            conversa,
            "operador",
            conteudo or None,
            usuario_id=usuario["id"],
            tipo="boleto" if dados_boleto else "texto",
            boleto=dados_boleto,
        )
        return conversa.id, [serializar_mensagem(mensagem)], serializar_conversa(conversa, texto_previa(mensagem))


def registrar_anexo_operador(conversa_id: int, usuario: dict, arquivo, legenda: str | None = None):
    legenda = (legenda or "").strip()[:4000]
    with abrir_sessao() as sessao:
        conversa = _carregar_para_escrita(sessao, conversa_id, usuario)
        mensagem = _adicionar_anexo(sessao, conversa, "operador", usuario["id"], arquivo, legenda)
        return conversa.id, [serializar_mensagem(mensagem)], serializar_conversa(conversa, texto_previa(mensagem))


def assumir_conversa(conversa_id: int, usuario: dict):
    with abrir_sessao() as sessao:
        _carregar_conversa(sessao, conversa_id, usuario)
        resultado = sessao.execute(
            update(Conversa)
            .where(Conversa.id == conversa_id, Conversa.status.in_(("iniciada", "aguardando")))
            .values(status="em_atendimento", operador_id=usuario["id"], assumida_em=agora())
            .execution_options(synchronize_session=False)
        )
        if resultado.rowcount == 0:
            raise ErroNegocio("Esta conversa já foi assumida por outro operador ou encerrada", 409)
        sessao.expire_all()
        conversa = sessao.get(Conversa, conversa_id)
        aviso = _adicionar_mensagem(sessao, conversa, "sistema", MENSAGEM_ASSUMIDA.format(operador=usuario["nome"]))
        previa = _previas(sessao, [conversa.id]).get(conversa.id)
        return conversa.id, [serializar_mensagem(aviso)], serializar_conversa(conversa, previa)


def encerrar_conversa(conversa_id: int, usuario: dict):
    with abrir_sessao() as sessao:
        conversa = _carregar_conversa(sessao, conversa_id, usuario)
        if conversa.status == "encerrada":
            raise ErroNegocio("Esta conversa já foi encerrada", 409)
        if usuario["perfil"] != "admin" and conversa.operador_id != usuario["id"]:
            raise ErroNegocio("Somente o operador responsável pode encerrar esta conversa", 403)
        conversa.status = "encerrada"
        conversa.encerrada_em = agora()
        aviso = _adicionar_mensagem(sessao, conversa, "sistema", MENSAGEM_ENCERRADA)
        return conversa.id, [serializar_mensagem(aviso)], serializar_conversa(conversa)


def obter_conversa(conversa_id: int, usuario: dict) -> dict:
    with abrir_sessao() as sessao:
        conversa = _carregar_conversa(sessao, conversa_id, usuario)
        return {"conversa": serializar_conversa(conversa), "mensagens": _listar_mensagens(sessao, conversa.id)}


def listar_painel(usuario: dict) -> dict:
    with abrir_sessao() as sessao:
        fila = (
            sessao.scalars(select(Conversa).where(Conversa.status == "aguardando").order_by(Conversa.iniciada_em))
            .unique()
            .all()
        )
        meus = (
            sessao.scalars(
                select(Conversa)
                .where(Conversa.status == "em_atendimento", Conversa.operador_id == usuario["id"])
                .order_by(Conversa.ultima_mensagem_em.desc())
            )
            .unique()
            .all()
        )
        previas = _previas(sessao, [conversa.id for conversa in (*fila, *meus)])
        return {
            "fila": [serializar_conversa(conversa, previas.get(conversa.id)) for conversa in fila],
            "meus": [serializar_conversa(conversa, previas.get(conversa.id)) for conversa in meus],
        }


def listar_historico(usuario: dict, busca: str = "", status: str = "", data_inicio: str = "", data_fim: str = "", pagina: int = 1) -> dict:
    consulta = select(Conversa).join(Cliente, Conversa.cliente_id == Cliente.id)
    if usuario["perfil"] != "admin":
        consulta = consulta.where(Conversa.operador_id == usuario["id"])
    busca = (busca or "").strip()
    if busca:
        digitos = somente_digitos(busca)
        condicoes = [Cliente.nome.contains(busca), Cliente.credor.contains(busca), Conversa.assunto.contains(busca)]
        if digitos:
            condicoes += [Cliente.telefone.contains(digitos), Cliente.cpf.contains(digitos)]
        consulta = consulta.where(or_(*condicoes))
    if status in STATUS_VALIDOS:
        consulta = consulta.where(Conversa.status == status)
    if data_inicio:
        consulta = consulta.where(Conversa.iniciada_em >= datetime.combine(_converter_data(data_inicio), time.min))
    if data_fim:
        consulta = consulta.where(Conversa.iniciada_em <= datetime.combine(_converter_data(data_fim), time.max))
    pagina = max(int(pagina or 1), 1)
    with abrir_sessao() as sessao:
        total = sessao.scalar(select(func.count()).select_from(consulta.subquery()))
        conversas = (
            sessao.scalars(
                consulta.order_by(Conversa.id.desc()).offset((pagina - 1) * ITENS_POR_PAGINA).limit(ITENS_POR_PAGINA)
            )
            .unique()
            .all()
        )
        return {
            "itens": [serializar_conversa(conversa) for conversa in conversas],
            "total": total,
            "pagina": pagina,
            "paginas": max((total + ITENS_POR_PAGINA - 1) // ITENS_POR_PAGINA, 1),
        }


def obter_anexo_cliente(token: str, anexo_id: int):
    with abrir_sessao() as sessao:
        cliente = _cliente_por_token(sessao, token)
        anexo = sessao.get(Anexo, anexo_id)
        if not anexo or sessao.get(Conversa, anexo.mensagem.conversa_id).cliente_id != cliente.id:
            raise ErroNegocio("Anexo não encontrado", 404)
        return anexo.nome_arquivo, anexo.tipo_mime, anexo.dados


def obter_anexo_usuario(usuario: dict, anexo_id: int):
    with abrir_sessao() as sessao:
        anexo = sessao.get(Anexo, anexo_id)
        if not anexo:
            raise ErroNegocio("Anexo não encontrado", 404)
        _carregar_conversa(sessao, anexo.mensagem.conversa_id, usuario)
        return anexo.nome_arquivo, anexo.tipo_mime, anexo.dados


def _validar_matricula(matricula: str) -> str:
    matricula = (matricula or "").strip()
    if len(matricula) != 4 or not matricula.isdigit():
        raise ErroNegocio("A matrícula deve ter exatamente 4 números")
    return matricula


def _validar_senha(senha: str) -> str:
    if not senha or len(senha) < 6:
        raise ErroNegocio("A senha deve ter pelo menos 6 caracteres")
    return senha


def listar_usuarios() -> list[dict]:
    with abrir_sessao() as sessao:
        return [serializar_usuario(usuario) for usuario in sessao.scalars(select(Usuario).order_by(Usuario.matricula))]


def criar_usuario(dados: dict) -> dict:
    matricula = _validar_matricula(dados.get("matricula"))
    nome = (dados.get("nome") or "").strip()[:120]
    perfil = dados.get("perfil") or "operador"
    if not nome:
        raise ErroNegocio("Informe o nome do operador")
    if perfil not in PERFIS:
        raise ErroNegocio("Perfil inválido")
    senha = _validar_senha(dados.get("senha"))
    with abrir_sessao() as sessao:
        if sessao.scalar(select(Usuario).where(Usuario.matricula == matricula)):
            raise ErroNegocio("Já existe um usuário com esta matrícula", 409)
        usuario = Usuario(
            matricula=matricula,
            nome=nome,
            perfil=perfil,
            ativo=True,
            senha_hash=seguranca.gerar_hash_senha(senha),
            criado_em=agora(),
        )
        sessao.add(usuario)
        sessao.flush()
        return serializar_usuario(usuario)


def atualizar_usuario(administrador: dict, usuario_id: int, dados: dict) -> dict:
    with abrir_sessao() as sessao:
        usuario = sessao.get(Usuario, usuario_id)
        if not usuario:
            raise ErroNegocio("Usuário não encontrado", 404)
        if dados.get("nome"):
            usuario.nome = dados["nome"].strip()[:120]
        if dados.get("perfil"):
            if dados["perfil"] not in PERFIS:
                raise ErroNegocio("Perfil inválido")
            if usuario.id == administrador["id"] and dados["perfil"] != "admin":
                raise ErroNegocio("Você não pode remover o seu próprio perfil de administrador")
            usuario.perfil = dados["perfil"]
        if dados.get("ativo") is not None:
            if usuario.id == administrador["id"] and not dados["ativo"]:
                raise ErroNegocio("Você não pode desativar o seu próprio usuário")
            usuario.ativo = bool(dados["ativo"])
        if dados.get("senha"):
            usuario.senha_hash = seguranca.gerar_hash_senha(_validar_senha(dados["senha"]))
            seguranca.limpar_falhas(usuario.matricula)
        return serializar_usuario(usuario)


def _validar_cliente(dados: dict) -> dict:
    nome = (dados.get("nome") or "").strip()[:150]
    credor = (dados.get("credor") or "").strip()[:150]
    telefone = somente_digitos(dados.get("telefone"))
    cpf = somente_digitos(dados.get("cpf")) or None
    if not nome:
        raise ErroNegocio("Informe o nome do cliente")
    if not credor:
        raise ErroNegocio("Informe o credor")
    if not 10 <= len(telefone) <= 13:
        raise ErroNegocio("Telefone inválido")
    if cpf and len(cpf) != 11:
        raise ErroNegocio("CPF inválido")
    return {
        "nome": nome,
        "credor": credor,
        "telefone": telefone,
        "cpf": cpf,
        "valor_divida": _converter_valor(dados.get("valor_divida")),
        "data_vencimento": _converter_data(dados.get("data_vencimento")),
    }


def listar_clientes(busca: str = "") -> list[dict]:
    consulta = select(Cliente).order_by(Cliente.id.desc()).limit(200)
    busca = (busca or "").strip()
    if busca:
        digitos = somente_digitos(busca)
        condicoes = [Cliente.nome.contains(busca), Cliente.credor.contains(busca)]
        if digitos:
            condicoes += [Cliente.telefone.contains(digitos), Cliente.cpf.contains(digitos)]
        consulta = consulta.where(or_(*condicoes))
    with abrir_sessao() as sessao:
        return [serializar_cliente(cliente) for cliente in sessao.scalars(consulta)]


def salvar_cliente(dados: dict, reaproveitar: bool = False) -> dict:
    validados = _validar_cliente(dados)
    with abrir_sessao() as sessao:
        cliente = None
        if reaproveitar:
            cliente = sessao.scalar(
                select(Cliente).where(
                    Cliente.telefone == validados["telefone"], Cliente.credor == validados["credor"]
                )
            )
        if cliente:
            for campo, valor in validados.items():
                setattr(cliente, campo, valor)
            cliente.atualizado_em = agora()
        else:
            momento = agora()
            cliente = Cliente(**validados, token=seguranca.gerar_token_cliente(), criado_em=momento, atualizado_em=momento)
            sessao.add(cliente)
        sessao.flush()
        return serializar_cliente(cliente)


def atualizar_cliente(cliente_id: int, dados: dict) -> dict:
    validados = _validar_cliente(dados)
    with abrir_sessao() as sessao:
        cliente = sessao.get(Cliente, cliente_id)
        if not cliente:
            raise ErroNegocio("Cliente não encontrado", 404)
        for campo, valor in validados.items():
            setattr(cliente, campo, valor)
        cliente.atualizado_em = agora()
        return serializar_cliente(cliente)
