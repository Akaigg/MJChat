import re
from datetime import date
from pathlib import PurePath

from app import configuracao

PADRAO_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
PALAVRAS_BOLETO = ("boleto", "fatura", "2via", "segunda-via", "segundavia", "linhadigitavel", ".pdf")
TAMANHO_LINK_EXTENSO = 60

TIPOS_PERMITIDOS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def calcular_retencao(inicio: date) -> date:
    try:
        return inicio.replace(year=inicio.year + configuracao.ANOS_RETENCAO)
    except ValueError:
        return inicio.replace(year=inicio.year + configuracao.ANOS_RETENCAO, day=28)


def eh_link_de_boleto(url: str) -> bool:
    minusculo = url.lower()
    return len(url) >= TAMANHO_LINK_EXTENSO or any(palavra in minusculo for palavra in PALAVRAS_BOLETO)


def extrair_boleto(texto: str):
    for encontrado in PADRAO_URL.findall(texto or ""):
        url = encontrado.rstrip(".,;:!?)]}")
        if eh_link_de_boleto(url):
            restante = re.sub(r"\s{2,}", " ", texto.replace(url, " ")).strip()
            return restante, url
    return texto, None


def url_valida(url: str) -> bool:
    return bool(url) and len(url) <= 2000 and PADRAO_URL.fullmatch(url.strip()) is not None


def identificar_arquivo(nome: str):
    nome_limpo = PurePath((nome or "arquivo").replace("\\", "/")).name.strip()[:200] or "arquivo"
    extensao = PurePath(nome_limpo).suffix.lower()
    return nome_limpo, TIPOS_PERMITIDOS.get(extensao)


def somente_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")
