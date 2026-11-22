"""Horas-padrão e tarifa por hora-padrão (Eq. 59: τ·H_pad)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from dynaprice.dominio.modelos.conversao import Numero, para_decimal
from dynaprice.dominio.modelos.erros import ValorInvalido


@dataclass(frozen=True, slots=True, order=True)
class Horas:
    valor: Decimal

    def __post_init__(self) -> None:
        if self.valor < 0:
            raise ValorInvalido(f"horas negativas: {self.valor}")

    @classmethod
    def de(cls, valor: Numero) -> Horas:
        return cls(para_decimal(valor, "horas"))

    @classmethod
    def zero(cls) -> Horas:
        return cls(Decimal(0))

    def __add__(self, outra: Horas) -> Horas:
        return Horas(self.valor + outra.valor)


@dataclass(frozen=True, slots=True, order=True)
class Tarifa:
    """τ: preço de uma hora-padrão (seção 6.4); estritamente positiva."""

    valor: Decimal

    def __post_init__(self) -> None:
        if self.valor <= 0:
            raise ValorInvalido(f"tarifa deve ser > 0: {self.valor}")

    @classmethod
    def de(cls, valor: Numero) -> Tarifa:
        return cls(para_decimal(valor, "tarifa"))

    def __mul__(self, horas: Horas) -> Decimal:
        return self.valor * horas.valor
