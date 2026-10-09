import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_, select

from app import configuracao, kapso
from app.banco import abrir_sessao
from app.modelos import Cliente
from app.servico import link_cliente
from app.utilitarios import somente_digitos

TEXTO_COM_CLIENTE = (
    "Olá, {nome}! Aqui é a {empresa}. "
    "Para conversar com a nossa equipe sobre o seu débito com {credor}, toque no botão abaixo."
)
TEXTO_SEM_CLIENTE = "Olá! Aqui é a {empresa}. Toque no botão abaixo para falar com a nossa equipe de atendimento."
ENDERECOS_INTERNOS = ("localhost", "127.0.0.1", "192.168.", "10.0.")


def ler_argumentos():
    leitor = argparse.ArgumentParser(description="Envia pelo WhatsApp (Kapso) um botão com o link do chat de atendimento.")
    leitor.add_argument("--para", required=True, help="WhatsApp de destino com DDI e DDD, ex.: 5511987654321")
    leitor.add_argument("--cliente-id", type=int, help="Cliente do MJChat cujo link será enviado")
    leitor.add_argument("--link", help="Link a enviar no botão, no lugar do link de um cliente")
    leitor.add_argument("--mensagem", help="Texto da mensagem acima do botão")
    leitor.add_argument("--texto-botao", default="Abrir atendimento", help="Texto do botão (até 20 caracteres)")
    leitor.add_argument("--template", help="Nome do template aprovado com botão de URL dinâmica (envio fora da janela de 24h)")
    leitor.add_argument("--idioma", default="pt_BR", help="Idioma do template")
    leitor.add_argument("--parametro", action="append", default=[], help="Variável do corpo do template, na ordem (repita a opção)")
    leitor.add_argument("--simular", action="store_true", help="Somente mostra a mensagem, sem enviar")
    return leitor.parse_args()


def buscar_cliente(cliente_id, numero):
    with abrir_sessao() as sessao:
        if cliente_id:
            cliente = sessao.get(Cliente, cliente_id)
            if not cliente:
                raise kapso.ErroKapso(f"Cliente {cliente_id} não encontrado")
        else:
            variantes = {numero, numero[2:] if numero.startswith("55") else numero}
            cliente = sessao.scalars(
                select(Cliente).where(or_(*(Cliente.telefone == variante for variante in variantes))).order_by(Cliente.id.desc())
            ).first()
        if not cliente:
            return None
        return {
            "nome": cliente.nome.split()[0].title(),
            "credor": cliente.credor,
            "link": link_cliente(cliente),
            "token": cliente.token,
        }


def montar_mensagem(argumentos):
    numero = kapso.normalizar_numero(argumentos.para)
    cliente = None if argumentos.link else buscar_cliente(argumentos.cliente_id, somente_digitos(numero))
    if not argumentos.link and not cliente:
        raise kapso.ErroKapso(
            "Nenhum cliente cadastrado com este telefone. Informe --cliente-id (veja Administração > Clientes) ou --link."
        )
    link = argumentos.link or cliente["link"]
    if any(trecho in link for trecho in ENDERECOS_INTERNOS):
        print(f"Atenção: o link {link} só abre dentro da rede da empresa. Ajuste URL_PUBLICA no .env para o endereço público.")
    if argumentos.template:
        token = cliente["token"] if cliente else link.rstrip("/").rsplit("/", 1)[-1]
        return kapso.montar_template_com_botao(numero, argumentos.template, argumentos.idioma, token, argumentos.parametro)
    if argumentos.mensagem:
        texto = argumentos.mensagem
    elif cliente:
        texto = TEXTO_COM_CLIENTE.format(nome=cliente["nome"], empresa=configuracao.NOME_EMPRESA, credor=cliente["credor"])
    else:
        texto = TEXTO_SEM_CLIENTE.format(empresa=configuracao.NOME_EMPRESA)
    return kapso.montar_botao_link(
        numero, texto, argumentos.texto_botao, link, cabecalho=configuracao.NOME_EMPRESA, rodape="Atendimento online"
    )


def principal():
    argumentos = ler_argumentos()
    try:
        mensagem = montar_mensagem(argumentos)
        if argumentos.simular:
            print(f"POST {kapso.endereco_envio()}")
            print(json.dumps(mensagem, ensure_ascii=False, indent=2))
            return 0
        resposta = kapso.enviar(mensagem)
    except kapso.ErroKapso as erro:
        print(f"Erro: {erro}")
        if not argumentos.template and "131047" in str(erro):
            print("O destinatário está fora da janela de 24 horas. Peça para ele enviar uma mensagem ao número ou use --template.")
        return 1
    identificador = (resposta.get("messages") or [{}])[0].get("id", "-")
    print(f"Mensagem enviada para {mensagem['to']}. Identificador: {identificador}")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
