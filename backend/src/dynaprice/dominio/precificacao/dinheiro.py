"""k_din: ponto único de arredondamento do preço (D11).

Strategy: o artigo admite arredondamento comercial como variante da política (seção 6.5);
o padrão é ao centavo, ROUND_HALF_UP, e o comercial só entra por parâmetro da política.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from dynaprice.dominio.modelos import Dinheiro, PoliticaVersao, ValorInvalido


class Arredondamento(Protocol):
    def arredondar(self, valor: Decimal) -> Dinheiro: ...


class ArredondamentoAoCentavo:
    def arredondar(self, valor: Decimal) -> Dinheiro:
        return Dinheiro.de(valor)


class ArredondamentoComercial:
    """Múltiplo de `multiplo` u.m. mais próximo, meio para cima (ex.: 5 ou 10)."""

    def __init__(self, multiplo: Decimal) -> None:
        if multiplo <= 0:
            raise ValorInvalido(f"múltiplo de arredondamento deve ser > 0: {multiplo}")
        self._multiplo = multiplo

    def arredondar(self, valor: Decimal) -> Dinheiro:
        unidades = (valor / self._multiplo).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        return Dinheiro.de(unidades * self._multiplo)


def arredondamento_da_politica(politica: PoliticaVersao) -> Arredondamento:
    if politica.arredondamento_multiplo is None:
        return ArredondamentoAoCentavo()
    return ArredondamentoComercial(politica.arredondamento_multiplo)
