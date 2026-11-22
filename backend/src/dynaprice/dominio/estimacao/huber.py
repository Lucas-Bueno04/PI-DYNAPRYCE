"""m_teq: β das equações de tempo por regressão robusta de Huber (seções 5.8 e 5.9).

t_m = β0,m + Σ β_k,m·x_k (Eq. 36), ajustada sobre horas registradas por empresa-mês com a
perda de Huber (statsmodels RLM + HuberT, c = 1,345): atípicos (seção 9.8) pesam menos.
Inclinação negativa não tem sentido operacional: vira 0 e fica registrada em `truncadas`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import statsmodels.api as sm
from numpy.typing import NDArray

from dynaprice.dominio.estimacao.amostras import AmostraDeDepartamento
from dynaprice.dominio.modelos import EquacaoDeTempo, ValorInvalido

_CASAS = Decimal("0.0001")
_PESO_ATENUADO = 0.999


@dataclass(frozen=True, slots=True)
class EquacaoEstimada:
    equacao: EquacaoDeTempo
    observacoes: int
    fracao_atenuada: float  # fração de linhas com peso de Huber < 1
    truncadas: tuple[str, ...]
    intervalos: Mapping[str, tuple[Decimal, Decimal]]  # IC 95% (β0 em horas, inclinações em min)
    r2: float  # 1 − SQR/SQT das horas registradas
    nao_identificadas: tuple[str, ...] = ()  # direcionadores sem variação na amostra


def _decimal(valor: float) -> Decimal:
    return Decimal(repr(valor)).quantize(_CASAS)


class EstimadorHuber:
    def __init__(self, c: float = 1.345, max_iter: int = 100) -> None:
        self._norma = sm.robust.norms.HuberT(t=c)
        self._max_iter = max_iter

    def estimar(self, amostra: AmostraDeDepartamento) -> EquacaoEstimada:
        nomes = amostra.direcionadores
        if len(amostra.horas) <= len(nomes) + 1:
            raise ValorInvalido(
                f"{amostra.departamento}: {len(amostra.horas)} linhas para {len(nomes) + 1} β"
            )
        matriz = np.asarray(amostra.matriz, dtype=float).reshape(-1, len(nomes))
        variam = _colunas_com_variacao(matriz)
        usados = tuple(nomes[j] for j in variam)
        x = sm.add_constant(matriz[:, variam], has_constant="add")
        y = np.asarray(amostra.horas, dtype=float)
        ajuste = sm.RLM(y, x, M=self._norma).fit(maxiter=self._max_iter)
        beta = dict(zip(("beta0_horas", *usados), map(float, ajuste.params), strict=True))
        return EquacaoEstimada(
            _equacao(amostra, beta),
            len(amostra.horas),
            float(np.mean(np.asarray(ajuste.weights) < _PESO_ATENUADO)),
            tuple(n for n in usados if beta[n] < 0),
            _intervalos(usados, np.asarray(ajuste.conf_int(0.05))),
            _r2(y, np.asarray(ajuste.fittedvalues)),
            tuple(n for n in nomes if n not in usados),
        )


def _colunas_com_variacao(matriz: NDArray[np.float64]) -> list[int]:
    return [j for j in range(matriz.shape[1]) if np.ptp(matriz[:, j]) > 0]


def _equacao(amostra: AmostraDeDepartamento, beta: dict[str, float]) -> EquacaoDeTempo:
    """Inclinação negativa ou não identificada (direcionador sem variação) vira 0."""
    inclinacoes = {n: _decimal(max(beta.get(n, 0.0), 0.0) * 60) for n in amostra.direcionadores}
    return EquacaoDeTempo(
        amostra.departamento, _decimal(max(beta["beta0_horas"], 0.0)), inclinacoes
    )


def _intervalos(
    nomes: tuple[str, ...], limites: NDArray[np.float64]
) -> dict[str, tuple[Decimal, Decimal]]:
    escalas = [("beta0_horas", 1.0)] + [(n, 60.0) for n in nomes]
    return {
        nome: (_decimal(float(baixo) * escala), _decimal(float(alto) * escala))
        for (nome, escala), (baixo, alto) in zip(escalas, limites, strict=True)
    }


def _r2(y: NDArray[np.float64], ajustado: NDArray[np.float64]) -> float:
    return float(1 - np.sum((y - ajustado) ** 2) / np.sum((y - y.mean()) ** 2))
