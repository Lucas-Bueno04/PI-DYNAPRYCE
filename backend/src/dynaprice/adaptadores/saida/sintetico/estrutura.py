"""Estrutura da carteira: contratos, empresas e vínculos (ADR-003), com mistos e sem vínculo."""

import random
from collections.abc import Mapping
from dataclasses import dataclass

from dynaprice.adaptadores.saida.sintetico.parametros import (
    DIRECIONADORES_BASE,
    ParametrosSinteticos,
)
from dynaprice.dominio.modelos import Competencia, Departamento, Empresa, Regime, Vinculo


@dataclass(frozen=True, slots=True)
class EmpresaPlanejada:
    empresa: Empresa
    escala: float  # tamanho latente que multiplica os direcionadores
    fator_atipico: float  # desvio persistente das horas registradas (Huber, 9.8)
    inicio: Competencia  # primeiro mês com dados (histórico parcial, ADR-004)
    mix: Mapping[str, float]  # perfil da empresa: multiplicador por direcionador (média 1)


@dataclass(frozen=True, slots=True)
class ContratoPlanejado:
    id: str
    mes_reajuste: int
    provisorio: bool


@dataclass(frozen=True, slots=True)
class PlanoDaCarteira:
    contratos: tuple[ContratoPlanejado, ...]
    empresas: tuple[EmpresaPlanejada, ...]
    vinculos: tuple[Vinculo, ...]


class PlanejadorDeEstrutura:
    def __init__(self, parametros: ParametrosSinteticos, aleatorio: random.Random) -> None:
        self._p = parametros
        self._rnd = aleatorio
        self._empresas: list[EmpresaPlanejada] = []
        self._vinculos: list[Vinculo] = []

    def planejar(self, inicio: Competencia, fim: Competencia) -> PlanoDaCarteira:
        contratos = [self._contrato(i, inicio, fim) for i in range(1, self._p.contratos + 1)]
        vinculadas = len(self._empresas)
        orfas = round(self._p.fracao_sem_vinculo * vinculadas / (1 - self._p.fracao_sem_vinculo))
        for _ in range(orfas):
            regime = self._sortear_regime()
            self._nova_empresa(regime, inicio, self._extra(self._tamanho(regime)))
        return PlanoDaCarteira(tuple(contratos), tuple(self._empresas), tuple(self._vinculos))

    def _contrato(self, numero: int, inicio: Competencia, fim: Competencia) -> ContratoPlanejado:
        contrato_id = f"C{numero:04d}"
        parcial = self._rnd.random() < self._p.fracao_historico_parcial
        desde = fim.somar(-self._rnd.randint(0, 10)) if parcial else inicio
        regime = self._sortear_regime()
        tamanho = self._tamanho(regime)
        quantidade = self._sortear_quantidade()
        misto = quantidade > 1 and self._rnd.random() < self._chance_de_misto()
        for ordem in range(quantidade):
            regime_empresa = self._outro_regime(regime) if misto and ordem > 0 else regime
            perfil = self._extra(tamanho) if ordem > 0 else (tamanho, frozenset(Departamento))
            empresa = self._nova_empresa(regime_empresa, desde, perfil)
            vinculo = Vinculo(empresa.id, contrato_id, desde=desde, principal=ordem == 0)
            self._vinculos.append(vinculo)
        return ContratoPlanejado(contrato_id, self._rnd.randint(1, 12), parcial)

    def _tamanho(self, regime: Regime) -> float:
        escala = self._p.escala_por_regime[regime] * self._p.mediana_tamanho
        return escala * self._rnd.lognormvariate(0, self._p.sigma_tamanho)

    def _extra(self, tamanho: float) -> tuple[float, frozenset[Departamento]]:
        departamentos = [d for d, _ in self._p.departamento_extra]
        pesos = [peso for _, peso in self._p.departamento_extra]
        departamento = self._rnd.choices(departamentos, weights=pesos)[0]
        return tamanho * self._rnd.uniform(*self._p.tamanho_extra), frozenset({departamento})

    def _nova_empresa(
        self, regime: Regime, inicio: Competencia, perfil: tuple[float, frozenset[Departamento]]
    ) -> Empresa:
        escala, departamentos = perfil
        empresa = Empresa(f"E{len(self._empresas) + 1:05d}", regime, departamentos)
        planejada = EmpresaPlanejada(empresa, escala, self._fator_atipico(), inicio, self._mix())
        self._empresas.append(planejada)
        return empresa

    def _mix(self) -> dict[str, float]:
        """Empresas diferem na proporção entre direcionadores (identifica cada β, seção 5.8)."""
        sigma = self._p.sigma_mix
        return {n: self._rnd.lognormvariate(-(sigma**2) / 2, sigma) for n in DIRECIONADORES_BASE}

    def _fator_atipico(self) -> float:
        p, sorteio = self._p, self._rnd.random()
        altos, baixos = p.fracao_atipicos_altos, p.fracao_atipicos_baixos
        tipico = (1 - altos * 2.75 - baixos * 0.375) / (1 - altos - baixos)  # média 1
        if sorteio < altos:
            return self._rnd.uniform(2.0, 3.5)
        if sorteio < altos + baixos:
            return self._rnd.uniform(0.25, 0.5)
        return tipico

    def _chance_de_misto(self) -> float:
        multiplas = sum(peso for n, peso in self._p.empresas_por_contrato if n > 1)
        return self._p.fracao_mistos / multiplas

    def _sortear_regime(self) -> Regime:
        regimes = list(self._p.proporcao_regimes)
        return self._rnd.choices(regimes, weights=list(self._p.proporcao_regimes.values()))[0]

    def _outro_regime(self, regime: Regime) -> Regime:
        return self._rnd.choice([r for r in Regime if r is not regime])

    def _sortear_quantidade(self) -> int:
        quantidades = [n for n, _ in self._p.empresas_por_contrato]
        pesos = [peso for _, peso in self._p.empresas_por_contrato]
        return self._rnd.choices(quantidades, weights=pesos)[0]
