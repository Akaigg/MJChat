import os
from pathlib import Path

from dotenv import load_dotenv

PASTA_BACKEND = Path(__file__).resolve().parent.parent
PASTA_PROJETO = PASTA_BACKEND.parent
PASTA_FRONTEND = PASTA_PROJETO / "frontend"
ARQUIVO_SQL = PASTA_PROJETO / "banco" / "criar_banco.sql"

load_dotenv(PASTA_BACKEND / ".env")

URL_BANCO = os.getenv("URL_BANCO", "")
SERVIDOR_BANCO = os.getenv("SERVIDOR_BANCO", "192.168.1.220")
PORTA_BANCO = int(os.getenv("PORTA_BANCO", "1433"))
NOME_BANCO = os.getenv("NOME_BANCO", "MJChat")
USUARIO_BANCO = os.getenv("USUARIO_BANCO", "")
SENHA_BANCO = os.getenv("SENHA_BANCO", "")
DRIVER_ODBC = os.getenv("DRIVER_ODBC", "ODBC Driver 18 for SQL Server")

CHAVE_SECRETA = os.getenv("CHAVE_SECRETA", "")
CHAVE_INTEGRACAO = os.getenv("CHAVE_INTEGRACAO", "")
URL_PUBLICA = os.getenv("URL_PUBLICA", "http://localhost:8000").rstrip("/")
NOME_EMPRESA = os.getenv("NOME_EMPRESA", "MJ Cobranças")
FUSO_HORARIO = os.getenv("FUSO_HORARIO", "America/Sao_Paulo")
HORAS_SESSAO = int(os.getenv("HORAS_SESSAO", "12"))
TAMANHO_MAXIMO_ANEXO = int(os.getenv("TAMANHO_MAXIMO_ANEXO_MB", "10")) * 1024 * 1024
ANOS_RETENCAO = 5

KAPSO_API_KEY = os.getenv("KAPSO_API_KEY", "")
KAPSO_ID_NUMERO = os.getenv("KAPSO_ID_NUMERO", "")
KAPSO_URL_BASE = os.getenv("KAPSO_URL_BASE", "https://api.kapso.ai/meta/whatsapp").rstrip("/")
KAPSO_VERSAO_GRAPH = os.getenv("KAPSO_VERSAO_GRAPH", "v23.0")

if len(CHAVE_SECRETA) < 16:
    raise RuntimeError("Defina CHAVE_SECRETA no arquivo backend/.env com pelo menos 16 caracteres")
