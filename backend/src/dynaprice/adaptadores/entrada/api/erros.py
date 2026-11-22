"""Tradução de erros em Problem Details (RFC 9457)."""

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from dynaprice.aplicacao.erros import (
    AcessoNegado,
    Conflito,
    MuitasTentativas,
    NaoAutenticado,
    NaoEncontrado,
)
from dynaprice.aplicacao.portas import TokenInvalido
from dynaprice.dominio.modelos import ErroDeDominio, TransicaoInvalida

_TIPO_MIDIA = "application/problem+json"


def problema(
    status: int,
    detalhe: str | None = None,
    extras: dict[str, Any] | None = None,
    cabecalhos: dict[str, str] | None = None,
) -> JSONResponse:
    corpo: dict[str, Any] = {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
    }
    if detalhe is not None:
        corpo["detail"] = detalhe
    return JSONResponse(
        {**corpo, **(extras or {})}, status, headers=cabecalhos, media_type=_TIPO_MIDIA
    )


def resposta_de_erro_inesperado() -> JSONResponse:
    return problema(500)


# Mensagem fixa: quem chama não descobre se o erro foi de senha, conta ou sessão.
_MAPA: tuple[tuple[type[Exception], int, str | None], ...] = (
    (TokenInvalido, 401, "não autenticado"),
    (NaoAutenticado, 401, "não autenticado"),
    (AcessoNegado, 403, "acesso negado"),
    (NaoEncontrado, 404, "não encontrado"),
    (TransicaoInvalida, 409, None),
    (Conflito, 409, None),
    (ErroDeDominio, 422, None),
)


def _manipulador(status: int, fixo: str | None) -> Any:
    async def manipular(_: Request, erro: Exception) -> JSONResponse:
        return problema(status, fixo if fixo is not None else str(erro))

    return manipular


async def _muitas_tentativas(_: Request, erro: Exception) -> JSONResponse:
    assert isinstance(erro, MuitasTentativas)
    return problema(429, "muitas tentativas", cabecalhos={"Retry-After": str(erro.espera_s)})


async def _http(_: Request, erro: Exception) -> JSONResponse:
    assert isinstance(erro, HTTPException)
    return problema(erro.status_code, cabecalhos=dict(erro.headers or {}))


async def _validacao(_: Request, erro: Exception) -> JSONResponse:
    assert isinstance(erro, RequestValidationError)
    # Só o caminho do campo e o tipo do erro: a entrada pode ter senha ou e-mail.
    campos = [{"campo": list(e["loc"]), "erro": e["type"]} for e in erro.errors()]
    return problema(422, "entrada inválida", {"campos": campos})


async def _inesperado(_: Request, __: Exception) -> JSONResponse:
    return resposta_de_erro_inesperado()


def registrar_erros(app: FastAPI) -> None:
    for tipo, status, fixo in _MAPA:
        app.add_exception_handler(tipo, _manipulador(status, fixo))
    app.add_exception_handler(MuitasTentativas, _muitas_tentativas)
    app.add_exception_handler(HTTPException, _http)
    app.add_exception_handler(RequestValidationError, _validacao)
    app.add_exception_handler(Exception, _inesperado)
