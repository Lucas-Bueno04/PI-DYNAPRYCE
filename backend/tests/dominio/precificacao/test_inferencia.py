"""F0.11: k_inf — cascata da ADR-004 (Quadro 3 adaptado; Eq. 56 e 79)."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dynaprice.dominio.modelos import (
    Dinheiro,
    Horas,
    Kappa,
    Regime,
    ValorInvalido,
    fabricar_politica,
)
from dynaprice.dominio.precificacao import (
    InferenciaDePreco,
    NivelDeInformacao,
    PisoDoRegime,
    PoliticaDePreco,
    fator_de_credibilidade,
    nivel_de_informacao,
)
from tests.dominio.modelos.documentos import documento_tabela_7

POLITICA = fabricar_politica(documento_tabela_7())  # s²/v² = 2
INFERENCIA = InferenciaDePreco(PoliticaDePreco(POLITICA), PisoDoRegime(POLITICA))
horas = st.decimals(min_value=Decimal(0), max_value=Decimal(300), places=3).map(Horas)
kappas = st.decimals(min_value=Decimal(1), max_value=Decimal("1.2"), places=2).map(Kappa)


def test_niveis() -> None:
    assert nivel_de_informacao(0) is NivelDeInformacao.SEM_HISTORICO
    assert nivel_de_informacao(5) is NivelDeInformacao.PARCIAL
    assert nivel_de_informacao(12) is NivelDeInformacao.COMPLETO
    assert nivel_de_informacao(15) is NivelDeInformacao.COMPLETO
    assert NivelDeInformacao.COMPLETO.ell == 2 and NivelDeInformacao.PARCIAL.ell == 1
    with pytest.raises(ValorInvalido):
        nivel_de_informacao(-1)


def test_credibilidade_eq_56() -> None:
    assert fator_de_credibilidade(0, Decimal(2)) == 0
    assert fator_de_credibilidade(6, Decimal(2)) == Decimal("0.75")
    assert fator_de_credibilidade(12, Decimal(2)) == Decimal(12) / 14


@given(st.integers(0, 11), st.decimals(min_value=Decimal("0.01"), max_value=Decimal(100), places=2))
def test_credibilidade_cresce_com_os_meses(m: int, razao: Decimal) -> None:
    z, z_mais = fator_de_credibilidade(m, razao), fator_de_credibilidade(m + 1, razao)
    assert 0 <= z < z_mais < 1


def test_sem_historico_e_o_piso_do_regime() -> None:
    preco = INFERENCIA.preco(Regime.LP, None, meses=0)
    assert preco.valor == Dinheiro.de("235")
    assert preco.provisorio
    assert preco.nivel is NivelDeInformacao.SEM_HISTORICO
    assert preco.credibilidade == 0


def test_parcial_combina_eq_79() -> None:
    preco = INFERENCIA.preco(Regime.LP, Horas.de("5.935"), meses=6)  # Z = 0,75
    esperado = Decimal("0.75") * Decimal("614.2725") + Decimal("0.25") * 235
    assert preco.exato == esperado
    assert preco.valor == Dinheiro.de(esperado)
    assert preco.provisorio


def test_completo_delega_a_k_pol() -> None:
    preco = INFERENCIA.preco(Regime.LP, Horas.de("5.935"), meses=12)
    assert preco.valor == Dinheiro.de("614.27")
    assert not preco.provisorio
    assert preco.alvo is not None and not preco.alvo.piso_vinculante


def test_regime_ausente_e_rejeitado() -> None:
    with pytest.raises(ValorInvalido, match="regime"):
        INFERENCIA.preco(None, Horas.de("1"), meses=3)


def test_com_meses_exige_horas() -> None:
    with pytest.raises(ValorInvalido):
        INFERENCIA.preco(Regime.SN, None, meses=3)


@given(st.sampled_from(list(Regime)), horas, st.integers(1, 11), kappas)
def test_parcial_fica_entre_o_piso_e_o_alvo_proprio(
    regime: Regime, h: Horas, m: int, kappa: Kappa
) -> None:
    preco = INFERENCIA.preco(regime, h, meses=m, kappa=kappa)
    piso = POLITICA.piso(regime).valor
    alvo = kappa.valor * max(piso, POLITICA.tarifa * h)
    assert piso <= preco.exato <= alvo  # A1/A2 preservados (seção 6.9)
