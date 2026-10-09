import secrets
import string
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException

from app import configuracao
from app.banco import abrir_sessao
from app.modelos import Usuario

ALGORITMO = "HS256"
LIMITE_TENTATIVAS = 5
SEGUNDOS_BLOQUEIO = 300

tentativas_falhas: dict[str, list[float]] = {}


def gerar_hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except ValueError:
        return False


def gerar_senha_aleatoria(tamanho: int = 10) -> str:
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


def gerar_token_cliente() -> str:
    return secrets.token_urlsafe(24)


def matricula_bloqueada(matricula: str) -> bool:
    limite = time.monotonic() - SEGUNDOS_BLOQUEIO
    recentes = [momento for momento in tentativas_falhas.get(matricula, []) if momento > limite]
    tentativas_falhas[matricula] = recentes
    return len(recentes) >= LIMITE_TENTATIVAS


def registrar_falha(matricula: str):
    tentativas_falhas.setdefault(matricula, []).append(time.monotonic())


def limpar_falhas(matricula: str):
    tentativas_falhas.pop(matricula, None)


def criar_token_acesso(usuario: Usuario) -> str:
    expira = datetime.now(timezone.utc) + timedelta(hours=configuracao.HORAS_SESSAO)
    dados = {"sub": str(usuario.id), "perfil": usuario.perfil, "exp": expira}
    return jwt.encode(dados, configuracao.CHAVE_SECRETA, algorithm=ALGORITMO)


def carregar_usuario_do_token(token: str):
    if not token:
        return None
    try:
        dados = jwt.decode(token, configuracao.CHAVE_SECRETA, algorithms=[ALGORITMO])
        usuario_id = int(dados["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    with abrir_sessao() as sessao:
        usuario = sessao.get(Usuario, usuario_id)
        if not usuario or not usuario.ativo:
            return None
        return {"id": usuario.id, "matricula": usuario.matricula, "nome": usuario.nome, "perfil": usuario.perfil}


def usuario_autenticado(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sessão inválida")
    usuario = carregar_usuario_do_token(authorization[7:].strip())
    if not usuario:
        raise HTTPException(status_code=401, detail="Sessão expirada ou inválida")
    return usuario


def administrador(usuario: dict = Depends(usuario_autenticado)):
    if usuario["perfil"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    return usuario


def validar_chave_integracao(x_chave_integracao: str | None = Header(default=None)):
    chave = configuracao.CHAVE_INTEGRACAO
    if not chave or not secrets.compare_digest(x_chave_integracao or "", chave):
        raise HTTPException(status_code=401, detail="Chave de integração inválida")
