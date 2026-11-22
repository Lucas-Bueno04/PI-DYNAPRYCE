"""Variação mensal de um índice de inflação (IPCA), em fração (0,0042 = 0,42%)."""

from dataclasses import dataclass
from decimal import Decimal

from dynaprice.dominio.modelos.competencia import Competencia


@dataclass(frozen=True, slots=True)
class VariacaoDeIndice:
    competencia: Competencia
    variacao: Decimal
