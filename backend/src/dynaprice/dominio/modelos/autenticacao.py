"""Identidade e parâmetros de sessão (ADR-002)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID


class Papel(StrEnum):
    ANALISAR = "analisar"
    APROVAR = "aprovar"
    ADMINISTRAR = "administrar"


_EXPOENTE_MAXIMO = 16  # timedelta estoura com expoente grande; o limite real é bloqueio_maximo
PAPEIS_COM_MFA = frozenset({Papel.APROVAR, Papel.ADMINISTRAR})


@dataclass(frozen=True, slots=True)
class Principal:
    """Quem faz a requisição, extraído do token de acesso."""

    usuario_id: UUID
    tenant_id: UUID
    papeis: frozenset[Papel]
    mfa_verificado: bool = False


@dataclass(frozen=True, slots=True)
class Usuario:
    id: UUID
    email: str
    senha_hash: str
    totp_cifrado: bytes | None = None
    totp_ultimo_passo: int | None = None
    mfa_ativo: bool = False
    ativo: bool = True
    falhas_login: int = 0
    bloqueado_ate: datetime | None = None

    def bloqueado_em(self, instante: datetime) -> bool:
        return self.bloqueado_ate is not None and instante < self.bloqueado_ate


@dataclass(frozen=True, slots=True)
class RegistroDeRefresh:
    """Token de renovação e a família dele, lidos com trava para a rotação."""

    hash_sha256: bytes
    familia_id: UUID
    usuario_id: UUID
    tenant_id: UUID
    mfa_verificado: bool
    usado_em: datetime | None
    expira_em: datetime
    familia_expira_em: datetime
    revogada_em: datetime | None


@dataclass(frozen=True, slots=True)
class ParametrosDeSessao:
    inatividade: timedelta = timedelta(hours=12)
    validade_absoluta: timedelta = timedelta(days=7)
    tolerancia_de_reuso: timedelta = timedelta(seconds=10)
    falhas_antes_do_bloqueio: int = 5
    falhas_antes_do_bloqueio_ip: int = 20  # um escritório inteiro pode sair pelo mesmo IP
    janela_de_falhas: timedelta = timedelta(hours=1)  # maior que o bloqueio máximo (N5)
    bloqueio_base: timedelta = timedelta(seconds=30)
    bloqueio_maximo: timedelta = timedelta(minutes=15)

    def duracao_do_bloqueio(self, falhas: int, limite: int | None = None) -> timedelta | None:
        """Atraso progressivo: dobra a cada falha depois do limite; None abaixo dele."""
        excedente = falhas - (self.falhas_antes_do_bloqueio if limite is None else limite)
        if excedente < 0:
            return None
        espera: timedelta = self.bloqueio_base * 2 ** min(excedente, _EXPOENTE_MAXIMO)
        return min(espera, self.bloqueio_maximo)
