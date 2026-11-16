"""Rotas de entrada por OIDC (F3.2): redirecionam ao IdP e concluem no retorno.

O estado (state, nonce, PKCE) viaja em cookie HttpOnly assinado; o desafio de MFA vai no
fragmento da URL (nunca na consulta), e o refresh sai em cookie como na entrada por senha.
"""

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Query, Request
from fastapi.responses import RedirectResponse

from dynaprice.adaptadores.entrada.api.rotas.auth import _gravar_cookie, _ip
from dynaprice.adaptadores.entrada.api.seguranca import Dependencias, publica
from dynaprice.aplicacao.casos_de_uso.autenticacao import ResultadoDeEntrada
from dynaprice.aplicacao.casos_de_uso.autenticacao.federacao import (
    ConcluirFederacao,
    IniciarFederacao,
)
from dynaprice.aplicacao.erros import ErroDeAplicacao, NaoEncontrado
from dynaprice.aplicacao.portas.oidc import ProvedorOidc

roteador = APIRouter(prefix="/auth/oidc", tags=["auth"])

COOKIE_ESTADO = "dynaprice_oidc"
_CAMINHO = "/api/v1/auth/oidc"
_VALIDADE_S = 600
_ERRO = "/entrar?erro=federacao"

CookieEstado = Annotated[str | None, Cookie(alias=COOKIE_ESTADO)]


def _provedor(deps: Dependencias) -> ProvedorOidc:
    if deps.provedor_oidc is None:
        raise NaoEncontrado("federação não configurada")
    return deps.provedor_oidc


def _destino(resultado: ResultadoDeEntrada) -> str:
    if resultado.desafio:
        fragmento = {"desafio": resultado.desafio}
        if resultado.cadastro_mfa_requerido:
            fragmento["cadastro_mfa"] = "1"
        return f"/entrar#{urlencode(fragmento)}"
    return "/" if resultado.tokens else _ERRO


def _resposta(destino: str) -> RedirectResponse:
    resposta = RedirectResponse(destino, status_code=302)
    resposta.delete_cookie(COOKIE_ESTADO, path=_CAMINHO)
    return resposta


@roteador.get("/disponivel", **publica())
def disponivel(deps: Dependencias) -> dict[str, bool]:
    return {"disponivel": deps.provedor_oidc is not None}


@roteador.get("/entrar", **publica())
def entrar(deps: Dependencias) -> RedirectResponse:
    inicio = IniciarFederacao(deps.auth, _provedor(deps)).executar()
    resposta = RedirectResponse(inicio.url, status_code=302)
    resposta.set_cookie(
        COOKIE_ESTADO,
        inicio.estado,
        max_age=_VALIDADE_S,
        path=_CAMINHO,
        httponly=True,
        secure=True,
        samesite="lax",  # o retorno do IdP é navegação de outro site: Strict não enviaria
    )
    return resposta


@roteador.get("/retorno", **publica())
def retorno(
    request: Request,
    deps: Dependencias,
    code: Annotated[str | None, Query(max_length=2048)] = None,
    state: Annotated[str | None, Query(max_length=512)] = None,
    estado: CookieEstado = None,
) -> RedirectResponse:
    provedor = _provedor(deps)
    if not code or not state or not estado:  # inclui `error=...` do IdP
        return _resposta(_ERRO)
    try:
        resultado = ConcluirFederacao(deps.auth, provedor).executar(
            code, state, estado, _ip(request)
        )
    except ErroDeAplicacao:
        return _resposta(_ERRO)
    resposta = _resposta(_destino(resultado))
    if resultado.tokens is not None:
        _gravar_cookie(resposta, resultado.tokens.refresh)
    return resposta
