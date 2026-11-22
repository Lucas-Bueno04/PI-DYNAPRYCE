"""Equação de tempo de um departamento (Eq. 36): t_m = β0,m + Σ β_k,m · x_k."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType

from dynaprice.dominio.modelos.erros import ValorInvalido
from dynaprice.dominio.modelos.regime import Departamento, Regime


def congelar(valores: Mapping[str, Decimal], nome: str) -> Mapping[str, Decimal]:
    """Cópia somente leitura com valores não negativos (direcionadores e inclinações)."""
    for chave, valor in valores.items():
        if not isinstance(valor, Decimal) or valor < 0:
            raise ValorInvalido(f"{nome}[{chave}] deve ser Decimal ≥ 0: {valor!r}")
    return MappingProxyType(dict(valores))


@dataclass(frozen=True, slots=True)
class EquacaoDeTempo:
    """β0 em horas; inclinações em minutos por unidade do direcionador (Tabela 7).

    `regime` None vale para todos os regimes; com regime, é a variante β0,m,r (seção 6.6).
    """

    departamento: Departamento
    beta0_horas: Decimal
    inclinacoes_minutos: Mapping[str, Decimal] = field(default_factory=dict)
    regime: Regime | None = None

    def __post_init__(self) -> None:
        if self.beta0_horas < 0:
            raise ValorInvalido(f"β0 negativo em {self.departamento}: {self.beta0_horas}")
        congeladas = congelar(self.inclinacoes_minutos, "inclinacoes_minutos")
        object.__setattr__(self, "inclinacoes_minutos", congeladas)

    @property
    def chave(self) -> tuple[Departamento, Regime | None]:
        return (self.departamento, self.regime)
