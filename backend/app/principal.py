import socketio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import configuracao
from app.eventos import sio
from app.rotas import administracao, atendimento, autenticacao, cliente, integracao, paginas

api = FastAPI(title="MJChat", docs_url="/api/documentacao", redoc_url=None)
api.mount("/estatico", StaticFiles(directory=configuracao.PASTA_FRONTEND), name="estatico")

for modulo in (paginas, autenticacao, cliente, atendimento, administracao, integracao):
    api.include_router(modulo.roteador)

aplicacao = socketio.ASGIApp(sio, other_asgi_app=api)
