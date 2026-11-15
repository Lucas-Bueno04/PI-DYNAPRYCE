"""Bloqueio progressivo por conta e por IP (ADR-002), com escritas pontuais."""

from dynaprice.aplicacao.casos_de_uso.autenticacao.base import (
    DependenciasDeAutenticacao,
    auditar_nos_inquilinos,
)
from dynaprice.aplicacao.erros import MuitasTentativas
from dynaprice.aplicacao.portas import UnidadeDeAutenticacao
from dynaprice.dominio.modelos.autenticacao import Usuario


class ControleDeFalhas:
    def __init__(self, deps: DependenciasDeAutenticacao, ip: str) -> None:
        self._deps = deps
        self._ip = deps.pseudonimo_ip(ip)

    def exigir_ip_livre(self, uow: UnidadeDeAutenticacao) -> None:
        agora = self._deps.relogio.agora()
        ate = uow.limites.bloqueado_ate(self._ip)
        if ate is not None and agora < ate:
            raise MuitasTentativas(int((ate - agora).total_seconds()) + 1)

    def exigir_conta_livre(self, usuario: Usuario) -> None:
        agora = self._deps.relogio.agora()
        if usuario.bloqueado_em(agora):
            assert usuario.bloqueado_ate is not None
            raise MuitasTentativas(int((usuario.bloqueado_ate - agora).total_seconds()) + 1)

    def registrar_falha_de_ip(self, uow: UnidadeDeAutenticacao) -> None:
        agora = self._deps.relogio.agora()
        parametros = self._deps.parametros
        falhas = uow.limites.registrar_falha(self._ip, agora, agora - parametros.janela_de_falhas)
        duracao = parametros.duracao_do_bloqueio(falhas, parametros.falhas_antes_do_bloqueio_ip)
        if duracao is not None:
            uow.limites.bloquear(self._ip, agora + duracao)

    def registrar_falha(self, uow: UnidadeDeAutenticacao, usuario: Usuario) -> None:
        falhas = uow.usuarios.registrar_falha_login(usuario.id)
        duracao = self._deps.parametros.duracao_do_bloqueio(falhas)
        if duracao is not None:
            uow.usuarios.bloquear(usuario.id, self._deps.relogio.agora() + duracao)
        self.registrar_falha_de_ip(uow)
        auditar_nos_inquilinos(uow, usuario.id, uow.usuarios.inquilinos(usuario.id), "login_falhou")

    def contar(self, uow: UnidadeDeAutenticacao, usuario: Usuario | None) -> None:
        if usuario is None:
            self.registrar_falha_de_ip(uow)
        else:
            self.registrar_falha(uow, usuario)

    def zerar_conta(self, uow: UnidadeDeAutenticacao, usuario: Usuario) -> None:
        """O limite por IP não zera com sucesso: decai pela janela de tempo (achado M2)."""
        uow.usuarios.zerar_falhas(usuario.id)
