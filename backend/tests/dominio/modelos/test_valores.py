"""F0.5: objetos de valor do domínio (principios.md §3) — invariantes do artigo no tipo."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dynaprice.dominio.modelos import (
    Competencia,
    DescontoNegociado,
    Dinheiro,
    Horas,
    Kappa,
    Regime,
    Tarifa,
    ValorInvalido,
)


class TestDinheiro:
    def test_arredonda_centavos_meio_para_cima(self) -> None:
        # D11: ROUND_HALF_UP, 2 casas — 103,5 x 5,935 = 614,2725 -> 614,27
        assert Dinheiro.de(Decimal("614.2725")).valor == Decimal("614.27")
        assert Dinheiro.de(Decimal("0.125")).valor == Decimal("0.13")

    def test_recusa_float(self) -> None:
        with pytest.raises(ValorInvalido):
            Dinheiro.de(0.1)  # type: ignore[arg-type]

    def test_aceita_texto_e_inteiro(self) -> None:
        assert Dinheiro.de("437").valor == Decimal("437.00")
        assert Dinheiro.de(235).valor == Decimal("235.00")

    def test_recusa_negativo(self) -> None:
        with pytest.raises(ValorInvalido):
            Dinheiro.de("-1")

    def test_soma_e_ordem(self) -> None:
        assert Dinheiro.de("1.10") + Dinheiro.de("2.20") == Dinheiro.de("3.30")
        assert Dinheiro.de("1") < Dinheiro.de("2")

    def test_imutavel(self) -> None:
        d = Dinheiro.de("1")
        with pytest.raises(FrozenInstanceError):
            d.valor = Decimal("2")  # type: ignore[misc]


class TestHorasETarifa:
    def test_horas_nao_negativas(self) -> None:
        assert Horas.de("5.935").valor == Decimal("5.935")
        with pytest.raises(ValorInvalido):
            Horas.de("-0.1")

    def test_tarifa_positiva(self) -> None:
        assert Tarifa.de("103.5").valor == Decimal("103.5")
        for invalido in ("0", "-3"):
            with pytest.raises(ValorInvalido):
                Tarifa.de(invalido)

    def test_tarifa_vezes_horas_e_decimal_exato(self) -> None:
        assert Tarifa.de("103.5") * Horas.de("5.935") == Decimal("614.2725")


class TestKappa:
    @given(st.decimals(min_value=Decimal("1.0"), max_value=Decimal("1.2"), places=3))
    def test_aceita_faixa_d12(self, valor: Decimal) -> None:
        assert Kappa.de(valor).valor == valor

    @given(
        st.one_of(
            st.decimals(max_value=Decimal("0.999"), allow_nan=False, allow_infinity=False),
            st.decimals(min_value=Decimal("1.201"), allow_nan=False, allow_infinity=False),
        )
    )
    def test_rejeita_fora_da_faixa(self, valor: Decimal) -> None:
        # Eq. (59): 1 <= κ <= κ̄; κ < 1 quebraria A1/A2 (D12 revisada)
        with pytest.raises(ValorInvalido):
            Kappa.de(valor)

    def test_teto_menor_da_politica(self) -> None:
        with pytest.raises(ValorInvalido):
            Kappa.de("1.15", maximo=Decimal("1.1"))

    def test_neutro(self) -> None:
        assert Kappa.neutro().valor == Decimal("1")


class TestDescontoNegociado:
    def test_ate_cinco_por_cento_sem_justificativa(self) -> None:
        assert DescontoNegociado.de("0.05").percentual == Decimal("0.05")

    def test_acima_de_cinco_por_cento_exige_justificativa(self) -> None:
        with pytest.raises(ValorInvalido):
            DescontoNegociado.de("0.06")
        d = DescontoNegociado.de("0.06", justificativa="cliente estratégico")
        assert d.justificativa == "cliente estratégico"

    def test_faixa(self) -> None:
        for invalido in ("-0.01", "1"):
            with pytest.raises(ValorInvalido):
                DescontoNegociado.de(invalido, justificativa="x")

    def test_aplicar_fica_fora_da_regra_de_preco(self) -> None:
        assert DescontoNegociado.de("0.10", justificativa="x").aplicar(
            Dinheiro.de("100")
        ) == Dinheiro.de("90")
        assert DescontoNegociado.nenhum().aplicar(Dinheiro.de("100")) == Dinheiro.de("100")


class TestCompetencia:
    def test_ordem_e_navegacao(self) -> None:
        c = Competencia(2026, 12)
        assert c.proxima() == Competencia(2027, 1)
        assert Competencia(2027, 1).anterior() == c
        assert Competencia(2026, 1) < Competencia(2026, 2)

    def test_meses_ate(self) -> None:
        assert Competencia(2025, 11).meses_ate(Competencia(2026, 10)) == 11

    def test_mes_invalido(self) -> None:
        with pytest.raises(ValorInvalido):
            Competencia(2026, 13)

    def test_texto(self) -> None:
        assert str(Competencia(2026, 3)) == "2026-03"
        assert Competencia.de_texto("2026-03") == Competencia(2026, 3)


def test_regimes_do_adr_004() -> None:
    assert [r.value for r in Regime] == ["MEI", "SN", "LP", "LR"]
