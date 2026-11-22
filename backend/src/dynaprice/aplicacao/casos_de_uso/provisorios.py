"""Relatório mensal "provisórios abaixo do esforço medido" (ADR-004, mitigação do risco).

O contrato provisório paga um preço misturado ao piso do regime; quando o esforço já medido
(κ·max(π_r, τ·H_pad)) é maior que o preço vigente, a diferença é receita que o escritório
deixa de cobrar até a revisão integral em ℓ = 2.
"""

from dataclasses import dataclass
from decimal import Decimal

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.portas import FabricaDeUnidades, PrecoAlvoRegistrado, UnidadeDeTrabalho
from dynaprice.dominio.modelos import (
    Competencia,
    Dinheiro,
    Horas,
    Kappa,
    Regime,
    fabricar_politica,
)
from dynaprice.dominio.modelos.autenticacao import Principal
from dynaprice.dominio.precificacao import PoliticaDePreco


@dataclass(frozen=True, slots=True)
class ProvisorioAbaixoDoEsforco:
    contrato_id: str
    preco_vigente: Dinheiro
    esforco: Dinheiro
    diferenca: Decimal
    meses: int


class ProvisoriosAbaixoDoEsforco:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(
        self, principal: Principal, competencia: Competencia
    ) -> tuple[ProvisorioAbaixoDoEsforco, ...]:
        autorizar(principal, Acao.VER_CARTEIRA)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            itens = self._itens(uow, competencia)
        return tuple(sorted(itens, key=lambda i: i.diferenca, reverse=True))

    def _itens(
        self, uow: UnidadeDeTrabalho, competencia: Competencia
    ) -> list[ProvisorioAbaixoDoEsforco]:
        provisorios = {c.id: c for c in uow.contratos.listar() if c.provisorio}
        politicas: dict[int, PoliticaDePreco] = {}
        itens: list[ProvisorioAbaixoDoEsforco] = []
        for alvo in uow.precos_alvo.da_competencia(competencia):
            contrato = provisorios.get(alvo.contrato_id)
            if contrato is None or alvo.horas_padrao is None:
                continue
            esforco = _esforco(uow, politicas, alvo, alvo.horas_padrao)
            if esforco.valor > contrato.preco_vigente.valor:
                itens.append(
                    ProvisorioAbaixoDoEsforco(
                        contrato.id,
                        contrato.preco_vigente,
                        esforco,
                        esforco.valor - contrato.preco_vigente.valor,
                        int(alvo.entradas["meses"]),
                    )
                )
        return itens


def _esforco(
    uow: UnidadeDeTrabalho,
    politicas: dict[int, PoliticaDePreco],
    alvo: PrecoAlvoRegistrado,
    horas: Decimal,
) -> Dinheiro:
    """Usa a versão da política com que o preço-alvo foi gravado."""
    if alvo.politica_versao not in politicas:
        registro = uow.politicas.obter(alvo.politica_versao)
        assert registro is not None  # a chave estrangeira garante a versão
        politicas[alvo.politica_versao] = PoliticaDePreco(fabricar_politica(registro.documento))
    kappa = Kappa(Decimal(alvo.entradas["kappa"]))
    resultado = politicas[alvo.politica_versao].preco_alvo(
        Regime(alvo.entradas["regime"]), Horas(horas), kappa
    )
    return resultado.valor
