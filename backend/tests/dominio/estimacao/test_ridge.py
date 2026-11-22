"""F0.17: m_esf — modelo multiplicativo de esforço com Ridge (Eq. 41–45), fora da fórmula (E2)."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dynaprice.dominio.estimacao import (
    AmostraDeEsforco,
    RegressaoRidge,
    amostra_de_esforco,
    graus_de_liberdade,
    ridge_fechado,
)
from dynaprice.dominio.modelos import Carteira, ValorInvalido


def _aleatorio(semente: int, n: int = 60, p: int = 4) -> tuple[np.ndarray, np.ndarray]:
    gerador = np.random.default_rng(semente)
    x = gerador.normal(size=(n, p))
    y = x @ np.arange(1, p + 1) + gerador.normal(scale=0.5, size=n)
    return x, y


@settings(max_examples=30)
@given(st.integers(0, 10_000), st.floats(0.01, 1000))
def test_eq_44_coincide_com_minimos_quadrados_aumentados(semente: int, lam: float) -> None:
    x, y = _aleatorio(semente)
    aumentada = np.vstack([x, np.sqrt(lam) * np.eye(x.shape[1])])
    alvo = np.concatenate([y, np.zeros(x.shape[1])])
    esperado = np.linalg.lstsq(aumentada, alvo, rcond=None)[0]
    np.testing.assert_allclose(ridge_fechado(x, y, lam), esperado, rtol=1e-8, atol=1e-10)


def test_lambda_zero_e_mqo() -> None:
    x, y = _aleatorio(1)
    np.testing.assert_allclose(ridge_fechado(x, y, 0.0), np.linalg.lstsq(x, y, rcond=None)[0])


def test_graus_de_liberdade_eq_45() -> None:
    x, _ = _aleatorio(2)
    assert graus_de_liberdade(x, 0.0) == pytest.approx(x.shape[1])
    valores = [graus_de_liberdade(x, lam) for lam in (0.1, 1, 10, 100)]
    assert valores == sorted(valores, reverse=True)


@pytest.fixture(scope="module")
def amostra(carteira: Carteira) -> AmostraDeEsforco:
    return amostra_de_esforco(carteira)


def test_amostra_log_log(amostra: AmostraDeEsforco, carteira: Carteira) -> None:
    assert len(amostra.y) == len(amostra.matriz) <= len(carteira.empresas)
    assert "ln1p_lancamentos_manuais" in amostra.nomes
    assert {"regime_SN", "regime_LP", "regime_LR"} <= set(amostra.nomes)  # MEI é a base


def test_ridge_na_carteira_sintetica(amostra: AmostraDeEsforco) -> None:
    modelo = RegressaoRidge(semente=0).ajustar(amostra)
    assert modelo.lam in RegressaoRidge().grade
    assert 0.4 <= modelo.r2_validacao <= 0.95  # artigo: ≈ 0,77 em validação cruzada (9.8)
    assert modelo.elasticidades["ln1p_lancamentos_manuais"] > 0
    assert modelo.elasticidades["ln1p_empregados"] > 0
    assert 0 < modelo.graus_de_liberdade <= len(amostra.nomes)
    previsto = modelo.prever(np.asarray(amostra.matriz))
    assert previsto.shape == (len(amostra.y),)


def test_reprodutivel(amostra: AmostraDeEsforco) -> None:
    a = RegressaoRidge(semente=3).ajustar(amostra)
    b = RegressaoRidge(semente=3).ajustar(amostra)
    assert a.lam == b.lam and a.elasticidades == b.elasticidades


def test_amostra_pequena() -> None:
    pequena = AmostraDeEsforco(("x",), ((1.0,), (2.0,)), (0.1, 0.2))
    with pytest.raises(ValorInvalido):
        RegressaoRidge(dobras=5).ajustar(pequena)
