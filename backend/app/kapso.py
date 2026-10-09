import json
import urllib.error
import urllib.request

from app import configuracao
from app.utilitarios import somente_digitos


class ErroKapso(Exception):
    pass


def normalizar_numero(numero: str) -> str:
    digitos = somente_digitos(numero)
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    if not 12 <= len(digitos) <= 15:
        raise ErroKapso("Número de WhatsApp inválido. Use DDI + DDD + número, ex.: 5511987654321")
    return digitos


def montar_botao_link(numero: str, texto: str, texto_botao: str, link: str, cabecalho: str = "", rodape: str = "") -> dict:
    interativo = {
        "type": "cta_url",
        "body": {"text": texto[:1024]},
        "action": {"name": "cta_url", "parameters": {"display_text": texto_botao[:20], "url": link}},
    }
    if cabecalho:
        interativo["header"] = {"type": "text", "text": cabecalho[:60]}
    if rodape:
        interativo["footer"] = {"text": rodape[:60]}
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": normalizar_numero(numero),
        "type": "interactive",
        "interactive": interativo,
    }


def montar_template_com_botao(numero: str, template: str, idioma: str, token: str, parametros_corpo=()) -> dict:
    componentes = []
    if parametros_corpo:
        componentes.append(
            {"type": "body", "parameters": [{"type": "text", "text": parametro} for parametro in parametros_corpo]}
        )
    componentes.append(
        {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": token}]}
    )
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": normalizar_numero(numero),
        "type": "template",
        "template": {"name": template, "language": {"code": idioma}, "components": componentes},
    }


def endereco_envio() -> str:
    return f"{configuracao.KAPSO_URL_BASE}/{configuracao.KAPSO_VERSAO_GRAPH}/{configuracao.KAPSO_ID_NUMERO}/messages"


def enviar(mensagem: dict) -> dict:
    if not configuracao.KAPSO_API_KEY:
        raise ErroKapso("Defina KAPSO_API_KEY no arquivo backend/.env")
    if not configuracao.KAPSO_ID_NUMERO:
        raise ErroKapso("Defina KAPSO_ID_NUMERO no arquivo backend/.env")
    requisicao = urllib.request.Request(
        endereco_envio(),
        data=json.dumps(mensagem).encode("utf-8"),
        method="POST",
        headers={"X-API-Key": configuracao.KAPSO_API_KEY, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=30) as resposta:
            return json.loads(resposta.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as erro:
        corpo = erro.read().decode("utf-8", errors="replace")
        try:
            detalhe = json.loads(corpo).get("error") or corpo
        except ValueError:
            detalhe = corpo
        if isinstance(detalhe, dict):
            detalhe = " ".join(str(detalhe.get(campo)) for campo in ("code", "message") if detalhe.get(campo))
        raise ErroKapso(f"A Kapso respondeu {erro.code}: {detalhe}")
    except urllib.error.URLError as erro:
        raise ErroKapso(f"Não foi possível conectar à Kapso: {erro.reason}")
