"""Amostra do modelo multiplicativo de esforço (Eq. 41–42): ln H̄ por empresa contra ln(1 + x̄)."""

import math
from collections import defaultdict
from dataclasses import dataclass

from dynaprice.dominio.estimacao.amostras import ESPECIFICACAO_PADRAO, Especificacao
from dynaprice.dominio.modelos import Carteira, Departamento, Empresa, Regime

_REGIME_BASE = Regime.MEI  # indicadores z_i: SN, LP e LR contra o MEI


@dataclass(frozen=True, slots=True)
class AmostraDeEsforco:
    nomes: tuple[str, ...]
    matriz: tuple[tuple[float, ...], ...]  # uma linha por empresa
    y: tuple[float, ...]  # ln das horas registradas médias por mês


def _horas_medias(carteira: Carteira) -> dict[str, float]:
    por_mes: dict[tuple[str, object], float] = defaultdict(float)
    for h in carteira.horas:
        por_mes[(h.empresa_id, h.competencia)] += float(h.horas.valor)
    soma: dict[str, float] = defaultdict(float)
    meses: dict[str, int] = defaultdict(int)
    for (empresa_id, _), horas in por_mes.items():
        soma[empresa_id] += horas
        meses[empresa_id] += 1
    return {e: soma[e] / meses[e] for e in soma}


def _direcionadores_medios(carteira: Carteira, nomes: tuple[str, ...]) -> dict[str, list[float]]:
    soma: dict[str, list[float]] = {}
    meses: dict[str, int] = defaultdict(int)
    for d in carteira.direcionadores:
        linha = soma.setdefault(d.empresa_id, [0.0] * len(nomes))
        for i, nome in enumerate(nomes):
            linha[i] += float(d.valor(nome))
        meses[d.empresa_id] += 1
    return {e: [v / meses[e] for v in linha] for e, linha in soma.items()}


_REGIMES = tuple(r for r in Regime if r is not _REGIME_BASE)


def _linha(medias: list[float], empresa: Empresa) -> tuple[float, ...]:
    """ln(1 + x̄_j) e indicadores z_i: regime e departamentos atendidos (Eq. 41)."""
    logs = [math.log1p(v) for v in medias]
    regimes = [float(empresa.regime is r) for r in _REGIMES]
    return tuple(logs + regimes + [float(empresa.atende(d)) for d in Departamento])


def _nomes(direcionadores: tuple[str, ...]) -> tuple[str, ...]:
    logs = tuple(f"ln1p_{n}" for n in direcionadores)
    return (
        logs + tuple(f"regime_{r}" for r in _REGIMES) + tuple(f"atende_{d}" for d in Departamento)
    )


def amostra_de_esforco(
    carteira: Carteira, especificacao: Especificacao = ESPECIFICACAO_PADRAO
) -> AmostraDeEsforco:
    direcionadores = tuple(n for nomes in especificacao.values() for n in nomes)
    horas = _horas_medias(carteira)
    medias = _direcionadores_medios(carteira, direcionadores)
    validas = [e for e in carteira.empresas if horas.get(e.id, 0.0) > 0 and e.id in medias]
    linhas = tuple(_linha(medias[e.id], e) for e in validas)
    y = tuple(math.log(horas[e.id]) for e in validas)
    return AmostraDeEsforco(_nomes(direcionadores), linhas, y)
