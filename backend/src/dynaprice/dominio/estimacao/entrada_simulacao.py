"""Monta a entrada do simulador a partir da carteira: k_agr por contrato e séries de base mensal."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from dynaprice.dominio.estimacao.credibilidade import SerieDeBase
from dynaprice.dominio.estimacao.ocultacao import MESES_COMPLETOS, ContratoConhecido
from dynaprice.dominio.estimacao.simulador import ContratoSimulado
from dynaprice.dominio.modelos import (
    Carteira,
    Competencia,
    Direcionadores,
    Empresa,
    PoliticaVersao,
)
from dynaprice.dominio.precificacao import (
    AgregadoDoContrato,
    AgregadorDeContratos,
    EquacoesDeTempo,
    HorasPadrao,
    PisoDoRegime,
    PoliticaDePreco,
)


@dataclass(frozen=True, slots=True)
class EntradaDeSimulacao:
    contratos: tuple[ContratoSimulado, ...]
    series: tuple[SerieDeBase, ...]  # contratos completos, para s²/v²


def contratos_da_carteira(
    carteira: Carteira, politica: PoliticaVersao, competencia: Competencia
) -> EntradaDeSimulacao:
    equacoes = EquacoesDeTempo(politica)
    agregados = AgregadorDeContratos(equacoes).agregar(
        competencia, carteira.empresas, carteira.vinculos, carteira.direcionadores
    )
    por_id = {c.id: c for c in carteira.contratos}
    simulados = tuple(
        ContratoSimulado(
            a.contrato_id,
            a.regime,
            a.horas_padrao.total,
            a.meses,
            por_id[a.contrato_id].preco_vigente,
            por_id[a.contrato_id].kappa,
            por_id[a.contrato_id].provisorio,
        )
        for a in agregados.contratos
        if a.contrato_id in por_id
    )
    series = _series(carteira, agregados.contratos, equacoes, politica)
    return EntradaDeSimulacao(simulados, series)


def _series(
    carteira: Carteira,
    agregados: Sequence[AgregadoDoContrato],
    equacoes: EquacoesDeTempo,
    politica: PoliticaVersao,
) -> tuple[SerieDeBase, ...]:
    empresas = {e.id: e for e in carteira.empresas}
    por_empresa: dict[str, list[Direcionadores]] = defaultdict(list)
    for registro in carteira.direcionadores:
        por_empresa[registro.empresa_id].append(registro)
    preco, referencia = PoliticaDePreco(politica), PisoDoRegime(politica)
    series = []
    for agregado in agregados:
        if agregado.meses < 12:
            continue
        mensal = _horas_mensais([empresas[e] for e in agregado.empresas], por_empresa, equacoes)
        bases = tuple(preco.base(agregado.regime, h.total) for _, h in sorted(mensal.items()))
        series.append(SerieDeBase(agregado.regime, referencia.base(agregado.regime), bases))
    return tuple(series)


def _horas_mensais(
    empresas: Sequence[Empresa],
    por_empresa: dict[str, list[Direcionadores]],
    equacoes: EquacoesDeTempo,
) -> dict[Competencia, HorasPadrao]:
    mensal: dict[Competencia, HorasPadrao] = defaultdict(lambda: HorasPadrao({}))
    for empresa in empresas:
        for registro in por_empresa[empresa.id]:
            mensal[registro.competencia] += equacoes.horas_padrao(empresa, registro.valores)
    return dict(mensal)


def contratos_conhecidos(
    carteira: Carteira, agregados: Sequence[AgregadoDoContrato], equacoes: EquacoesDeTempo
) -> tuple[ContratoConhecido, ...]:
    """Contratos com 12 meses e suas horas-padrão dos 12 últimos meses (protocolo de ocultação)."""
    empresas = {e.id: e for e in carteira.empresas}
    por_empresa: dict[str, list[Direcionadores]] = defaultdict(list)
    for registro in carteira.direcionadores:
        por_empresa[registro.empresa_id].append(registro)
    conhecidos = []
    for agregado in agregados:
        if agregado.meses < MESES_COMPLETOS:
            continue
        membros = [empresas[e] for e in agregado.empresas]
        mensal = _horas_mensais(membros, por_empresa, equacoes)
        ultimos = [mensal[c].total for c in sorted(mensal)][-MESES_COMPLETOS:]
        departamentos = frozenset().union(*(e.departamentos for e in membros))
        conhecidos.append(
            ContratoConhecido(agregado.contrato_id, agregado.regime, departamentos, tuple(ultimos))
        )
    return tuple(conhecidos)
