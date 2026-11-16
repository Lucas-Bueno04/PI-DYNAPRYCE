"""Administração de usuários do inquilino (uc_users)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path
from pydantic import BaseModel, ConfigDict, Field

from dynaprice.adaptadores.entrada.api.seguranca import Dependencias, PrincipalAtual, exige
from dynaprice.aplicacao.autorizacao import Acao
from dynaprice.aplicacao.casos_de_uso.recuperar_acesso import GerarRedefinicao
from dynaprice.aplicacao.casos_de_uso.usuarios import (
    TAMANHO_MAXIMO_DA_SENHA,
    CriarUsuario,
    DefinirPapeis,
    DesativarUsuario,
    ListarUsuarios,
)
from dynaprice.dominio.modelos.autenticacao import Papel

roteador = APIRouter(prefix="/usuarios", tags=["usuarios"])

IdDoUsuario = Annotated[UUID, Path()]


class CorpoCriar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=320)
    senha: str = Field(max_length=TAMANHO_MAXIMO_DA_SENHA)
    papeis: set[Papel]


class CorpoPapeis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    papeis: set[Papel]


class RespostaUsuario(BaseModel):
    id: UUID
    email: str
    ativo: bool
    mfa_ativo: bool
    papeis: list[Papel]


class RespostaCriado(BaseModel):
    id: UUID


class RespostaRedefinicao(BaseModel):
    token: str


@roteador.get("", **exige(Acao.GERIR_USUARIOS))
def listar(deps: Dependencias, principal: PrincipalAtual) -> list[RespostaUsuario]:
    return [
        RespostaUsuario(
            id=u.id, email=u.email, ativo=u.ativo, mfa_ativo=u.mfa_ativo, papeis=sorted(papeis)
        )
        for u, papeis in ListarUsuarios(deps.auth).executar(principal)
    ]


@roteador.post("", status_code=201, **exige(Acao.GERIR_USUARIOS))
def criar(corpo: CorpoCriar, deps: Dependencias, principal: PrincipalAtual) -> RespostaCriado:
    identificador = CriarUsuario(deps.auth).executar(
        principal, corpo.email, corpo.senha, frozenset(corpo.papeis)
    )
    return RespostaCriado(id=identificador)


@roteador.put("/{usuario_id}/papeis", status_code=204, **exige(Acao.GERIR_USUARIOS))
def definir_papeis(
    usuario_id: IdDoUsuario, corpo: CorpoPapeis, deps: Dependencias, principal: PrincipalAtual
) -> None:
    DefinirPapeis(deps.auth).executar(principal, usuario_id, frozenset(corpo.papeis))


@roteador.delete("/{usuario_id}", status_code=204, **exige(Acao.GERIR_USUARIOS))
def desativar(usuario_id: IdDoUsuario, deps: Dependencias, principal: PrincipalAtual) -> None:
    DesativarUsuario(deps.auth).executar(principal, usuario_id)


@roteador.post("/{usuario_id}/redefinicao", **exige(Acao.GERIR_USUARIOS))
def gerar_redefinicao(
    usuario_id: IdDoUsuario, deps: Dependencias, principal: PrincipalAtual
) -> RespostaRedefinicao:
    return RespostaRedefinicao(token=GerarRedefinicao(deps.auth).executar(principal, usuario_id))
