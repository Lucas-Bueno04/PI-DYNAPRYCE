"""F0.7: k_din — arredondamento como Strategy; comercial só por parâmetro da política (D11)."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dynaprice.dominio.modelos import Dinheiro, ValorInvalido, fabricar_politica
from dynaprice.dominio.precificacao import (
    ArredondamentoAoCentavo,
    ArredondamentoComercial,
    arredondamento_da_politica,
)
from tests.dominio.modelos.documentos import documento_tabela_7

valores = st.decimals(min_value=Decimal(0), max_value=Decimal(10**6), places=6)


def test_centavo_meio_para_cima() -> None:
    r = ArredondamentoAoCentavo()
    assert r.arredondar(Decimal("614.2725")) == Dinheiro.de("614.27")
    assert r.arredondar(Decimal("502.5500")) == Dinheiro.de("502.55")
    assert r.arredondar(Decimal("577.9325")) == Dinheiro.de("577.93")
    assert r.arredondar(Decimal("0.005")) == Dinheiro.de("0.01")


@pytest.mark.parametrize(
    ("multiplo", "valor", "esperado"),
    [("5", "502.55", "505"), ("5", "502.49", "500"), ("10", "614.27", "610"), ("10", "615", "620")],
)
def test_comercial_ao_multiplo_meio_para_cima(multiplo: str, valor: str, esperado: str) -> None:
    r = ArredondamentoComercial(Decimal(multiplo))
    assert r.arredondar(Decimal(valor)) == Dinheiro.de(esperado)


def test_comercial_recusa_multiplo_nao_positivo() -> None:
    with pytest.raises(ValorInvalido):
        ArredondamentoComercial(Decimal(0))


@given(valores)
def test_centavo_erra_no_maximo_meio_centavo(valor: Decimal) -> None:
    assert abs(ArredondamentoAoCentavo().arredondar(valor).valor - valor) <= Decimal("0.005")


@given(valores, st.sampled_from([Decimal(5), Decimal(10)]))
def test_comercial_e_multiplo_e_proximo(valor: Decimal, multiplo: Decimal) -> None:
    arredondado = ArredondamentoComercial(multiplo).arredondar(valor).valor
    assert arredondado % multiplo == 0
    assert abs(arredondado - valor) <= multiplo / 2


def test_politica_padrao_arredonda_ao_centavo() -> None:
    politica = fabricar_politica(documento_tabela_7())
    assert politica.arredondamento_multiplo is None
    assert isinstance(arredondamento_da_politica(politica), ArredondamentoAoCentavo)


def test_politica_com_arredondamento_comercial() -> None:
    documento = documento_tabela_7() | {"arredondamento": {"multiplo": "5"}}
    politica = fabricar_politica(documento)
    assert politica.arredondamento_multiplo == Decimal(5)
    r = arredondamento_da_politica(politica)
    assert r.arredondar(Decimal("502.55")) == Dinheiro.de("505")


def test_politica_recusa_multiplo_invalido() -> None:
    with pytest.raises(ValorInvalido):
        fabricar_politica(documento_tabela_7() | {"arredondamento": {"multiplo": "-5"}})
