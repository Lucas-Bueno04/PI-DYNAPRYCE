"""Rota de cotação de cliente novo (d_cot): regime obrigatório, decomposição na resposta."""

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from dynaprice.adaptadores.entrada.api.seguranca import Dependencias, PrincipalAtual, exige
from dynaprice.aplicacao.autorizacao import Acao
from dynaprice.aplicacao.casos_de_uso.cotar import PedidoDeCotacao
from dynaprice.dominio.modelos import Competencia, Regime

roteador = APIRouter(tags=["cotacoes"])


class CorpoCotacao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regime: Regime
    meses: int = Field(default=0, ge=0, le=600)
    horas_padrao: Decimal | None = Field(default=None, ge=0, le=100000)
    kappa: Decimal | None = None


class RespostaCotacao(BaseModel):
    id: UUID
    preco: str
    politica_versao: int
    provisorio: bool
    decomposicao: dict[str, Any]


class RespostaReproducao(BaseModel):
    gravado: str
    recalculado: str


@roteador.post("/cotacoes", status_code=201, **exige(Acao.COTAR_SERVICO))
def cotar(corpo: CorpoCotacao, deps: Dependencias, principal: PrincipalAtual) -> RespostaCotacao:
    cotacao = deps.casos.cotar.executar(
        principal, PedidoDeCotacao(corpo.regime, corpo.meses, corpo.horas_padrao, corpo.kappa)
    )
    return RespostaCotacao(
        id=cotacao.id,
        preco=str(cotacao.preco),
        politica_versao=cotacao.politica_versao,
        provisorio=cotacao.provisorio,
        decomposicao=dict(cotacao.decomposicao),
    )


@roteador.get("/cotacoes/{cotacao_id}/reproducao", **exige(Acao.COTAR_SERVICO))
def reproduzir(
    cotacao_id: UUID, deps: Dependencias, principal: PrincipalAtual
) -> RespostaReproducao:
    comparacao = deps.casos.reproduzir_cotacao.executar(principal, cotacao_id)
    return RespostaReproducao(
        gravado=str(comparacao.gravado), recalculado=str(comparacao.recalculado)
    )


class RespostaProvisorio(BaseModel):
    contrato_id: str
    preco_vigente: str
    esforco: str
    diferenca: str
    meses: int


@roteador.get("/relatorios/provisorios", **exige(Acao.VER_CARTEIRA))
def provisorios_abaixo_do_esforco(
    competencia: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
    deps: Dependencias,
    principal: PrincipalAtual,
) -> list[RespostaProvisorio]:
    itens = deps.casos.provisorios.executar(principal, Competencia.de_texto(competencia))
    return [
        RespostaProvisorio(
            contrato_id=i.contrato_id,
            preco_vigente=str(i.preco_vigente),
            esforco=str(i.esforco),
            diferenca=str(i.diferenca),
            meses=i.meses,
        )
        for i in itens
    ]
