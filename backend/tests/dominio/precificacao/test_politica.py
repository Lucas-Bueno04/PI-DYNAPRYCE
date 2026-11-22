"""F0.9: k_pol — P* = κ·max(π_r, τ·H_pad) (Eq. 59) e Proposição 3."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dynaprice.dominio.modelos import (
    Dinheiro,
    Horas,
    Kappa,
    PoliticaVersao,
    Regime,
    ValorInvalido,
    fabricar_politica,
)
from dynaprice.dominio.precificacao import PoliticaDePreco
from tests.dominio.modelos.documentos import documento_tabela_7

POLITICA = fabricar_politica(documento_tabela_7())
horas = st.decimals(min_value=Decimal(0), max_value=Decimal(500), places=4).map(Horas)
kappas = st.decimals(min_value=Decimal(1), max_value=Decimal("1.2"), places=2).map(Kappa)
regimes = st.sampled_from(list(Regime))


def _p(politica: PoliticaVersao = POLITICA) -> PoliticaDePreco:
    return PoliticaDePreco(politica)


def test_tabela_7_sem_piso_vinculante() -> None:
    alvo = _p().preco_alvo(Regime.LP, Horas.de("5.935"))
    assert alvo.valor == Dinheiro.de("614.27")
    assert alvo.exato == Decimal("614.2725")
    assert not alvo.piso_vinculante
    assert alvo.piso == Dinheiro.de("235")
    assert alvo.parcela_esforco == Decimal("614.2725")


def test_piso_vinculante() -> None:
    alvo = _p().preco_alvo(Regime.LP, Horas.de("2"))  # 103,5 x 2 = 207 < 235
    assert alvo.piso_vinculante
    assert alvo.valor == Dinheiro.de("235")


def test_kappa_multiplica_a_base() -> None:
    alvo = _p().preco_alvo(Regime.LP, Horas.de("5.935"), Kappa.de("1.1"))
    assert alvo.valor == Dinheiro.de("675.70")  # 614,2725 x 1,1 = 675,69975


def test_kappa_acima_do_teto_da_politica_e_rejeitado() -> None:
    documento = documento_tabela_7() | {"kappa_maximo": "1.1"}
    with pytest.raises(ValorInvalido):
        _p(fabricar_politica(documento)).preco_alvo(Regime.LP, Horas.de("1"), Kappa.de("1.15"))


def test_ponto_de_quebra_eq_60() -> None:
    assert _p().ponto_de_quebra(Regime.LP) == Horas(Decimal(235) / Decimal("103.5"))


def test_arredondamento_comercial_da_politica() -> None:
    politica = fabricar_politica(documento_tabela_7() | {"arredondamento": {"multiplo": "10"}})
    assert _p(politica).preco_alvo(Regime.LP, Horas.de("5.935")).valor == Dinheiro.de("610")


# --- Proposição 3 ---


@given(regimes, horas, kappas)
def test_a1_a2_preco_cobre_piso_e_esforco(regime: Regime, h: Horas, kappa: Kappa) -> None:
    alvo = _p().preco_alvo(regime, h, kappa)
    assert alvo.exato >= POLITICA.piso(regime).valor
    assert alvo.exato >= POLITICA.tarifa.valor * h.valor


@given(regimes, horas)
def test_minimalidade_com_kappa_um(regime: Regime, h: Horas) -> None:
    alvo = _p().preco_alvo(regime, h)
    assert alvo.exato == max(POLITICA.piso(regime).valor, POLITICA.tarifa.valor * h.valor)


@given(regimes, horas, horas, kappas)
def test_a4_nao_decrescente(regime: Regime, h1: Horas, h2: Horas, kappa: Kappa) -> None:
    baixo, alto = sorted([h1, h2])
    p = _p()
    assert p.preco_alvo(regime, baixo, kappa).exato <= p.preco_alvo(regime, alto, kappa).exato


@given(regimes, horas, horas, kappas)
def test_continuidade_lipschitz(regime: Regime, h1: Horas, h2: Horas, kappa: Kappa) -> None:
    p = _p()
    salto = abs(p.preco_alvo(regime, h1, kappa).exato - p.preco_alvo(regime, h2, kappa).exato)
    assert salto <= kappa.valor * POLITICA.tarifa.valor * abs(h1.valor - h2.valor)


@given(regimes, horas, horas, kappas)
def test_convexidade(regime: Regime, h1: Horas, h2: Horas, kappa: Kappa) -> None:
    p = _p()
    meio = Horas((h1.valor + h2.valor) / 2)
    media = (p.preco_alvo(regime, h1, kappa).exato + p.preco_alvo(regime, h2, kappa).exato) / 2
    assert p.preco_alvo(regime, meio, kappa).exato <= media


@given(regimes, horas)
def test_a3_proporcional_acima_do_ponto_de_quebra(regime: Regime, h: Horas) -> None:
    p = _p()
    dobro = Horas(h.valor * 2)
    if h >= p.ponto_de_quebra(regime):
        assert p.preco_alvo(regime, dobro).exato == 2 * p.preco_alvo(regime, h).exato
