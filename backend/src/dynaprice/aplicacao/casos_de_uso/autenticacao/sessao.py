"""Renovação com rotação e detecção de reuso, saída e troca de inquilino."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from dynaprice.aplicacao.casos_de_uso.autenticacao.base import (
    DependenciasDeAutenticacao,
    ParDeTokens,
    abrir_sessao,
    emitir_par,
    hash_do_token,
)
from dynaprice.aplicacao.erros import (
    AcessoNegado,
    ErroDeAplicacao,
    NaoAutenticado,
    RenovacaoConcorrente,
)
from dynaprice.aplicacao.portas import UnidadeDeAutenticacao
from dynaprice.dominio.modelos.autenticacao import Principal, RegistroDeRefresh, Usuario


def _executar_confirmando[T](
    deps: DependenciasDeAutenticacao, acao: Callable[[UnidadeDeAutenticacao], T]
) -> T:
    """O erro sobe depois do commit: a revogação por reuso precisa ficar gravada."""
    erro: ErroDeAplicacao | None = None
    with deps.fabrica.sem_tenant() as uow:
        try:
            resultado = acao(uow)
        except ErroDeAplicacao as falha:
            erro = falha
    if erro is not None:
        raise erro
    return resultado


class _ValidadorDeRefresh:
    """Regra única de validade do refresh: toda rota que o aceita passa por aqui (achado A1)."""

    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def validar(
        self, uow: UnidadeDeAutenticacao, hash_token: bytes
    ) -> tuple[RegistroDeRefresh, Usuario]:
        registro = uow.sessoes.travar_token(hash_token)
        if registro is None or registro.revogada_em is not None:
            raise NaoAutenticado("sessão inválida")
        agora = self._deps.relogio.agora()
        if registro.usado_em is not None:
            self._tratar_reuso(uow, registro, agora)
        if agora >= registro.expira_em or agora >= registro.familia_expira_em:
            raise NaoAutenticado("sessão expirada")
        usuario = uow.usuarios.obter(registro.usuario_id)
        if usuario is None or not usuario.ativo:
            uow.sessoes.revogar_familia(registro.familia_id, agora, "usuario_inativo")
            raise NaoAutenticado("sessão inválida")
        return registro, usuario

    def _tratar_reuso(
        self, uow: UnidadeDeAutenticacao, registro: RegistroDeRefresh, agora: datetime
    ) -> None:
        assert registro.usado_em is not None
        if agora - registro.usado_em <= self._deps.parametros.tolerancia_de_reuso:
            raise RenovacaoConcorrente("token rotacionado há instantes")
        uow.sessoes.revogar_familia(registro.familia_id, agora, "reuso")
        uow.fixar_tenant(registro.tenant_id)
        uow.auditoria.registrar(
            "refresh_reusado",
            {"familia_id": str(registro.familia_id)},
            usuario_id=registro.usuario_id,
        )
        raise NaoAutenticado("sessão revogada")


class RenovarSessao:
    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, refresh: str) -> ParDeTokens:
        return _executar_confirmando(
            self._deps, lambda uow: self._renovar(uow, hash_do_token(refresh))
        )

    def _renovar(self, uow: UnidadeDeAutenticacao, hash_token: bytes) -> ParDeTokens:
        registro, usuario = _ValidadorDeRefresh(self._deps).validar(uow, hash_token)
        uow.sessoes.marcar_usado(hash_token, registro.familia_id, self._deps.relogio.agora())
        return emitir_par(
            self._deps,
            uow,
            usuario,
            registro.tenant_id,
            registro.familia_id,
            registro.mfa_verificado,
            registro.familia_expira_em,
        )


class Sair:
    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, refresh: str) -> None:
        with self._deps.fabrica.sem_tenant() as uow:
            registro = uow.sessoes.travar_token(hash_do_token(refresh))
            if registro is not None:
                uow.sessoes.revogar_familia(registro.familia_id, self._deps.relogio.agora(), "sair")


class TrocarInquilino:
    def __init__(self, deps: DependenciasDeAutenticacao) -> None:
        self._deps = deps

    def executar(self, principal: Principal, refresh: str, tenant_id: UUID) -> ParDeTokens:
        return _executar_confirmando(
            self._deps, lambda uow: self._trocar(uow, principal, refresh, tenant_id)
        )

    def _trocar(
        self,
        uow: UnidadeDeAutenticacao,
        principal: Principal,
        refresh: str,
        tenant_id: UUID,
    ) -> ParDeTokens:
        if not uow.usuarios.papeis(principal.usuario_id, tenant_id):
            raise AcessoNegado("sem papel no inquilino")
        registro, usuario = _ValidadorDeRefresh(self._deps).validar(uow, hash_do_token(refresh))
        if usuario.id != principal.usuario_id:
            raise NaoAutenticado("sessão inválida")
        uow.sessoes.revogar_familia(registro.familia_id, self._deps.relogio.agora(), "troca")
        return abrir_sessao(
            self._deps,
            uow,
            usuario,
            tenant_id,
            registro.mfa_verificado,
            registro.familia_expira_em,
        )
