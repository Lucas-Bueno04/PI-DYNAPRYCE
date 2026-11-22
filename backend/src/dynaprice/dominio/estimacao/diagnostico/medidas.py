"""Medidas descritivas do diagnóstico: regra afim (Eq. 12, seção 5.4), Gini (5.5), I_i (5.6)."""

from collections.abc import Sequence

import numpy as np


def gini(valores: Sequence[float]) -> float:
    """G = Σ_i (2i − n − 1)·x_(i) / (n·Σx), com x ordenado crescente."""
    x = np.sort(np.asarray(valores, dtype=float))
    if x.size == 0 or np.any(x < 0) or x.sum() == 0:
        raise ValueError("Gini exige valores não negativos com soma positiva")
    i = np.arange(1, x.size + 1)
    return float(np.sum((2 * i - x.size - 1) * x) / (x.size * x.sum()))


def regra_afim(horas: Sequence[float], precos: Sequence[float]) -> tuple[float, float, float]:
    """F = a + b·H por mínimos quadrados: (a, b, R²)."""
    h, f = np.asarray(horas, dtype=float), np.asarray(precos, dtype=float)
    b, a = np.polyfit(h, f, 1)
    residuo = f - (a + b * h)
    return float(a), float(b), float(1 - residuo @ residuo / np.sum((f - f.mean()) ** 2))


def indices_de_alinhamento(precos: Sequence[float], horas: Sequence[float]) -> list[float]:
    """I_i = (F_i/ΣF)/(H_i/ΣH): participação na receita sobre participação no esforço."""
    f, h = np.asarray(precos, dtype=float), np.asarray(horas, dtype=float)
    return [float(v) for v in (f / f.sum()) / (h / h.sum())]


def percentil(valores: Sequence[float], q: float) -> float:
    return float(np.quantile(np.asarray(valores, dtype=float), q))
