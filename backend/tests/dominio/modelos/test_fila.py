"""Backoff exponencial com teto e variação (decisão F1-FILA)."""

import pytest

from dynaprice.dominio.modelos import ValorInvalido
from dynaprice.dominio.modelos.fila import ParametrosDeFila, atraso_de_backoff

SEM_VARIACAO = ParametrosDeFila(variacao=0.0)


@pytest.mark.parametrize(("tentativa", "esperado"), [(1, 60), (2, 120), (3, 240), (7, 3600)])
def test_backoff_exponencial_com_teto(tentativa: int, esperado: float) -> None:
    assert atraso_de_backoff(tentativa, SEM_VARIACAO, 0.5) == esperado


@pytest.mark.parametrize(("sorteio", "esperado"), [(0.0, 54.0), (1.0, 66.0)])
def test_variacao_de_dez_por_cento(sorteio: float, esperado: float) -> None:
    assert atraso_de_backoff(1, ParametrosDeFila(), sorteio) == pytest.approx(esperado)


def test_heartbeat_precisa_ser_menor_que_o_lease() -> None:
    with pytest.raises(ValorInvalido):
        ParametrosDeFila(lease_s=60, heartbeat_s=60)
