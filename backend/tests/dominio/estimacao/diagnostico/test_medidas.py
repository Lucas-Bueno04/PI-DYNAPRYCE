"""F0.19: medidas do diagnóstico (seções 5.4–5.6 e 9.4–9.5 do artigo)."""

import pytest

from dynaprice.dominio.estimacao.diagnostico import (
    gini,
    indices_de_alinhamento,
    percentil,
    regra_afim,
)


def test_gini_igualdade_e_concentracao() -> None:
    assert gini([5, 5, 5, 5]) == pytest.approx(0.0)
    assert gini([0, 0, 0, 10]) == pytest.approx(0.75)  # (n-1)/n para um só com tudo
    assert gini([1, 2, 3, 4]) == pytest.approx(0.25)


def test_gini_vazio_ou_negativo() -> None:
    with pytest.raises(ValueError):
        gini([])
    with pytest.raises(ValueError):
        gini([1, -1])


def test_regra_afim_mqo_eq_12() -> None:
    a, b, r2 = regra_afim([1, 2, 3, 4], [215, 245, 277, 309])
    assert a == pytest.approx(183.0, abs=1e-9) and b == pytest.approx(31.4, abs=1e-9)
    assert 0.99 < r2 <= 1


def test_indice_de_alinhamento_eq_5_6() -> None:
    """I_i = (F_i / ΣF) / (H_i / ΣH): 1 quando o preço acompanha o esforço."""
    assert indices_de_alinhamento([100, 200], [1, 2]) == pytest.approx([1.0, 1.0])
    assert indices_de_alinhamento([300, 100], [1, 1]) == pytest.approx([1.5, 0.5])


def test_percentil_linear() -> None:
    assert percentil([10, 20, 30, 40, 50], 0.5) == 30
    assert percentil([10, 20, 30, 40, 50], 0.1) == pytest.approx(14)
