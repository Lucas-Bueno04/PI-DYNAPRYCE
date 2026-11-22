"""Métricas em memória por rota: contagem e duração (F1.41). Zeram a cada reinício."""

import threading
from collections import defaultdict


class Metricas:
    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._contagem: dict[str, int] = defaultdict(int)
        self._duracao: dict[str, float] = defaultdict(float)

    def registrar(self, chave: str, duracao_s: float) -> None:
        with self._trava:
            self._contagem[chave] += 1
            self._duracao[chave] += duracao_s

    def instantaneo(self) -> dict[str, dict[str, float]]:
        with self._trava:
            return {
                chave: {"quantidade": total, "duracao_total_s": round(self._duracao[chave], 4)}
                for chave, total in self._contagem.items()
            }
