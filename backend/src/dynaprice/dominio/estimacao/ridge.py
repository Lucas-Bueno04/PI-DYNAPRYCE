"""m_esf: Ridge sobre o modelo log-log (Eq. 43–45). Controle e diagnóstico, fora do preço (E2).

Colunas padronizadas, y centrado, intercepto sem penalidade; λ escolhido entre 20 valores
em escala log de 1e-2 a 1e3 por validação cruzada interna de K partes (seção 5.11).
"""

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from dynaprice.dominio.estimacao.esforco import AmostraDeEsforco
from dynaprice.dominio.modelos import ValorInvalido

type Matriz = NDArray[np.float64]

GRADE_PADRAO: tuple[float, ...] = tuple(float(v) for v in np.logspace(-2, 3, 20))


def ridge_fechado(x: Matriz, y: Matriz, lam: float) -> Matriz:
    """β̂_λ = (XᵀX + λI)⁻¹ Xᵀy (Eq. 44)."""
    p = x.shape[1]
    return np.linalg.solve(x.T @ x + lam * np.eye(p), x.T @ y)


def graus_de_liberdade(x: Matriz, lam: float) -> float:
    """gl(λ) = Σ d_j² / (d_j² + λ) (Eq. 45)."""
    d2 = np.linalg.svd(x, compute_uv=False) ** 2
    return float(np.sum(d2 / (d2 + lam)))


@dataclass(frozen=True, slots=True)
class ModeloRidge:
    nomes: tuple[str, ...]
    lam: float
    intercepto: float
    coeficientes: tuple[float, ...]  # na escala original de cada coluna
    graus_de_liberdade: float
    r2: float
    r2_validacao: float

    @property
    def elasticidades(self) -> dict[str, float]:
        """β_j de ln(1 + x_j): elasticidade parcial do esforço (Eq. 42)."""
        return dict(zip(self.nomes, self.coeficientes, strict=True))

    def prever(self, matriz: Matriz) -> Matriz:
        return np.asarray(self.intercepto + matriz @ np.asarray(self.coeficientes), dtype=float)


def _r2(y: Matriz, previsto: Matriz) -> float:
    return float(1 - np.sum((y - previsto) ** 2) / np.sum((y - y.mean()) ** 2))


@dataclass(frozen=True, slots=True)
class _Padronizacao:
    media: Matriz
    desvio: Matriz

    @classmethod
    def de(cls, x: Matriz) -> _Padronizacao:
        desvio = x.std(axis=0)
        return cls(x.mean(axis=0), np.where(desvio > 0, desvio, 1.0))

    def aplicar(self, x: Matriz) -> Matriz:
        return (x - self.media) / self.desvio


def _ajustar(x: Matriz, y: Matriz, lam: float) -> tuple[_Padronizacao, float, Matriz]:
    escala = _Padronizacao.de(x)
    beta = ridge_fechado(escala.aplicar(x), y - y.mean(), lam)
    return escala, float(y.mean()), beta


@dataclass(frozen=True, slots=True)
class RegressaoRidge:
    grade: tuple[float, ...] = field(default=GRADE_PADRAO)
    dobras: int = 5
    semente: int = 0

    def ajustar(self, amostra: AmostraDeEsforco) -> ModeloRidge:
        x, y = np.asarray(amostra.matriz, dtype=float), np.asarray(amostra.y, dtype=float)
        if len(y) < 2 * self.dobras:
            raise ValorInvalido(f"Ridge com {len(y)} linhas para {self.dobras} partes")
        partes = np.random.default_rng(self.semente).permutation(len(y)) % self.dobras
        previsoes = {lam: self._fora_da_parte(x, y, partes, lam) for lam in self.grade}
        lam = min(self.grade, key=lambda v: float(np.mean((y - previsoes[v]) ** 2)))
        escala, intercepto, beta = _ajustar(x, y, lam)
        coeficientes = beta / escala.desvio
        intercepto_original = intercepto - float(escala.media @ coeficientes)
        return ModeloRidge(
            nomes=amostra.nomes,
            lam=lam,
            intercepto=intercepto_original,
            coeficientes=tuple(float(c) for c in coeficientes),
            graus_de_liberdade=graus_de_liberdade(escala.aplicar(x), lam),
            r2=_r2(y, intercepto_original + x @ coeficientes),
            r2_validacao=_r2(y, previsoes[lam]),
        )

    def _fora_da_parte(self, x: Matriz, y: Matriz, partes: NDArray[np.int64], lam: float) -> Matriz:
        previsto = np.empty_like(y)
        for k in range(self.dobras):
            teste = partes == k
            escala, intercepto, beta = _ajustar(x[~teste], y[~teste], lam)
            previsto[teste] = intercepto + escala.aplicar(x[teste]) @ beta
        return previsto
