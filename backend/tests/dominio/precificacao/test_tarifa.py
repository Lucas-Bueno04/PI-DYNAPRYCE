"""F0.13: k_tar — τ̂ (Eq. 65), τ* exata (Prop. 5, Eq. 67), custo (Eq. 63–64) e Proposição 7."""

from decimal import Decimal

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from dynaprice.dominio.modelos import Dinheiro, Horas, Kappa, Regime, ValorInvalido
from dynaprice.dominio.precificacao import (
    ObservacaoDeTarifa,
    TarifaAncoradaEmCusto,
    TarifaPorPrecoRevelado,
    TarifaPorReceitaAlvo,
    margem_implicita,
    receita,
    tarifa_por_bissecao,
)

PISOS = {
    Regime.MEI: Dinheiro.de("80"),
    Regime.SN: Dinheiro.de("185"),
    Regime.LP: Dinheiro.de("235"),
    Regime.LR: Dinheiro.de("340"),
}
TOLERANCIA = Decimal("1e-15")


def _obs(regime: Regime, h: str, f: str, kappa: str = "1") -> ObservacaoDeTarifa:
    return ObservacaoDeTarifa(regime, Horas.de(h), Dinheiro.de(f), Kappa.de(kappa))


CARTEIRA = [
    _obs(Regime.LP, "5.935", "437"),
    _obs(Regime.SN, "2", "250"),
    _obs(Regime.SN, "1", "200"),
    _obs(Regime.LR, "12", "900", "1.1"),
]


def test_preco_revelado_eq_65() -> None:
    tau = TarifaPorPrecoRevelado().estimar(CARTEIRA, PISOS)
    assert tau.valor == Decimal(1787) / Decimal("20.935")


def test_preco_revelado_sem_horas() -> None:
    with pytest.raises(ValorInvalido):
        TarifaPorPrecoRevelado().estimar([], PISOS)


def test_receita_eq_66() -> None:
    # τ = 100: LP 593,5; SN max(185, 200) = 200; SN 185; LR 1,1 x 1200 = 1320
    assert receita(Decimal(100), CARTEIRA, PISOS) == Decimal("2298.5")


def test_receita_alvo_atinge_a_receita() -> None:
    tau = TarifaPorReceitaAlvo(Decimal(2000)).estimar(CARTEIRA, PISOS)
    assert receita(tau.valor, CARTEIRA, PISOS) == pytest.approx(Decimal(2000), abs=TOLERANCIA)


def test_receita_alvo_abaixo_da_soma_dos_pisos_nao_tem_solucao() -> None:
    """Prop. 4 exige Σ κ·π_r < R_alvo."""
    with pytest.raises(ValorInvalido):
        TarifaPorReceitaAlvo(Decimal(900)).estimar(CARTEIRA, PISOS)


def test_receita_constante_e_tau_estrela() -> None:
    tau_estrela = TarifaPorReceitaAlvo.receita_constante(CARTEIRA).estimar(CARTEIRA, PISOS)
    assert receita(tau_estrela.valor, CARTEIRA, PISOS) == pytest.approx(
        Decimal(1787), abs=TOLERANCIA
    )


def test_ancorada_em_custo_eq_63_e_64() -> None:
    tau = TarifaAncoradaEmCusto(Decimal(60), Decimal("0.85"), Decimal("0.3")).estimar([], PISOS)
    assert tau.valor == Decimal(60) / Decimal("0.85") * Decimal("1.3")
    assert margem_implicita(tau.valor, Decimal("0.85"), Decimal(60)) == pytest.approx(
        Decimal("0.3"), abs=TOLERANCIA
    )


observacoes = st.lists(
    st.builds(
        ObservacaoDeTarifa,
        st.sampled_from(list(Regime)),
        st.decimals(min_value=Decimal("0.5"), max_value=Decimal(30), places=2).map(Horas),
        st.decimals(min_value=Decimal(50), max_value=Decimal(3000), places=2).map(Dinheiro),
        st.decimals(min_value=Decimal(1), max_value=Decimal("1.2"), places=2).map(Kappa),
    ),
    min_size=1,
    max_size=40,
)


def _preco(o: ObservacaoDeTarifa, tau: Decimal) -> Decimal:
    return o.kappa.valor * max(PISOS[o.regime].valor, tau * o.horas_padrao.valor)


@settings(max_examples=150)
@given(observacoes)
def test_proposicao_7(carteira: list[ObservacaoDeTarifa]) -> None:
    r0 = sum((o.honorario.valor for o in carteira), Decimal(0))
    assume(sum(o.kappa.valor * PISOS[o.regime].valor for o in carteira) < r0)
    tau_chapeu = TarifaPorPrecoRevelado().estimar(carteira, PISOS).valor
    tau_estrela = TarifaPorReceitaAlvo.receita_constante(carteira).estimar(carteira, PISOS).valor
    c = tau_chapeu / tau_estrela
    assert tau_chapeu >= tau_estrela - TOLERANCIA  # (a)
    for o in carteira:  # (b)
        assert _preco(o, tau_estrela) <= _preco(o, tau_chapeu) + TOLERANCIA
        assert _preco(o, tau_chapeu) <= c * _preco(o, tau_estrela) + TOLERANCIA * 1000
    r_chapeu = receita(tau_chapeu, carteira, PISOS)  # (c)
    assert r0 - TOLERANCIA * 1000 <= r_chapeu <= c * r0 + TOLERANCIA * 1000


@settings(max_examples=150)
@given(observacoes, st.decimals(min_value=Decimal("1.01"), max_value=Decimal(3), places=2))
def test_proposicao_5_solucao_exata_coincide_com_bissecao(
    carteira: list[ObservacaoDeTarifa], fator: Decimal
) -> None:
    soma_pisos = sum(o.kappa.valor * PISOS[o.regime].valor for o in carteira)
    alvo = soma_pisos * fator
    exata = TarifaPorReceitaAlvo(alvo).estimar(carteira, PISOS).valor
    numerica = tarifa_por_bissecao(carteira, PISOS, alvo, precisao=Decimal("1e-9"))
    assert abs(exata - numerica) <= Decimal("1e-8")
