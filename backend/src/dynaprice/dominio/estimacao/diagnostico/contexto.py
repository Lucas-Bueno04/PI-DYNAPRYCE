"""Contexto da análise: equações estimadas, contratos agregados (k_agr) e modelo de esforço."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from dynaprice.dominio.estimacao.amostras import amostras_da_carteira
from dynaprice.dominio.estimacao.diagnostico.rascunho import documento_de_politica
from dynaprice.dominio.estimacao.esforco import AmostraDeEsforco, amostra_de_esforco
from dynaprice.dominio.estimacao.huber import EquacaoEstimada, EstimadorHuber
from dynaprice.dominio.estimacao.ridge import ModeloRidge, RegressaoRidge
from dynaprice.dominio.modelos import (
    Carteira,
    Competencia,
    Contrato,
    PoliticaVersao,
    Regime,
    fabricar_politica,
)
from dynaprice.dominio.precificacao import (
    AgregadoDoContrato,
    AgregadorDeContratos,
    EquacoesDeTempo,
    ResultadoDaAgregacao,
)


@dataclass(frozen=True, slots=True)
class ContratoAnalisado:
    agregado: AgregadoDoContrato
    contrato: Contrato
    horas_registradas: float  # média mensal somada nas empresas do contrato

    @property
    def honorario(self) -> float:
        return float(self.contrato.preco_vigente.valor)

    @property
    def completo(self) -> bool:
        return self.agregado.meses >= 12


@dataclass(frozen=True, slots=True)
class Contexto:
    carteira: Carteira
    referencia: Competencia
    equacoes: tuple[EquacaoEstimada, ...]
    politica_base: PoliticaVersao  # só as equações estimadas valem; pisos e τ são provisórios
    agregacao: ResultadoDaAgregacao
    contratos: tuple[ContratoAnalisado, ...]
    esforco: AmostraDeEsforco
    ridge: ModeloRidge


def _horas_por_empresa(carteira: Carteira) -> dict[str, float]:
    soma: dict[str, float] = defaultdict(float)
    meses: dict[str, set[Competencia]] = defaultdict(set)
    for h in carteira.horas:
        soma[h.empresa_id] += float(h.horas.valor)
        meses[h.empresa_id].add(h.competencia)
    return {e: soma[e] / len(meses[e]) for e in soma}


def montar_contexto(carteira: Carteira, referencia: Competencia, semente: int) -> Contexto:
    equacoes = tuple(EstimadorHuber().estimar(a) for a in amostras_da_carteira(carteira))
    provisorio = {r: Decimal(1) for r in Regime}
    documento = documento_de_politica(
        [e.equacao for e in equacoes], provisorio, Decimal(1), Decimal(1)
    )
    politica = fabricar_politica(documento)
    agregacao = AgregadorDeContratos(EquacoesDeTempo(politica)).agregar(
        referencia, carteira.empresas, carteira.vinculos, carteira.direcionadores
    )
    horas = _horas_por_empresa(carteira)
    por_id = {c.id: c for c in carteira.contratos}
    contratos = tuple(
        ContratoAnalisado(a, por_id[a.contrato_id], sum(horas.get(e, 0.0) for e in a.empresas))
        for a in agregacao.contratos
        if a.contrato_id in por_id
    )
    esforco = amostra_de_esforco(carteira)
    ridge = RegressaoRidge(semente=semente).ajustar(esforco)
    return Contexto(carteira, referencia, equacoes, politica, agregacao, contratos, esforco, ridge)
