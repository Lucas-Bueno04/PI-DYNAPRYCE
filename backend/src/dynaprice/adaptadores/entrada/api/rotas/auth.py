"""Rotas de /auth (ADR-002): o refresh trafega só em cookie HttpOnly."""

from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Cookie, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from dynaprice.adaptadores.entrada.api.seguranca import (
    Dependencias,
    PrincipalAtual,
    autenticada,
    publica,
)
from dynaprice.aplicacao.casos_de_uso.autenticacao import (
    CadastrarMfa,
    ConcluirMfa,
    ConfirmarMfa,
    Entrar,
    ParDeTokens,
    RenovarSessao,
    Sair,
    TrocarInquilino,
)
from dynaprice.aplicacao.casos_de_uso.recuperar_acesso import RecuperarMfa, RedefinirSenha
from dynaprice.aplicacao.casos_de_uso.usuarios import TAMANHO_MAXIMO_DA_SENHA
from dynaprice.aplicacao.erros import AcessoNegado, NaoAutenticado

roteador = APIRouter(prefix="/auth", tags=["auth"])

COOKIE = "dynaprice_refresh"
_CAMINHO_DO_COOKIE = "/api/v1/auth"
_DURACAO_DO_COOKIE = timedelta(days=7)

CookieRefresh = Annotated[str | None, Cookie(alias=COOKIE)]


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CorpoEntrar(_Entrada):
    email: str = Field(max_length=320)
    senha: str = Field(max_length=TAMANHO_MAXIMO_DA_SENHA)


class CorpoMfa(_Entrada):
    desafio: str = Field(max_length=4096)
    codigo: str = Field(max_length=16)


class CorpoCadastro(_Entrada):
    desafio: str = Field(max_length=4096)


class CorpoInquilino(_Entrada):
    tenant_id: UUID


class CorpoRedefinir(_Entrada):
    token: str = Field(max_length=256)
    nova_senha: str = Field(max_length=TAMANHO_MAXIMO_DA_SENHA)


class CorpoRecuperarMfa(_Entrada):
    email: str = Field(max_length=320)
    senha: str = Field(max_length=TAMANHO_MAXIMO_DA_SENHA)
    codigo: str = Field(max_length=64)


class RespostaTokens(BaseModel):
    acesso: str
    tenant_id: UUID
    inquilinos: list[UUID]


class RespostaEntrar(BaseModel):
    tokens: RespostaTokens | None = None
    desafio: str | None = None
    cadastro_mfa_requerido: bool = False


class RespostaCadastro(BaseModel):
    segredo: str
    uri: str


class RespostaConfirmacao(BaseModel):
    tokens: RespostaTokens
    codigos_de_recuperacao: list[str]


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconhecido"


def _gravar_cookie(resposta: Response, refresh: str) -> None:
    resposta.set_cookie(
        COOKIE,
        refresh,
        max_age=int(_DURACAO_DO_COOKIE.total_seconds()),
        path=_CAMINHO_DO_COOKIE,
        httponly=True,
        secure=True,
        samesite="strict",
    )


def _tokens(resposta: Response, par: ParDeTokens) -> RespostaTokens:
    _gravar_cookie(resposta, par.refresh)
    return RespostaTokens(
        acesso=par.acesso, tenant_id=par.tenant_id, inquilinos=list(par.inquilinos)
    )


def _exigir_origem(deps: Dependencias, request: Request) -> None:
    if request.headers.get("origin") != deps.origem_permitida:
        raise AcessoNegado("origem não permitida")


def _exigir_cookie(refresh: str | None) -> str:
    if refresh is None:
        raise NaoAutenticado("sem cookie")
    return refresh


@roteador.post("/entrar", **publica())
def entrar(
    corpo: CorpoEntrar, request: Request, resposta: Response, deps: Dependencias
) -> RespostaEntrar:
    resultado = Entrar(deps.auth).executar(corpo.email, corpo.senha, _ip(request))
    return RespostaEntrar(
        tokens=None if resultado.tokens is None else _tokens(resposta, resultado.tokens),
        desafio=resultado.desafio,
        cadastro_mfa_requerido=resultado.cadastro_mfa_requerido,
    )


@roteador.post("/mfa", **publica())
def concluir_mfa(
    corpo: CorpoMfa, request: Request, resposta: Response, deps: Dependencias
) -> RespostaTokens:
    return _tokens(
        resposta, ConcluirMfa(deps.auth).executar(corpo.desafio, corpo.codigo, _ip(request))
    )


@roteador.post("/mfa/cadastrar", **publica())
def cadastrar_mfa(corpo: CorpoCadastro, deps: Dependencias) -> RespostaCadastro:
    cadastro = CadastrarMfa(deps.auth).executar(corpo.desafio)
    return RespostaCadastro(segredo=cadastro.segredo, uri=cadastro.uri)


@roteador.post("/mfa/confirmar", **publica())
def confirmar_mfa(corpo: CorpoMfa, resposta: Response, deps: Dependencias) -> RespostaConfirmacao:
    confirmado = ConfirmarMfa(deps.auth).executar(corpo.desafio, corpo.codigo)
    return RespostaConfirmacao(
        tokens=_tokens(resposta, confirmado.tokens),
        codigos_de_recuperacao=list(confirmado.codigos_de_recuperacao),
    )


@roteador.post("/renovar", **publica())
def renovar(
    request: Request, resposta: Response, deps: Dependencias, refresh: CookieRefresh = None
) -> RespostaTokens:
    _exigir_origem(deps, request)
    return _tokens(resposta, RenovarSessao(deps.auth).executar(_exigir_cookie(refresh)))


@roteador.post("/sair", status_code=204, **publica())
def sair(
    request: Request, resposta: Response, deps: Dependencias, refresh: CookieRefresh = None
) -> None:
    _exigir_origem(deps, request)
    if refresh is not None:
        Sair(deps.auth).executar(refresh)
    resposta.delete_cookie(COOKIE, path=_CAMINHO_DO_COOKIE)


@roteador.post("/inquilino", **autenticada())
def trocar_inquilino(
    corpo: CorpoInquilino,
    request: Request,
    resposta: Response,
    deps: Dependencias,
    principal: PrincipalAtual,
    refresh: CookieRefresh = None,
) -> RespostaTokens:
    _exigir_origem(deps, request)
    par = TrocarInquilino(deps.auth).executar(principal, _exigir_cookie(refresh), corpo.tenant_id)
    return _tokens(resposta, par)


@roteador.post("/redefinir", status_code=204, **publica())
def redefinir(corpo: CorpoRedefinir, deps: Dependencias) -> None:
    RedefinirSenha(deps.auth).executar(corpo.token, corpo.nova_senha)


@roteador.post("/recuperar-mfa", status_code=204, **publica())
def recuperar_mfa(corpo: CorpoRecuperarMfa, request: Request, deps: Dependencias) -> None:
    RecuperarMfa(deps.auth).executar(corpo.email, corpo.senha, corpo.codigo, _ip(request))


@roteador.get("/jwks.json", **publica())
def jwks(deps: Dependencias) -> dict[str, Any]:
    return deps.auth.emissor.jwks()
