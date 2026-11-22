"""in_auth: Bearer → Principal, e declaração do papel de cada rota (S5)."""

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.casos_de_uso.autenticacao import DependenciasDeAutenticacao
from dynaprice.aplicacao.erros import NaoAutenticado
from dynaprice.aplicacao.portas.oidc import ProvedorOidc
from dynaprice.dominio.modelos.autenticacao import Principal

PUBLICA = "publica"
AUTENTICADA = "autenticada"

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class Servicos:
    """O que as rotas usam; montado no Composition Root."""

    auth: DependenciasDeAutenticacao
    origem_permitida: str
    casos: Any = None  # CasosDeUso, montado no Composition Root
    provedor_oidc: ProvedorOidc | None = None  # federação (F3); ausente = rotas 404


def servicos(request: Request) -> Servicos:
    montados: Servicos = request.app.state.servicos
    return montados


Dependencias = Annotated[Servicos, Depends(servicos)]


def principal_atual(
    deps: Dependencias,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credenciais is None:
        raise NaoAutenticado("sem token")
    return deps.auth.emissor.verificar(credenciais.credentials)


PrincipalAtual = Annotated[Principal, Depends(principal_atual)]


class _Autorizar:
    def __init__(self, acao: Acao) -> None:
        self._acao = acao

    def __call__(self, principal: PrincipalAtual) -> None:
        autorizar(principal, self._acao)


def publica() -> dict[str, Any]:
    return {"openapi_extra": {"x-papel": PUBLICA}}


def autenticada() -> dict[str, Any]:
    return {
        "dependencies": [Depends(principal_atual)],
        "openapi_extra": {"x-papel": AUTENTICADA},
    }


def exige(acao: Acao) -> dict[str, Any]:
    """Declara e aplica a permissão: o que está no OpenAPI é o que a rota cobra."""
    return {"dependencies": [Depends(_Autorizar(acao))], "openapi_extra": {"x-papel": acao.value}}
