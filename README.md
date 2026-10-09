# MJChat

Live chat para atendimento de cobrança. O cliente recebe pelo WhatsApp (via Kapso) uma mensagem com um botão de link; ao tocar, abre o chat no navegador do próprio WhatsApp e conversa com um operador, sem custo de conversa da Meta.

- **Backend:** Python (FastAPI) + Socket.IO (`python-socketio`)
- **Frontend:** HTML, CSS e JavaScript puro, com o cliente Socket.IO
- **Banco:** SQL Server (`192.168.1.220`, banco `MJChat`)

## Funcionalidades

- Chat em tempo real entre operador e cliente (Socket.IO, com fallback para long-polling em redes ruins).
- Ao abrir o link, o cliente recebe uma mensagem automática pedindo o assunto e para aguardar um operador. A primeira mensagem dele vira o assunto e a conversa entra na fila.
- O operador vê na fila e na ficha do cliente: **nome, credor, telefone, valor devido e vencimento**.
- Envio de anexos e fotos pelos dois lados (JPG, PNG, GIF, WEBP, PDF, DOC/DOCX, XLS/XLSX, TXT; até 10 MB).
- **Boleto formatado:** link extenso ou link de boleto enviado pelo operador vira um cartão com credor, valor, vencimento e os botões "Abrir boleto" e "Copiar link". Também existe o botão **Enviar boleto**, para informar link, valor e vencimento.
- Operadores identificados por **matrícula de 4 números**. A senha é definida pelo administrador, guardada com hash bcrypt e nunca mais exibida. O operador não consegue trocar a senha.
- **Confirmação de leitura:** cada mensagem mostra ✓ enviada, ✓✓ cinza entregue (chegou ao aparelho) e ✓✓ azul lida (a tela estava aberta e visível). Passando o mouse aparecem os horários. Do lado do cliente, só conta como lida quando o operador responsável pela conversa abre a conversa. As confirmações ficam na tabela `confirmacoes_mensagens` e seguem a mesma retenção de 5 anos.
- **Online / visto por último:** o operador vê se o cliente está online ou "visto por último hoje às 15:30" (na ficha e com um ponto verde na lista). O cliente vê o mesmo do operador que o atende. O administrador vê na lista de operadores quem está online.
- Painel do administrador: cadastrar e desativar operadores, redefinir senhas, cadastrar clientes e gerar links, consultar o histórico de conversas.
- **Retenção legal de 5 anos:** cada conversa grava `retencao_ate`, o sistema não tem nenhuma função de exclusão e triggers no SQL Server bloqueiam `DELETE` de conversas, mensagens e anexos dentro do prazo e qualquer `UPDATE` em mensagens e anexos. Os anexos ficam dentro do banco (`VARBINARY(MAX)`), então entram no mesmo backup.

## Instalação

Requisitos: Python 3.11 ou superior e o [Microsoft ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server).

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # Linux
pip install -r requirements.txt
copy .env.exemplo .env            # Windows (Linux: cp .env.exemplo .env)
```

Edite o `backend/.env` com o usuário e a senha do SQL Server e gere chaves aleatórias para `CHAVE_SECRETA` e `CHAVE_INTEGRACAO`. Por exemplo: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Se `USUARIO_BANCO` ficar vazio, a conexão usa a autenticação integrada do Windows.

### Criar o banco e os dados fictícios

```bash
python scripts/inicializar_banco.py
```

O script executa `banco/criar_banco.sql` no servidor `192.168.1.220`, criando o banco `MJChat`, as tabelas e os triggers. Depois insere os dados de teste e imprime os links dos clientes. O usuário do banco precisa de permissão para criar banco. Se não tiver, peça ao DBA para rodar `banco/criar_banco.sql` no SSMS e execute o script Python depois disso: ele só vai inserir os dados.

### Rodar

```bash
uvicorn app.principal:aplicacao --host 0.0.0.0 --port 8000
```

- Operadores: `http://servidor:8000/login`
- Administração: `http://servidor:8000/admin`
- Cliente: `http://servidor:8000/c/<token>`

Para os clientes acessarem pela internet, publique o sistema atrás de um proxy reverso com HTTPS (IIS, nginx ou Cloudflare Tunnel), encaminhando também o WebSocket do caminho `/socket.io/`, e ajuste `URL_PUBLICA` no `.env`. Use um único processo do uvicorn: com vários workers seria necessário um gerenciador de mensagens (Redis) para o Socket.IO.

