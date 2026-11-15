"""Base da autenticação (ADR-002): dependências, resultados e abertura de sessão."""

import hashlib
import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from dynaprice.aplicacao.erros import NaoAutenticado
from dynaprice.aplicacao.portas import (
    Cifrador,
    EmissorDeTokens,
    FabricaDeUnidades,
    HashDeSenha,
    Relogio,
    TokenInvalido,
    UnidadeDeAutenticacao,
    VerificadorTotp,
)
from dynaprice.dominio.modelos.autenticacao import ParametrosDeSessao, Principal, Usuario

TOTAL_DE_CODIGOS_DE_RECUPERACAO = 10
_CONTEXTO_TOTP = "totp"


def hash_do_token(token: str) -> bytes:
    """Tokens opacos têm 256 bits de entropia: SHA-256 basta (sem sal, sem custo)."""
    return hashlib.sha256(token.encode()).digest()


def contexto_totp(usuario_id: UUID) -> str:
    return f"{_CONTEXTO_TOTP}:{usuario_id}"


@dataclass(frozen=True, slots=True)
class DependenciasDeAutenticacao:
    fabrica: FabricaDeUnidades
    relogio: Relogio
    hash_de_senha: HashDeSenha
    totp: VerificadorTotp
    emissor: EmissorDeTokens
    cifrador: Cifrador
    pseudonimo_ip: Callable[[str], bytes]
    parametros: ParametrosDeSessao = field(default_factory=ParametrosDeSessao)


@dataclass(frozen=True, slots=True)
class ParDeTokens:
    acesso: str
    refresh: str
    tenant_id: UUID
    inquilinos: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class ResultadoDeEntrada:
    tokens: ParDeTokens | None = None
    desafio: str | None = None
    cadastro_mfa_requerido: bool = False


def abrir_sessao(
    deps: DependenciasDeAutenticacao,
    uow: UnidadeDeAutenticacao,
    usuario: Usuario,
    tenant_id: UUID,
    mfa: bool,
    limite: datetime | None = None,
) -> ParDeTokens:
    """`limite` herda a validade absoluta quando a sessão continua outra (troca de inquilino)."""
    agora = deps.relogio.agora()
    expira_em = limite or agora + deps.parametros.validade_absoluta
    familia = uow.sessoes.criar_familia(usuario.id, tenant_id, mfa, agora, expira_em)
    return emitir_par(deps, uow, usuario, tenant_id, familia, mfa, expira_em)


def emitir_par(
    deps: DependenciasDeAutenticacao,
    uow: UnidadeDeAutenticacao,
    usuario: Usuario,
    tenant_id: UUID,
    familia: UUID,
    mfa: bool,
    limite: datetime,
) -> ParDeTokens:
    agora = deps.relogio.agora()
    refresh = secrets.token_urlsafe(32)
    expira_em = min(agora + deps.parametros.inatividade, limite)
    uow.sessoes.registrar_token(hash_do_token(refresh), familia, agora, expira_em)
    papeis = uow.usuarios.papeis(usuario.id, tenant_id)
    acesso = deps.emissor.emitir(Principal(usuario.id, tenant_id, papeis, mfa))
    return ParDeTokens(acesso, refresh, tenant_id, tuple(uow.usuarios.inquilinos(usuario.id)))


def auditar_nos_inquilinos(
    uow: UnidadeDeAutenticacao, usuario_id: UUID, inquilinos: Sequence[UUID], tipo: str
) -> None:
    """Eventos de conta valem para todos os inquilinos dela (cada trilha é por inquilino)."""
    for tenant_id in inquilinos:
        uow.fixar_tenant(tenant_id)
        uow.auditoria.registrar(tipo, {}, usuario_id=usuario_id)


def usuario_do_desafio(
    deps: DependenciasDeAutenticacao, uow: UnidadeDeAutenticacao, desafio: str
) -> Usuario:
    try:
        usuario = uow.usuarios.obter(deps.emissor.verificar_desafio(desafio))
    except TokenInvalido as erro:
        raise NaoAutenticado("desafio inválido") from erro
    if usuario is None or not usuario.ativo:
        raise NaoAutenticado("desafio inválido")
    return usuario
