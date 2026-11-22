"""k_inf: preço com informação incompleta pela cascata da ADR-004 (adapta o Quadro 3).

| meses | nível        | preço                                              |
| 12+   | ℓ = 2        | k_pol: κ·max(π_r, τ·H_pad)                         |
| 1–11  | ℓ = 1        | κ·[Z·max(π_r, τ·H_pad,pr) + (1 − Z)·B̂], Eq. (79)   |
| 0     | sem histórico| B̂ = regra sem histórico (piso do regime no MVP)    |

O regime é obrigatório: não existe nível 0 (ADR-004 item 2).
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Protocol

from dynaprice.dominio.modelos import (
    Dinheiro,
    Horas,
    Kappa,
    PoliticaVersao,
    Regime,
    ValorInvalido,
)
from dynaprice.dominio.precificacao.politica import PoliticaDePreco, PrecoAlvo

MESES_COMPLETOS = 12


class NivelDeInformacao(Enum):
    COMPLETO = 2
    PARCIAL = 1
    SEM_HISTORICO = 0

    @property
    def ell(self) -> int:
        """ℓ da Eq. (4); sem histórico é ℓ = 1 com regime conhecido (ADR-004)."""
        return 2 if self is NivelDeInformacao.COMPLETO else 1


def nivel_de_informacao(meses: int) -> NivelDeInformacao:
    if meses < 0:
        raise ValorInvalido(f"meses negativos: {meses}")
    if meses >= MESES_COMPLETOS:
        return NivelDeInformacao.COMPLETO
    return NivelDeInformacao.PARCIAL if meses > 0 else NivelDeInformacao.SEM_HISTORICO


def fator_de_credibilidade(meses: int, razao_s2_v2: Decimal) -> Decimal:
    """Z = m / (m + s²/v²) (Eq. 56, Bühlmann)."""
    return Decimal(meses) / (Decimal(meses) + razao_s2_v2)


class BaseSemHistorico(Protocol):
    """Strategy de B̂ (seção 6.9): piso do regime no MVP; vizinhança fica para F2/F3."""

    def base(self, regime: Regime) -> Decimal: ...


class PisoDoRegime:
    def __init__(self, politica: PoliticaVersao) -> None:
        self._politica = politica

    def base(self, regime: Regime) -> Decimal:
        return self._politica.piso(regime).valor


@dataclass(frozen=True, slots=True)
class PrecoInferido:
    nivel: NivelDeInformacao
    credibilidade: Decimal  # Z
    exato: Decimal
    valor: Dinheiro
    alvo: PrecoAlvo | None  # preço próprio max(π_r, τ·H) quando há meses

    @property
    def provisorio(self) -> bool:
        return self.nivel is not NivelDeInformacao.COMPLETO


class InferenciaDePreco:
    def __init__(self, politica_de_preco: PoliticaDePreco, sem_historico: BaseSemHistorico) -> None:
        self._politica = politica_de_preco
        self._sem_historico = sem_historico

    def preco(
        self,
        regime: Regime | None,
        horas_padrao: Horas | None,
        meses: int,
        kappa: Kappa | None = None,
    ) -> PrecoInferido:
        if regime is None:
            raise ValorInvalido("regime obrigatório (ADR-004): não existe nível 0")
        nivel = nivel_de_informacao(meses)
        if nivel is NivelDeInformacao.SEM_HISTORICO:
            base = self._sem_historico.base(regime)
            return PrecoInferido(nivel, Decimal(0), base, self._arredondar(base), None)
        if horas_padrao is None:
            raise ValorInvalido(f"{meses} meses de histórico sem horas-padrão")
        alvo = self._politica.preco_alvo(regime, horas_padrao, kappa)
        if nivel is NivelDeInformacao.COMPLETO:
            return PrecoInferido(nivel, Decimal(1), alvo.exato, alvo.valor, alvo)
        return self._parcial(regime, alvo, meses)

    def _parcial(self, regime: Regime, alvo: PrecoAlvo, meses: int) -> PrecoInferido:
        z = fator_de_credibilidade(meses, self._politica.versao.razao_s2_v2)
        proprio = self._politica.base(regime, alvo.horas_padrao)
        exato = alvo.kappa.valor * (z * proprio + (1 - z) * self._sem_historico.base(regime))
        return PrecoInferido(NivelDeInformacao.PARCIAL, z, exato, self._arredondar(exato), alvo)

    def _arredondar(self, valor: Decimal) -> Dinheiro:
        return self._politica.arredondar(valor)
