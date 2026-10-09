import re
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app import configuracao
from app.banco import Base, abrir_sessao, criar_motor, motor, usa_sql_server
from app.modelos import Cliente, ConfirmacaoMensagem, Conversa, Mensagem, Usuario, agora
from app.seguranca import gerar_hash_senha, gerar_token_cliente
from app.servico import (
    MENSAGEM_ASSUMIDA,
    MENSAGEM_ASSUNTO_RECEBIDO,
    MENSAGEM_BOAS_VINDAS,
    MENSAGEM_ENCERRADA,
    link_cliente,
)
from app.utilitarios import calcular_retencao

USUARIOS_TESTE = [
    ("0001", "Administrador do Sistema", "admin", "Admin@2026"),
    ("1001", "Ana Paula Ribeiro", "operador", "Operador@1001"),
    ("1002", "Bruno Carvalho Lima", "operador", "Operador@1002"),
    ("1003", "Camila Duarte Souza", "operador", "Operador@1003"),
]

CLIENTES_TESTE = [
    ("Maria Aparecida dos Santos", "11122233396", "11987654321", "Banco Horizonte S.A.", "1847.90", 12),
    ("José Roberto Almeida", "22233344405", "21998765432", "Loja Estrela Magazine", "629.45", -20),
    ("Fernanda Oliveira Costa", "33344455514", "31991234567", "Conecta Telecom", "312.18", -45),
    ("Carlos Eduardo Pereira", "44455566623", "41996543210", "Financeira Prisma", "5230.00", 5),
    ("Luciana Martins Rocha", "55566677732", "51993456789", "Universidade Aurora", "2140.75", -90),
    ("Ricardo Gomes Ferreira", "66677788841", "61992345678", "Cartão Vértice", "978.30", 30),
]


def executar_script_sql():
    script = configuracao.ARQUIVO_SQL.read_text(encoding="utf-8")
    script = script.replace("N'MJChat'", f"N'{configuracao.NOME_BANCO}'")
    script = script.replace("DATABASE MJChat", f"DATABASE [{configuracao.NOME_BANCO}]")
    script = script.replace("USE MJChat", f"USE [{configuracao.NOME_BANCO}]")
    lotes = [lote.strip() for lote in re.split(r"^\s*GO\s*$", script, flags=re.MULTILINE | re.IGNORECASE)]
    motor_mestre = criar_motor("master", isolation_level="AUTOCOMMIT")
    with motor_mestre.connect() as conexao:
        for lote in lotes:
            if lote:
                conexao.exec_driver_sql(lote)
    motor_mestre.dispose()


def criar_estrutura():
    if usa_sql_server():
        executar_script_sql()
    else:
        Base.metadata.create_all(motor)


def adicionar_mensagem(sessao, conversa, remetente, conteudo, momento, usuario=None, boleto=None):
    mensagem = Mensagem(
        conversa_id=conversa.id,
        remetente=remetente,
        usuario_id=usuario.id if usuario else None,
        tipo="boleto" if boleto else "texto",
        conteudo=conteudo,
        enviada_em=momento,
    )
    if boleto:
        mensagem.url_boleto, mensagem.valor_boleto, mensagem.vencimento_boleto = boleto
    conversa.ultima_mensagem_em = momento
    sessao.add(mensagem)
    sessao.flush()
    return mensagem


def confirmar_leitura(sessao, mensagem, leitor=None):
    for tipo, segundos in (("entregue", 5), ("lida", 40)):
        sessao.add(
            ConfirmacaoMensagem(
                mensagem_id=mensagem.id,
                tipo=tipo,
                usuario_id=leitor.id if leitor else None,
                registrada_em=mensagem.enviada_em + timedelta(seconds=segundos),
            )
        )