## Dados de teste

| Matrícula | Senha | Perfil |
|---|---|---|
| 0001 | Admin@2026 | Administrador |
| 1001 | Operador@1001 | Operador (Ana Paula Ribeiro) |
| 1002 | Operador@1002 | Operador (Bruno Carvalho Lima) |
| 1003 | Operador@1003 | Operador (Camila Duarte Souza) |

O script também cria 6 clientes fictícios (Banco Horizonte, Loja Estrela Magazine, Conecta Telecom, Financeira Prisma, Universidade Aurora e Cartão Vértice), uma conversa já encerrada com boleto no histórico e uma conversa aguardando na fila. Os links dos clientes são impressos no terminal e também aparecem em **Administração > Clientes > Copiar link**.

Roteiro sugerido:

1. Entre com `1001` em uma janela e abra o link de um cliente em outra (ou no celular).
2. Escreva o assunto como cliente. A conversa aparece na fila do operador.
3. Assuma a conversa, troque mensagens, envie fotos e PDFs dos dois lados.
4. Cole um link longo de boleto ou use **Enviar boleto** para ver o cartão formatado.
5. Encerre a conversa e confira em **Administração > Conversas**.

Antes de ir para produção, troque as senhas de teste ou apague os dados fictícios do banco.

## Integração com o Kapso

1. Antes de disparar a mensagem, gere o link do cliente:

```http
POST /api/integracao/links
X-Chave-Integracao: <CHAVE_INTEGRACAO>
Content-Type: application/json

{
  "nome": "Maria Aparecida dos Santos",
  "cpf": "11122233396",
  "telefone": "5511987654321",
  "credor": "Banco Horizonte S.A.",
  "valor_divida": "1847.90",
  "data_vencimento": "2026-10-21"
}
```

Resposta: `{"token": "...", "link": "https://chat.suaempresa.com.br/c/...", "cliente_id": 1}`. Se o mesmo telefone e credor já existirem, os dados são atualizados e o link é mantido.

2. No template do WhatsApp aprovado na Meta, use um botão de URL dinâmica `https://chat.suaempresa.com.br/c/{{1}}` e envie o `token` como variável.

A documentação interativa da API fica em `/api/documentacao`.

### Enviar o botão pelo WhatsApp (script)

Preencha no `backend/.env`:

```
KAPSO_API_KEY=<chave da Kapso>
KAPSO_ID_NUMERO=1087358919742996
```

Exemplos (dentro da pasta `backend`):

```bash
python scripts/enviar_botao_kapso.py --para 5511987654321 --cliente-id 1
python scripts/enviar_botao_kapso.py --para 5511987654321 --link https://chat.suaempresa.com.br/c/TOKEN
python scripts/enviar_botao_kapso.py --para 5511987654321 --cliente-id 1 --template atendimento_chat --parametro Maria
python scripts/enviar_botao_kapso.py --para 5511987654321 --cliente-id 1 --simular
```

- Sem `--template`, o script envia uma mensagem interativa com botão de link (`cta_url`). A Meta só aceita esse tipo dentro da janela de 24 horas, ou seja, depois que o cliente mandou alguma mensagem para o número.
- Com `--template`, envia um template aprovado cujo botão de URL termina em `{{1}}` (`https://chat.suaempresa.com.br/c/{{1}}`). O script coloca o token do cliente nessa variável. Funciona a qualquer momento.
- Sem `--cliente-id` e sem `--link`, o script procura o cliente cadastrado com o telefone de destino.
- `--simular` mostra a mensagem que seria enviada, sem enviar.

## Estrutura

```
banco/criar_banco.sql            script do SQL Server (tabelas, índices e triggers de retenção)
backend/app/principal.py         aplicação FastAPI + Socket.IO
backend/app/servico.py           regras de negócio
backend/app/eventos.py           eventos em tempo real (Socket.IO)
backend/app/rotas/               rotas HTTP (cliente, atendimento, administração, integração)
backend/scripts/inicializar_banco.py  criação do banco e dados fictícios
frontend/                        páginas e scripts do cliente, operador e administrador
```
