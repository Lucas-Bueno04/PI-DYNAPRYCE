"""Calibração do rascunho de política: pisos (D2), τ̂ e τ* (D3, Prop. 7) e s²/v² (Eq. 56)."""

import json
from dataclasses import dataclass
from decimal import Decimal

from dynaprice.dominio.estimacao.credibilidade import estimar_razao_s2_v2
from dynaprice.dominio.estimacao.diagnostico.contexto import Contexto
from dynaprice.dominio.estimacao.diagnostico.medidas import percentil
from dynaprice.dominio.estimacao.diagnostico.rascunho import documento_de_politica
from dynaprice.dominio.estimacao.entrada_simulacao import contratos_da_carteira
from dynaprice.dominio.modelos import (
    Dinheiro,
    PoliticaVersao,
    Regime,
    ValorInvalido,
    fabricar_politica,
)
from dynaprice.dominio.precificacao import (
    ObservacaoDeTarifa,
    TarifaPorPrecoRevelado,
    TarifaPorReceitaAlvo,
)

PERCENTIL_DO_PISO = 0.10  # D2 (a): percentil baixo do preço praticado por regime


@dataclass(frozen=True, slots=True)
class Calibracao:
    pisos: dict[Regime, Decimal]
    pisos_sem_dados: frozenset[Regime]
    tau_chapeu: Decimal
    tau_estrela: Decimal | None  # None quando Σκπ ≥ R0 (Prop. 4 não vale)
    razao_s2_v2: Decimal
    politica: PoliticaVersao
    documento: str


def _honorarios(contexto: Contexto, regime: Regime | None) -> list[float]:
    return [
        c.honorario
        for c in contexto.contratos
        if c.completo and (regime is None or c.agregado.regime is regime)
    ]


def _pisos(contexto: Contexto) -> tuple[dict[Regime, Decimal], frozenset[Regime]]:
    """P10 do honorário por regime; regime sem contratos usa o P10 da carteira toda."""
    todos = _honorarios(contexto, None)
    por_regime = {r: _honorarios(contexto, r) for r in Regime}
    pisos = {
        r: Dinheiro.de(f"{percentil(v or todos, PERCENTIL_DO_PISO):.4f}").valor
        for r, v in por_regime.items()
    }
    return pisos, frozenset(r for r, v in por_regime.items() if not v)


def observacoes(contexto: Contexto) -> list[ObservacaoDeTarifa]:
    return [
        ObservacaoDeTarifa(
            c.agregado.regime,
            c.agregado.horas_padrao.total,
            c.contrato.preco_vigente,
            c.contrato.kappa,
        )
        for c in contexto.contratos
        if c.completo and c.agregado.horas_padrao.total.valor > 0
    ]


def calibrar(contexto: Contexto) -> Calibracao:
    pisos, sem = _pisos(contexto)
    dinheiro = {r: Dinheiro(v) for r, v in pisos.items()}
    obs = observacoes(contexto)
    tau = TarifaPorPrecoRevelado().estimar(obs, dinheiro).valor
    try:
        estrela: Decimal | None = (
            TarifaPorReceitaAlvo.receita_constante(obs).estimar(obs, dinheiro).valor
        )
    except ValorInvalido:
        estrela = None
    equacoes = [e.equacao for e in contexto.equacoes]
    preliminar = fabricar_politica(documento_de_politica(equacoes, pisos, tau, Decimal(1)))
    series = contratos_da_carteira(contexto.carteira, preliminar, contexto.referencia).series
    razao = Decimal(repr(estimar_razao_s2_v2(series))).quantize(Decimal("0.0001"))
    documento = documento_de_politica(equacoes, pisos, tau.quantize(Decimal("0.0001")), razao)
    texto = json.dumps(documento, ensure_ascii=False, indent=2)
    return Calibracao(pisos, sem, tau, estrela, razao, fabricar_politica(documento), texto)
