"""Dinheiro: Decimal com 2 casas e ROUND_HALF_UP (D11). Único ponto de arredondamento a centavos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from dynaprice.dominio.modelos.conversao import Numero, para_decimal
from dynaprice.dominio.modelos.erros import ValorInvalido

CENTAVO = Decimal("0.01")


@dataclass(frozen=True, slots=True, order=True)
class Dinheiro:
    valor: Decimal

    def __post_init__(self) -> None:
        if self.valor < 0:
            raise ValorInvalido(f"dinheiro negativo: {self.valor}")
        if self.valor != self.valor.quantize(CENTAVO):
            raise ValorInvalido(f"dinheiro com mais de 2 casas: {self.valor}; use Dinheiro.de")

    @classmethod
    def de(cls, valor: Numero) -> Dinheiro:
        return cls(para_decimal(valor, "dinheiro").quantize(CENTAVO, rounding=ROUND_HALF_UP))

    def __add__(self, outro: Dinheiro) -> Dinheiro:
        return Dinheiro(self.valor + outro.valor)

    def __str__(self) -> str:
        return f"{self.valor:.2f}"
