"""Estimação anual e portão de aceite das equações de tempo (D-PORTAO-EQ, F1.30).

O erro é medido em horas, fora da amostra: 20% das empresas ficam de fora do ajuste, com semente
fixa. O R² do Ridge saiu do caminho do preço (E2), por isso não serve de critério.
"""

import hashlib
import json
from dataclasses import fields, replace
from decimal import Decimal
from typing import Any

from dynaprice.dominio.estimacao.amostras import AmostraDeDepartamento, amostras_da_carteira
from dynaprice.dominio.estimacao.diagnostico.calibracao import calibrar
from dynaprice.dominio.estimacao.diagnostico.contexto import montar_contexto
from dynaprice.dominio.estimacao.entrada_simulacao import contratos_da_carteira
from dynaprice.dominio.estimacao.huber import EstimadorHuber
from dynaprice.dominio.estimacao.simulador import SimuladorDePolitica
from dynaprice.dominio.modelos import (
    Carteira,
    Competencia,
    Departamento,
    EquacaoDeTempo,
    EstimativaDePolitica,
    PoliticaVersao,
)
from dynaprice.dominio.precificacao import NucleoDePreco

TOLERANCIA = Decimal("1.05")
_CASAS = Decimal("0.0001")
_MINUTOS_POR_HORA = 60.0


def portao_de_aceite(
    eam_novo: Decimal, eam_vigente: Decimal | None, *, betas_validos: bool
) -> bool:
    if eam_vigente is None:
        return betas_validos
    return eam_novo <= eam_vigente * TOLERANCIA


def _prever(equacao: EquacaoDeTempo, nomes: tuple[str, ...], linha: tuple[float, ...]) -> float:
    minutos = sum(
        float(equacao.inclinacoes_minutos.get(nome, Decimal(0))) * valor
        for nome, valor in zip(nomes, linha, strict=True)
    )
    return float(equacao.beta0_horas) + minutos / _MINUTOS_POR_HORA


def _eam(
    amostras: list[AmostraDeDepartamento], equacoes: dict[Departamento, EquacaoDeTempo]
) -> Decimal:
    erros = [
        abs(_prever(equacoes[a.departamento], a.direcionadores, linha) - horas)
        for a in amostras
        if a.departamento in equacoes
        for linha, horas in zip(a.matriz, a.horas, strict=True)
    ]
    return Decimal(repr(sum(erros) / len(erros))).quantize(_CASAS)


def _gerais(politica: PoliticaVersao) -> dict[Departamento, EquacaoDeTempo]:
    gerais = {e.departamento: e for e in politica.equacoes if e.regime is None}
    return {**{e.departamento: e for e in politica.equacoes}, **gerais}


class EstimadorAnual:
    def __init__(self, semente: int = 0, fracao_de_ajuste: float = 0.8) -> None:
        self._semente = semente
        self._fracao = fracao_de_ajuste

    def _no_ajuste(self, empresa_id: str) -> bool:
        resumo = hashlib.sha256(f"{self._semente}:{empresa_id}".encode()).digest()
        return resumo[0] / 256 < self._fracao

    def _partes(self, carteira: Carteira) -> tuple[Carteira, Carteira]:
        ajuste = [h for h in carteira.horas if self._no_ajuste(h.empresa_id)]
        teste = [h for h in carteira.horas if not self._no_ajuste(h.empresa_id)]
        return replace(carteira, horas=tuple(ajuste)), replace(carteira, horas=tuple(teste))

    def estimar(
        self, carteira: Carteira, referencia: Competencia, vigente: PoliticaVersao | None
    ) -> EstimativaDePolitica:
        ajuste, teste = self._partes(carteira)
        amostras_de_ajuste = amostras_da_carteira(ajuste)
        novas = {a.departamento: EstimadorHuber().estimar(a).equacao for a in amostras_de_ajuste}
        amostras = amostras_da_carteira(teste)
        eam_novo = _eam(amostras, novas)
        eam_vigente = None if vigente is None else _eam(amostras, _gerais(vigente))
        validos = all(e.beta0_horas >= 0 for e in novas.values())
        aceito = portao_de_aceite(eam_novo, eam_vigente, betas_validos=validos)
        documento: dict[str, Any] = json.loads(
            calibrar(montar_contexto(carteira, referencia, self._semente)).documento
        )
        return EstimativaDePolitica(documento, aceito, _relatorio(eam_novo, eam_vigente, aceito))


def _relatorio(eam_novo: Decimal, eam_vigente: Decimal | None, aceito: bool) -> dict[str, Any]:
    return {
        "eam_novo": str(eam_novo),
        "eam_vigente": None if eam_vigente is None else str(eam_vigente),
        "portao": "aprovado" if aceito else "reprovado",
    }


class SimuladorDaCarteira:
    """Simula um rascunho de política sobre a carteira (m_sim), sem segunda fórmula."""

    def simular(
        self, carteira: Carteira, politica: PoliticaVersao, referencia: Competencia
    ) -> dict[str, Any]:
        entrada = contratos_da_carteira(carteira, politica, referencia)
        resultado = SimuladorDePolitica(NucleoDePreco.da_politica(politica)).simular(
            entrada.contratos
        )
        return {
            campo.name: str(valor) if isinstance(valor, Decimal) else valor
            for campo in fields(resultado)
            for valor in [getattr(resultado, campo.name)]
        }
