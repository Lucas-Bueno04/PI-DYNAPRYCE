"""Cadastro do TOTP e códigos de recuperação."""

import secrets
from dataclasses import dataclass
from uuid import UUID, uuid4

from dynaprice.aplicacao.casos_de_uso.autenticacao.base import (
    TOTAL_DE_CODIGOS_DE_RECUPERACAO,
    DependenciasDeAutenticacao,
    ParDeTokens,
    abrir_sessao,
    auditar_nos_inquilinos,
    contexto_totp,
    usuario_do_desafio,
)
from dynaprice.aplicacao.erros import AcessoNegado, Conflito, NaoAutenticado
from dynaprice.aplicacao.portas import UnidadeDeAutenticacao
from dynaprice.dominio.modelos.autenticacao import Usuario


@dataclass(frozen=True, slots=True)
class CadastroDeMfa:
    segredo: str
    uri: str


class CadastrarMfa:
    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, desafio: str) -> CadastroDeMfa:
        with self._deps.fabrica.sem_tenant() as uow:
            usuario = usuario_do_desafio(self._deps, uow, desafio)
            if usuario.mfa_ativo:
                # O desafio prova só a senha: não pode trocar um MFA já ativo.
                raise AcessoNegado("MFA já cadastrado")
            segredo = self._deps.totp.novo_segredo()
            cifrado = self._deps.cifrador.cifrar(segredo.encode(), contexto_totp(usuario.id))
            uow.usuarios.iniciar_cadastro_mfa(usuario.id, cifrado)
            return CadastroDeMfa(segredo, self._deps.totp.uri(segredo, usuario.email))


@dataclass(frozen=True, slots=True)
class MfaConfirmado:
    tokens: ParDeTokens
    codigos_de_recuperacao: tuple[str, ...]


class ConfirmarMfa:
    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, desafio: str, codigo: str) -> MfaConfirmado:
        with self._deps.fabrica.sem_tenant() as uow:
            usuario = usuario_do_desafio(self._deps, uow, desafio)
            passo = self._passo(usuario, codigo)
            assert usuario.totp_cifrado is not None
            if not uow.usuarios.ativar_mfa(usuario.id, passo, usuario.totp_cifrado):
                raise Conflito("MFA já cadastrado")
            codigos = gerar_codigos(self._deps, uow, usuario.id)
            inquilinos = uow.usuarios.inquilinos(usuario.id)
            if not inquilinos:
                raise NaoAutenticado("usuário sem inquilino")
            auditar_nos_inquilinos(uow, usuario.id, inquilinos, "mfa_cadastrado")
            tokens = abrir_sessao(self._deps, uow, usuario, inquilinos[0], mfa=True)
            return MfaConfirmado(tokens, codigos)

    def _passo(self, usuario: Usuario, codigo: str) -> int:
        if usuario.mfa_ativo or usuario.totp_cifrado is None:
            raise Conflito("não há cadastro de MFA em andamento")
        segredo = self._deps.cifrador.decifrar(usuario.totp_cifrado, contexto_totp(usuario.id))
        passo = self._deps.totp.passo_valido(segredo.decode(), codigo, self._deps.relogio.agora())
        if passo is None:
            raise NaoAutenticado("código inválido")
        return passo


def gerar_codigos(
    deps: DependenciasDeAutenticacao, uow: UnidadeDeAutenticacao, usuario_id: UUID
) -> tuple[str, ...]:
    ids = [uuid4() for _ in range(TOTAL_DE_CODIGOS_DE_RECUPERACAO)]
    segredos = [secrets.token_hex(8) for _ in ids]
    # O id no código permite conferir um único hash: custo fixo, sem oráculo de tempo (A3).
    uow.recuperacao.substituir_codigos(
        usuario_id, [(i, deps.hash_de_senha.gerar(s)) for i, s in zip(ids, segredos, strict=True)]
    )
    return tuple(f"{i.hex}.{s}" for i, s in zip(ids, segredos, strict=True))
