"""F0.8: k_teq — horas-padrão por departamento (Eq. 36; Tabela 7; seções 6.3 e 6.6)."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dynaprice.dominio.modelos import (
    Competencia,
    Departamento,
    Direcionadores,
    Empresa,
    Horas,
    PoliticaVersao,
    Regime,
    ValorInvalido,
    fabricar_politica,
)
from dynaprice.dominio.precificacao import EquacoesDeTempo, media_dos_direcionadores
from tests.dominio.modelos.documentos import documento_tabela_7

TABELA_7 = {
    "notas_entrada": Decimal(30),
    "lancamentos_manuais": Decimal(40),
    "empregados": Decimal(2),
}


@pytest.fixture
def politica() -> PoliticaVersao:
    return fabricar_politica(documento_tabela_7())


def test_tabela_7(politica: PoliticaVersao) -> None:
    hpad = EquacoesDeTempo(politica).horas_padrao(Empresa("e", Regime.LP), TABELA_7)
    assert hpad.horas(Departamento.FISCAL) == Decimal("2.785")
    assert round(hpad.horas(Departamento.CONTABIL), 3) == Decimal("2.483")
    assert round(hpad.horas(Departamento.FOLHA), 3) == Decimal("0.667")
    assert hpad.total == Horas.de("5.935")  # exato, sem resíduo de dízima


def test_so_departamentos_atendidos(politica: PoliticaVersao) -> None:
    folha = Empresa("f", Regime.SN, frozenset({Departamento.FOLHA}))
    hpad = EquacoesDeTempo(politica).horas_padrao(folha, TABELA_7)
    assert hpad.departamentos == frozenset({Departamento.FOLHA})
    assert round(hpad.total.valor, 3) == Decimal("0.667")
    assert hpad.horas(Departamento.FISCAL) == Decimal(0)


def test_direcionador_ausente_vale_zero(politica: PoliticaVersao) -> None:
    hpad = EquacoesDeTempo(politica).horas_padrao(Empresa("e", Regime.LP), {})
    assert hpad.total == Horas.de("1.75")  # Σ β0 (seção 6.6)


def test_equacao_do_regime(politica: PoliticaVersao) -> None:
    documento = documento_tabela_7()
    documento["equacoes_de_tempo"].append(
        {"departamento": "fiscal", "regime": "LR", "beta0_horas": "2", "inclinacoes_minutos": {}}
    )
    hpad = EquacoesDeTempo(fabricar_politica(documento)).horas_padrao(
        Empresa("e", Regime.LR), TABELA_7
    )
    assert hpad.horas(Departamento.FISCAL) == Decimal(2)


def test_departamento_atendido_sem_equacao() -> None:
    documento = documento_tabela_7()
    documento["equacoes_de_tempo"].pop()  # sem folha
    with pytest.raises(ValorInvalido):
        EquacoesDeTempo(fabricar_politica(documento)).horas_padrao(
            Empresa("e", Regime.LP), TABELA_7
        )


contagens = st.dictionaries(
    st.sampled_from(["notas_entrada", "lancamentos_manuais", "empregados"]),
    st.integers(min_value=0, max_value=5000).map(Decimal),
)


@given(contagens)
def test_horas_padrao_nunca_abaixo_da_soma_dos_beta0(valores: dict[str, Decimal]) -> None:
    politica = fabricar_politica(documento_tabela_7())
    hpad = EquacoesDeTempo(politica).horas_padrao(Empresa("e", Regime.SN), valores)
    assert hpad.total.valor >= Decimal("1.75")


@given(st.lists(contagens, min_size=1, max_size=12))
def test_equacao_da_media_e_a_media_das_equacoes(meses: list[dict[str, Decimal]]) -> None:
    """Seção 6.3: equações afins => t(x̄) = média dos t(x_t)."""
    politica = fabricar_politica(documento_tabela_7())
    equacoes = EquacoesDeTempo(politica)
    empresa = Empresa("e", Regime.SN)
    registros = [
        Direcionadores("e", Competencia(2025, 1).somar(i), valores)
        for i, valores in enumerate(meses)
    ]
    da_media = equacoes.horas_padrao(empresa, media_dos_direcionadores(registros)).total.valor
    mensais = [equacoes.horas_padrao(empresa, m).total.valor for m in meses]
    assert da_media == pytest.approx(sum(mensais) / len(mensais), abs=Decimal("1e-20"))


def test_media_dos_direcionadores() -> None:
    meses = [
        Direcionadores("e", Competencia(2025, 1), {"a": Decimal(10)}),
        Direcionadores("e", Competencia(2025, 2), {"a": Decimal(20), "b": Decimal(3)}),
    ]
    assert media_dos_direcionadores(meses) == {"a": Decimal(15), "b": Decimal("1.5")}


def test_media_sem_meses() -> None:
    with pytest.raises(ValorInvalido):
        media_dos_direcionadores([])
