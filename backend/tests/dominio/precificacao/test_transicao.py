"""F0.12: k_tr — transição limitada com congelamento (Eq. 72, Algoritmo 3) e Proposição 8."""

from decimal import Decimal

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from dynaprice.dominio.modelos import Dinheiro, ValorInvalido
from dynaprice.dominio.precificacao import (
    ArredondamentoAoCentavo,
    ArredondamentoComercial,
    MotivoDoPasso,
    RegraDeTransicao,
    ciclos_ate_o_alvo,
)

THETA = Decimal("0.15")
REGRA = RegraDeTransicao(THETA, ArredondamentoAoCentavo())
precos = st.decimals(min_value=Decimal(50), max_value=Decimal(5000), places=2).map(Dinheiro)
inflacoes = st.decimals(min_value=Decimal(0), max_value=Decimal("0.12"), places=3)


def test_trajetoria_da_tabela_7() -> None:
    """D11: trajetória exata 437 → 502,55 → 577,93 → 614,27 (artigo: 437, 503, 578, 614,27)."""
    alvo, preco, trajetoria = Dinheiro.de("614.27"), Dinheiro.de("437"), []
    for _ in range(4):
        preco = REGRA.proximo(preco, alvo).novo
        trajetoria.append(preco)
    assert trajetoria == [Dinheiro.de(v) for v in ("502.55", "577.93", "614.27", "614.27")]
    assert ciclos_ate_o_alvo(Decimal("614.27") / 437, THETA) == 3  # Eq. (98)


def test_motivos() -> None:
    assert REGRA.proximo(Dinheiro.de("437"), Dinheiro.de("614.27")).motivo is MotivoDoPasso.TETO
    assert REGRA.proximo(Dinheiro.de("600"), Dinheiro.de("614.27")).motivo is MotivoDoPasso.ALVO
    congelado = REGRA.proximo(Dinheiro.de("700"), Dinheiro.de("614.27"))
    assert congelado.motivo is MotivoDoPasso.CONGELADO
    assert congelado.novo == Dinheiro.de("700")


def test_inflacao_corrige_antes_do_teto() -> None:
    passo = REGRA.proximo(Dinheiro.de("100"), Dinheiro.de("200"), inflacao=Decimal("0.04"))
    assert passo.corrigido == Decimal("104.00")
    assert passo.novo == Dinheiro.de("119.60")  # 104 x 1,15


def test_alvo_abaixo_do_vigente_corrigido_congela_nominal() -> None:
    passo = REGRA.proximo(Dinheiro.de("100"), Dinheiro.de("102"), inflacao=Decimal("0.04"))
    assert passo.novo == Dinheiro.de("102")  # max(P*, P) com P* < B


def test_revisao_integral_vai_ao_alvo_nos_dois_sentidos() -> None:
    """Seção 6.7: provisório que chega a ℓ = 2 vai ao alvo sem θ e sem congelamento."""
    sobe = REGRA.proximo(Dinheiro.de("235"), Dinheiro.de("614.27"), revisao_integral=True)
    desce = REGRA.proximo(Dinheiro.de("700"), Dinheiro.de("614.27"), revisao_integral=True)
    assert sobe.novo == desce.novo == Dinheiro.de("614.27")
    assert sobe.motivo is MotivoDoPasso.REVISAO_INTEGRAL


def test_inflacao_negativa_recusada() -> None:
    with pytest.raises(ValorInvalido):
        REGRA.proximo(Dinheiro.de("100"), Dinheiro.de("200"), inflacao=Decimal("-0.01"))


def test_theta_negativo_recusado() -> None:
    with pytest.raises(ValorInvalido):
        RegraDeTransicao(Decimal("-0.1"), ArredondamentoAoCentavo())


# --- Proposição 8 ---


@given(precos, precos, inflacoes)
def test_a_nominal_nunca_diminui(vigente: Dinheiro, alvo: Dinheiro, pi: Decimal) -> None:
    assert REGRA.proximo(vigente, alvo, inflacao=pi).novo >= vigente


@given(precos, precos, inflacoes)
def test_b_alta_real_limitada(vigente: Dinheiro, alvo: Dinheiro, pi: Decimal) -> None:
    passo = REGRA.proximo(vigente, alvo, inflacao=pi)
    assert passo.novo.valor <= passo.corrigido * (1 + THETA) + Decimal("0.005")


@given(precos, precos, inflacoes)
def test_c_nunca_ultrapassa_o_alvo_partindo_de_baixo(
    vigente: Dinheiro, alvo: Dinheiro, pi: Decimal
) -> None:
    assume(vigente <= alvo)
    assert REGRA.proximo(vigente, alvo, inflacao=pi).novo <= alvo


@given(precos, st.decimals(min_value=Decimal("1.01"), max_value=Decimal(4), places=3))
def test_d_chega_em_teto_de_ln_g_sobre_ln_1_mais_theta(inicial: Dinheiro, g: Decimal) -> None:
    alvo = Dinheiro.de(inicial.valor * g)
    distancia = alvo.valor / inicial.valor
    t = ciclos_ate_o_alvo(distancia, THETA)
    # fora da vizinhança de (1+θ)^t = G, onde o centavo decide o ciclo
    assume(all(abs((1 + THETA) ** k / distancia - 1) > Decimal("0.001") for k in (t - 1, t)))
    preco, ciclos = inicial, 0
    while preco < alvo:
        preco, ciclos = REGRA.proximo(preco, alvo).novo, ciclos + 1
    assert ciclos == t


@given(precos, precos)
def test_comercial_preserva_a_e_c(vigente: Dinheiro, alvo: Dinheiro) -> None:
    regra = RegraDeTransicao(THETA, ArredondamentoComercial(Decimal(5)))
    novo = regra.proximo(vigente, alvo).novo
    assert novo >= vigente
    if vigente <= alvo:
        assert novo <= alvo