def popular_dados():
    with abrir_sessao() as sessao:
        if sessao.scalar(select(Usuario).limit(1)):
            print("O banco já possui dados. Nenhum dado fictício foi inserido.")
            return False
        momento = agora()
        usuarios = {}
        for matricula, nome, perfil, senha in USUARIOS_TESTE:
            usuario = Usuario(
                matricula=matricula,
                nome=nome,
                perfil=perfil,
                ativo=True,
                senha_hash=gerar_hash_senha(senha),
                criado_em=momento,
            )
            sessao.add(usuario)
            usuarios[matricula] = usuario
        clientes = []
        for nome, cpf, telefone, credor, valor, dias in CLIENTES_TESTE:
            cliente = Cliente(
                nome=nome,
                cpf=cpf,
                telefone=telefone,
                credor=credor,
                valor_divida=Decimal(valor),
                data_vencimento=date.today() + timedelta(days=dias),
                token=gerar_token_cliente(),
                criado_em=momento,
                atualizado_em=momento,
            )
            sessao.add(cliente)
            clientes.append(cliente)
        sessao.flush()

        inicio = momento - timedelta(days=3)
        encerrada = Conversa(
            cliente_id=clientes[1].id,
            operador_id=usuarios["1001"].id,
            status="encerrada",
            assunto="Gostaria de negociar a minha dívida",
            iniciada_em=inicio,
            assumida_em=inicio + timedelta(minutes=2),
            encerrada_em=inicio + timedelta(minutes=15),
            ultima_mensagem_em=inicio,
            retencao_ate=calcular_retencao(inicio.date()),
        )
        sessao.add(encerrada)
        sessao.flush()
        operadora = usuarios["1001"]
        roteiro = [
            ("sistema", MENSAGEM_BOAS_VINDAS.format(nome="José", empresa=configuracao.NOME_EMPRESA), None, None),
            ("cliente", "Gostaria de negociar a minha dívida", None, None),
            ("sistema", MENSAGEM_ASSUMIDA.format(operador=operadora.nome), None, None),
            ("operador", "Olá, José! Posso te ajudar. Consigo um desconto de 15% para pagamento à vista.", operadora, None),
            ("cliente", "Ótimo, pode me enviar o boleto?", None, None),
            (
                "operador",
                "Segue o boleto atualizado com o desconto:",
                operadora,
                (
                    "https://boletos.exemplo.com.br/2via/emitir?documento=00190500954014481606906809350314337370000000100&credor=estrela",
                    Decimal("535.03"),
                    date.today() + timedelta(days=2),
                ),
            ),
            ("cliente", "Recebido, obrigado!", None, None),
            ("sistema", MENSAGEM_ENCERRADA, None, None),
        ]
        for indice, (remetente, texto, usuario, boleto) in enumerate(roteiro):
            momento_mensagem = inicio + timedelta(minutes=indice * 2)
            mensagem = adicionar_mensagem(sessao, encerrada, remetente, texto, momento_mensagem, usuario, boleto)
            if remetente == "cliente":
                confirmar_leitura(sessao, mensagem, operadora)
            elif remetente == "operador":
                confirmar_leitura(sessao, mensagem)
        clientes[1].visto_por_ultimo = inicio + timedelta(minutes=16)
        operadora.visto_por_ultimo = inicio + timedelta(minutes=20)

        aguardando = Conversa(
            cliente_id=clientes[2].id,
            status="aguardando",
            assunto="Recebi uma cobrança que não reconheço",
            iniciada_em=momento - timedelta(minutes=6),
            ultima_mensagem_em=momento,
            retencao_ate=calcular_retencao(momento.date()),
        )
        sessao.add(aguardando)
        sessao.flush()
        adicionar_mensagem(
            sessao,
            aguardando,
            "sistema",
            MENSAGEM_BOAS_VINDAS.format(nome="Fernanda", empresa=configuracao.NOME_EMPRESA),
            momento - timedelta(minutes=6),
        )
        adicionar_mensagem(sessao, aguardando, "cliente", "Recebi uma cobrança que não reconheço", momento - timedelta(minutes=5))
        adicionar_mensagem(
            sessao,
            aguardando,
            "sistema",
            MENSAGEM_ASSUNTO_RECEBIDO,
            momento - timedelta(minutes=5),
        )

        print("\nUsuários de teste (matrícula / senha):")
        for matricula, nome, perfil, senha in USUARIOS_TESTE:
            print(f"  {matricula} / {senha}  ->  {nome} ({perfil})")
        print("\nLinks de teste dos clientes:")
        for cliente in clientes:
            print(f"  {cliente.nome} ({cliente.credor}): {link_cliente(cliente)}")
        return True


if __name__ == "__main__":
    criar_estrutura()
    print("Estrutura do banco criada/verificada.")
    popular_dados()
