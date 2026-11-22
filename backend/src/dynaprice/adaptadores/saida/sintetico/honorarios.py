"""Honorários pela regra implícita regressiva F = a + b·H (seção 9.4), com ruído multiplicativo."""

import math
import random
from collections.abc import Iterable

from dynaprice.adaptadores.saida.sintetico.estrutura import PlanoDaCarteira
from dynaprice.adaptadores.saida.sintetico.parametros import ParametrosSinteticos
from dynaprice.dominio.modelos import Competencia, Dinheiro, Honorario


def _meses(inicio: Competencia, fim: Competencia) -> Iterable[Competencia]:
    return (inicio.somar(i) for i in range(inicio.meses_ate(fim) + 1))


class GeradorDeHonorarios:
    def __init__(self, parametros: ParametrosSinteticos, aleatorio: random.Random) -> None:
        self._p = parametros
        self._rnd = aleatorio

    def gerar(
        self,
        plano: PlanoDaCarteira,
        horas_medias: dict[str, float],
        inicio: Competencia,
        fim: Competencia,
    ) -> tuple[Honorario, ...]:
        horas_contrato: dict[str, float] = {}
        desde: dict[str, Competencia] = {}
        for v in plano.vinculos:
            horas_contrato[v.contrato_id] = (
                horas_contrato.get(v.contrato_id, 0.0) + horas_medias[v.empresa_id]
            )
            desde[v.contrato_id] = max(inicio, v.desde)
        honorarios: list[Honorario] = []
        for contrato in plano.contratos:
            valor = self._valor(horas_contrato[contrato.id])
            honorarios.extend(
                Honorario(contrato.id, c, valor) for c in _meses(desde[contrato.id], fim)
            )
        return tuple(honorarios)

    def _valor(self, horas: float) -> Dinheiro:
        sigma = self._p.sigma_preco
        ruido = math.exp(self._rnd.gauss(-(sigma**2) / 2, sigma))
        valor = (self._p.regra_implicita_a + self._p.regra_implicita_b * horas) * ruido
        return Dinheiro.de(f"{valor:.4f}")
