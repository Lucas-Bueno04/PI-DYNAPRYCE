"""Direcionadores mensais e horas registradas (eq. 2: ln H = ln H* + w) de cada empresa."""

import math
import random
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

from dynaprice.adaptadores.saida.sintetico.estrutura import EmpresaPlanejada
from dynaprice.adaptadores.saida.sintetico.parametros import (
    DIRECIONADORES_BASE,
    EQUACOES_VERDADEIRAS,
    SAZONALIDADE,
    ParametrosSinteticos,
)
from dynaprice.dominio.modelos import (
    Competencia,
    Direcionadores,
    EquacaoDeTempo,
    Horas,
    HorasRegistradas,
)

_QUATRO_CASAS = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class EsforcoGerado:
    direcionadores: tuple[Direcionadores, ...]
    horas: tuple[HorasRegistradas, ...]
    horas_medias: dict[str, float]  # média mensal de horas registradas por empresa


def _meses(inicio: Competencia, fim: Competencia) -> Iterator[Competencia]:
    atual = inicio
    while atual <= fim:
        yield atual
        atual = atual.proxima()


def _minutos(equacao: EquacaoDeTempo, valores: dict[str, Decimal]) -> float:
    return sum(
        float(b * valores.get(k, Decimal(0))) for k, b in equacao.inclinacoes_minutos.items()
    )


def _direcionadores_atendidos(planejada: EmpresaPlanejada) -> frozenset[str]:
    """Só existem dados dos serviços prestados: sem folha, não há empregados no sistema."""
    return frozenset(
        nome
        for eq in EQUACOES_VERDADEIRAS
        if planejada.empresa.atende(eq.departamento)
        for nome in eq.inclinacoes_minutos
    )


class GeradorDeEsforco:
    def __init__(self, parametros: ParametrosSinteticos, aleatorio: random.Random) -> None:
        self._p = parametros
        self._rnd = aleatorio

    def gerar(
        self, empresas: tuple[EmpresaPlanejada, ...], inicio: Competencia, fim: Competencia
    ) -> EsforcoGerado:
        direcionadores: list[Direcionadores] = []
        horas: list[HorasRegistradas] = []
        medias: dict[str, float] = {}
        for planejada in empresas:
            meses = list(_meses(max(inicio, planejada.inicio), fim))
            total = 0.0
            for competencia in meses:
                mes = self._mes(planejada, competencia)
                direcionadores.append(mes[0])
                horas.extend(mes[1])
                total += sum(float(h.horas.valor) for h in mes[1])
            medias[planejada.empresa.id] = total / len(meses)
        return EsforcoGerado(tuple(direcionadores), tuple(horas), medias)

    def _mes(
        self, planejada: EmpresaPlanejada, competencia: Competencia
    ) -> tuple[Direcionadores, list[HorasRegistradas]]:
        valores = self._direcionadores(planejada, competencia)
        empresa_id = planejada.empresa.id
        registros = [
            HorasRegistradas(
                empresa_id,
                competencia,
                eq.departamento,
                self._horas(eq, valores, planejada.fator_atipico),
            )
            for eq in EQUACOES_VERDADEIRAS
            if planejada.empresa.atende(eq.departamento)
        ]
        return Direcionadores(empresa_id, competencia, valores), registros

    def _direcionadores(
        self, planejada: EmpresaPlanejada, competencia: Competencia
    ) -> dict[str, Decimal]:
        escala = planejada.escala * SAZONALIDADE[competencia.mes - 1]
        atendidos = _direcionadores_atendidos(planejada)
        return {
            nome: Decimal(round(media * escala * planejada.mix[nome] * self._ruido()))
            if nome in atendidos
            else Decimal(0)
            for nome, media in DIRECIONADORES_BASE.items()
        }

    def _ruido(self) -> float:
        return self._rnd.lognormvariate(0, 0.2)

    def _horas(self, equacao: EquacaoDeTempo, valores: dict[str, Decimal], fator: float) -> Horas:
        padrao = float(equacao.beta0_horas) + _minutos(equacao, valores) / 60
        sigma = self._p.sigma_medida
        erro = math.exp(self._rnd.gauss(-(sigma**2) / 2, sigma))  # média 1
        registradas = padrao / self._p.rho * fator * erro
        return Horas(Decimal(repr(registradas)).quantize(_QUATRO_CASAS))
