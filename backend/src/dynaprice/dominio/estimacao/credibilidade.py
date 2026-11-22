"""Estimação de s²/v² do fator de credibilidade Z = m/(m + s²/v²) (Eq. 55–56; ADR-004).

s²: variância mensal do preço de base dentro do contrato (ruído da média própria);
v²: erro quadrático da referência sem histórico (o piso do regime, ADR-004) contra a base
de longo prazo do contrato. Calculado sobre contratos com informação completa.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import fmean, variance

from dynaprice.dominio.modelos import Regime, ValorInvalido


@dataclass(frozen=True, slots=True)
class SerieDeBase:
    regime: Regime
    referencia: Decimal  # B̂: base sem histórico (π_r no MVP)
    bases_mensais: tuple[Decimal, ...]  # max(π_r, τ·H_pad do mês)


def _variancia_mensal(serie: SerieDeBase) -> float:
    return variance(map(float, serie.bases_mensais))


def _erro_da_referencia(serie: SerieDeBase) -> float:
    return (fmean(map(float, serie.bases_mensais)) - float(serie.referencia)) ** 2


def estimar_razao_s2_v2(series: Sequence[SerieDeBase]) -> float:
    uteis = [s for s in series if len(s.bases_mensais) >= 2]
    if not uteis:
        raise ValorInvalido("s²/v² exige contratos com ao menos 2 meses")
    s2 = fmean(map(_variancia_mensal, uteis))
    v2 = fmean(map(_erro_da_referencia, uteis))
    if v2 <= 0:
        raise ValorInvalido("v² nulo: a base nunca se afasta da referência")
    return s2 / v2
