from urllib.parse import quote

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response

from app import configuracao, servico
from app.utilitarios import identificar_arquivo

TIPOS_EXIBIDOS = ("image/", "application/pdf", "text/plain")


def erro_http(erro: servico.ErroNegocio) -> HTTPException:
    return HTTPException(status_code=erro.codigo, detail=erro.mensagem)


async def ler_arquivo(arquivo: UploadFile):
    nome, tipo_mime = identificar_arquivo(arquivo.filename)
    if not tipo_mime:
        raise HTTPException(status_code=415, detail="Tipo de arquivo não permitido. Envie fotos, PDF, Word, Excel ou TXT.")
    dados = await arquivo.read(configuracao.TAMANHO_MAXIMO_ANEXO + 1)
    if not dados:
        raise HTTPException(status_code=400, detail="Arquivo vazio")
    if len(dados) > configuracao.TAMANHO_MAXIMO_ANEXO:
        limite = configuracao.TAMANHO_MAXIMO_ANEXO // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"O arquivo ultrapassa o limite de {limite} MB")
    return nome, tipo_mime, dados


def resposta_arquivo(nome: str, tipo_mime: str, dados: bytes) -> Response:
    disposicao = "inline" if tipo_mime.startswith(TIPOS_EXIBIDOS) else "attachment"
    return Response(
        content=dados,
        media_type=tipo_mime,
        headers={
            "Content-Disposition": f"{disposicao}; filename*=UTF-8''{quote(nome)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )
