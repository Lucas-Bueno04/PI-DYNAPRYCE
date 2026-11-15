"""Recuperação de senha e de MFA (uc_recup, ADR-002): toda recuperação revoga as sessões."""

import secrets
from datetime import timedelta
from uuid import UUID

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.casos_de_uso.autenticacao import (
    DependenciasDeAutenticacao,
    hash_do_token,
)
from dynaprice.aplicacao.casos_de_uso.autenticacao.base import auditar_nos_inquilinos
from dynaprice.aplicacao.casos_de_uso.autenticacao.controle import ControleDeFalhas
from dynaprice.aplicacao.casos_de_uso.usuarios import validar_senha
from dynaprice.aplicacao.erros import AcessoNegado, NaoAutenticado, NaoEncontrado
from dynaprice.aplicacao.portas import UnidadeDeAutenticacao
from dynaprice.dominio.modelos.autenticacao import Principal, Usuario

VALIDADE_DO_LINK = timedelta(minutes=30)


class GerarRedefinicao:
    """O administrador gera o link de uso único e o repassa (MVP sem envio de e-mail)."""

    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, principal: Principal, usuario_id: UUID) -> str:
        autorizar(principal, Acao.GERIR_USUARIOS)
        with self._deps.fabrica.sem_tenant() as uow:
            inquilinos = set(uow.usuarios.inquilinos(usuario_id))
            if principal.tenant_id not in inquilinos:
                raise NaoEncontrado("usuário não pertence ao inquilino")
            if inquilinos != {principal.tenant_id}:
                # A senha é global: quem administra um inquilino não entra nos outros (M1).
                raise AcessoNegado("usuário também pertence a outro inquilino")
            token = secrets.token_urlsafe(32)
            limite = self._deps.relogio.agora() + VALIDADE_DO_LINK
            uow.recuperacao.invalidar_redefinicoes(usuario_id)
            uow.recuperacao.criar_redefinicao(hash_do_token(token), usuario_id, limite)
            uow.fixar_tenant(principal.tenant_id)
            uow.auditoria.registrar(
                "redefinicao_gerada", {"usuario": str(usuario_id)}, usuario_id=principal.usuario_id
            )
            return token


def _encerrar_sessoes(
    deps: DependenciasDeAutenticacao, uow: UnidadeDeAutenticacao, usuario: Usuario, tipo: str
) -> None:
    uow.sessoes.revogar_do_usuario(usuario.id, deps.relogio.agora(), tipo)
    auditar_nos_inquilinos(uow, usuario.id, uow.usuarios.inquilinos(usuario.id), tipo)


class RedefinirSenha:
    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, token: str, nova_senha: str) -> None:
        validar_senha(nova_senha)
        with self._deps.fabrica.sem_tenant() as uow:
            usuario_id = uow.recuperacao.consumir_redefinicao(
                hash_do_token(token), self._deps.relogio.agora()
            )
            usuario = None if usuario_id is None else uow.usuarios.obter(usuario_id)
            if usuario is None:
                raise NaoAutenticado("link inválido")
            uow.usuarios.redefinir_senha(usuario.id, self._deps.hash_de_senha.gerar(nova_senha))
            uow.recuperacao.invalidar_redefinicoes(usuario.id)
            _encerrar_sessoes(self._deps, uow, usuario, "senha_redefinida")


class RecuperarMfa:
    """Senha + código de recuperação de uso único desligam o MFA; o usuário cadastra de novo.

    Sempre faz exatamente duas verificações Argon2: o tempo não revela e-mail nem senha (A3).
    """

    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, email: str, senha: str, codigo: str, ip: str) -> None:
        controle = ControleDeFalhas(self._deps, ip)
        # O erro sobe depois do commit: a falha contada precisa ficar gravada.
        with self._deps.fabrica.sem_tenant() as uow:
            controle.exigir_ip_livre(uow)
            usuario = uow.usuarios.obter_por_email(email)
            if usuario is not None:
                controle.exigir_conta_livre(usuario)
            aceito, codigo_id = self._conferir(uow, usuario, senha, codigo)
            if usuario is None or codigo_id is None or not aceito:
                controle.contar(uow, usuario)
                recuperado = False
            else:
                recuperado = self._recuperar(uow, controle, usuario, codigo_id)
        if not recuperado:
            raise NaoAutenticado("credenciais inválidas")

    def _conferir(
        self, uow: UnidadeDeAutenticacao, usuario: Usuario | None, senha: str, codigo: str
    ) -> tuple[bool, UUID | None]:
        hash_de_senha = self._deps.hash_de_senha
        if usuario is None or not usuario.ativo:
            hash_de_senha.simular_verificacao(senha)
            hash_de_senha.simular_verificacao(codigo)
            return False, None
        senha_certa = hash_de_senha.verificar(usuario.senha_hash, senha)
        codigo_id, segredo = _separar_codigo(codigo)
        guardado = (
            None if codigo_id is None else uow.recuperacao.hash_do_codigo(usuario.id, codigo_id)
        )
        if guardado is None:
            hash_de_senha.simular_verificacao(segredo)
            return False, None
        codigo_certo = hash_de_senha.verificar(guardado, segredo)  # sempre roda: custo fixo
        return senha_certa and codigo_certo, codigo_id

    def _recuperar(
        self,
        uow: UnidadeDeAutenticacao,
        controle: ControleDeFalhas,
        usuario: Usuario,
        codigo_id: UUID,
    ) -> bool:
        if not uow.recuperacao.consumir_codigo(codigo_id, self._deps.relogio.agora()):
            return False
        uow.usuarios.desligar_mfa(usuario.id)
        controle.zerar_conta(uow, usuario)
        _encerrar_sessoes(self._deps, uow, usuario, "mfa_recuperado")
        return True


def _separar_codigo(codigo: str) -> tuple[UUID | None, str]:
    identificador, _, segredo = codigo.partition(".")
    try:
        return UUID(hex=identificador), segredo
    except ValueError:
        return None, segredo
