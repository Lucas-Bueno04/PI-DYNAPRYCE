"""Entrada por OIDC (F3.2): o IdP prova quem é; a conta, os papéis e o MFA continuam nossos.

O IdP nunca cria conta: o e-mail verificado precisa casar com um usuário ativo já cadastrado.
Depois disso o fluxo é o mesmo da senha (`proxima_etapa`): TOTP, cadastro de MFA ou sessão.
"""

import secrets
from dataclasses import dataclass

from dynaprice.aplicacao.casos_de_uso.autenticacao.base import (
    DependenciasDeAutenticacao,
    ResultadoDeEntrada,
    auditar_nos_inquilinos,
)
from dynaprice.aplicacao.casos_de_uso.autenticacao.entrada import proxima_etapa
from dynaprice.aplicacao.erros import NaoAutenticado
from dynaprice.aplicacao.portas import TokenInvalido
from dynaprice.aplicacao.portas.oidc import EstadoDeFederacao, ProvedorOidc, desafio_pkce

_BYTES_ALEATORIOS = 32


@dataclass(frozen=True, slots=True)
class InicioDeFederacao:
    url: str
    estado: str  # JWT assinado que o navegador devolve no retorno (cookie HttpOnly)


class IniciarFederacao:
    def __init__(self, deps: DependenciasDeAutenticacao, provedor: ProvedorOidc) -> None:
        self._deps = deps
        self._provedor = provedor

    def executar(self) -> InicioDeFederacao:
        estado = EstadoDeFederacao(
            secrets.token_urlsafe(_BYTES_ALEATORIOS),
            secrets.token_urlsafe(_BYTES_ALEATORIOS),
            secrets.token_urlsafe(_BYTES_ALEATORIOS),
        )
        url = self._provedor.url_de_autorizacao(
            estado.state, estado.nonce, desafio_pkce(estado.verificador_pkce)
        )
        return InicioDeFederacao(url, self._deps.emissor.emitir_estado_de_federacao(estado))


class ConcluirFederacao:
    def __init__(self, deps: DependenciasDeAutenticacao, provedor: ProvedorOidc) -> None:
        self._deps = deps
        self._provedor = provedor

    def executar(
        self, codigo: str, state: str, estado_assinado: str, ip: str
    ) -> ResultadoDeEntrada:
        estado = self._estado(estado_assinado)
        if not secrets.compare_digest(state.encode(), estado.state.encode()):
            raise NaoAutenticado("estado não confere")
        try:
            identidade = self._provedor.identidade(codigo, estado.verificador_pkce, estado.nonce)
        except TokenInvalido as erro:
            raise NaoAutenticado("identidade recusada") from erro
        if not identidade.email_verificado or not identidade.email:
            raise NaoAutenticado("e-mail não verificado pelo provedor")
        with self._deps.fabrica.sem_tenant() as uow:
            usuario = uow.usuarios.obter_por_email(identidade.email)
            if usuario is None or not usuario.ativo:
                raise NaoAutenticado("conta não autorizada")
            auditar_nos_inquilinos(
                uow, usuario.id, uow.usuarios.inquilinos(usuario.id), "login_federado"
            )
            return proxima_etapa(self._deps, uow, usuario)

    def _estado(self, token: str) -> EstadoDeFederacao:
        try:
            return self._deps.emissor.verificar_estado_de_federacao(token)
        except TokenInvalido as erro:
            raise NaoAutenticado("estado inválido") from erro
