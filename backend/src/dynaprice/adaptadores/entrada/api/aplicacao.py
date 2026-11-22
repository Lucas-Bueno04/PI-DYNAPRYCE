"""Montagem da aplicação FastAPI: rotas em /api/v1 e request id."""

import re
import time
from collections.abc import Awaitable, Callable, Sequence
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Request, Response

from dynaprice.adaptadores.entrada.api.erros import registrar_erros
from dynaprice.adaptadores.entrada.api.metricas import Metricas
from dynaprice.adaptadores.entrada.api.rotas import ROTEADORES
from dynaprice.adaptadores.entrada.api.seguranca import Servicos

PREFIXO = "/api/v1"
_REQUEST_ID_VALIDO = re.compile(r"^[\w-]{1,64}$")


async def _request_id(
    request: Request, proxima: Callable[[Request], Awaitable[Response]]
) -> Response:
    recebido = request.headers.get("x-request-id", "")
    identificador = recebido if _REQUEST_ID_VALIDO.match(recebido) else str(uuid4())
    request.state.request_id = identificador
    inicio = time.monotonic()
    resposta = await proxima(request)
    # A rota vem depois do roteamento e usa o molde: ids não entram na chave da métrica.
    rota = getattr(request.scope.get("route"), "path", None)
    if rota is not None:
        chave = (
            f"{request.method} {PREFIXO}{rota}"
            if not rota.startswith(PREFIXO)
            else f"{request.method} {rota}"
        )
        request.app.state.metricas.registrar(
            f"{chave} {resposta.status_code}", time.monotonic() - inicio
        )
    resposta.headers["x-request-id"] = identificador
    if request.url.path.startswith(f"{PREFIXO}/auth") or request.url.path.endswith("/redefinicao"):
        resposta.headers["cache-control"] = "no-store"
    return resposta


def criar_app(servicos: Servicos, rotas_extras: Sequence[APIRouter] = ()) -> FastAPI:
    app = FastAPI(
        title="DynaPrice API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{PREFIXO}/openapi.json",
    )
    app.state.servicos = servicos
    app.state.metricas = Metricas()
    app.middleware("http")(_request_id)
    registrar_erros(app)
    for modulo in (*ROTEADORES, *rotas_extras):
        app.include_router(modulo, prefix=PREFIXO)
    return app
