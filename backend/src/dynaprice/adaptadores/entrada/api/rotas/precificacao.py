"""Rotas do ciclo de preço: recomendações, exportação, políticas e divergências."""

from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from dynaprice.adaptadores.entrada.api.seguranca import Dependencias, PrincipalAtual, exige
from dynaprice.aplicacao.autorizacao import Acao
from dynaprice.aplicacao.casos_de_uso.consultas import RecomendacaoDetalhada
from dynaprice.aplicacao.casos_de_uso.decidir import AjustarKappa, Aprovar, Decisao, Rejeitar
from dynaprice.dominio.modelos import ValorInvalido
from dynaprice.dominio.modelos.recomendacao import EstadoRecomendacao

roteador = APIRouter(tags=["precificacao"])


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CorpoDecisao(_Entrada):
    versao: int
    acao: Literal["aprovar", "ajustar", "rejeitar"]
    kappa: Decimal | None = None
    justificativa: str = Field(default="", max_length=2000)
    motivo: str = Field(default="", max_length=2000)


class CorpoDocumento(_Entrada):
    documento: dict[str, Any]


class CorpoJustificativa(_Entrada):
    texto: str = Field(max_length=2000)


class RespostaRecomendacao(BaseModel):
    id: UUID
    contrato_id: str
    competencia: str
    efeito: str
    estado: EstadoRecomendacao
    versao: int
    preco_vigente: str
    preco_proposto: str
    trajetoria: list[str]
    decomposicao: dict[str, Any]


class RespostaLote(BaseModel):
    lote_id: UUID | None


class RespostaPolitica(BaseModel):
    versao: int
    estado: str
    documento: dict[str, Any]
    portao_aceite: bool | None
    relatorio: dict[str, Any] | None


class RespostaVersao(BaseModel):
    versao: int


class RespostaDivergencia(BaseModel):
    id: UUID
    contrato_id: str
    competencia: str
    aprovado: str
    cobrado: str
    situacao: str
    justificativa: str


def _recomendacao(item: RecomendacaoDetalhada) -> RespostaRecomendacao:
    r = item.recomendacao
    return RespostaRecomendacao(
        id=r.id,
        contrato_id=r.contrato_id,
        competencia=str(r.competencia),
        efeito=str(r.efeito),
        estado=r.estado,
        versao=r.versao,
        preco_vigente=str(r.preco_vigente),
        preco_proposto=str(r.preco_proposto),
        trajetoria=[str(p) for p in r.trajetoria],
        decomposicao=dict(item.decomposicao),
    )


def _decisao(corpo: CorpoDecisao) -> Decisao:
    if corpo.acao == "aprovar":
        return Aprovar()
    if corpo.acao == "rejeitar":
        return Rejeitar(corpo.motivo)
    if corpo.kappa is None:
        raise ValorInvalido("o ajuste exige o valor de κ")
    return AjustarKappa(corpo.kappa, corpo.justificativa)


@roteador.get("/recomendacoes", **exige(Acao.VER_CARTEIRA))
def listar_recomendacoes(
    deps: Dependencias,
    principal: PrincipalAtual,
    estado: Annotated[EstadoRecomendacao | None, Query()] = None,
) -> list[RespostaRecomendacao]:
    return [_recomendacao(i) for i in deps.casos.listar_recomendacoes.executar(principal, estado)]


@roteador.post(
    "/recomendacoes/{recomendacao_id}/decisao",
    status_code=204,
    **exige(Acao.DECIDIR_RECOMENDACAO),
)
def decidir(
    recomendacao_id: UUID, corpo: CorpoDecisao, deps: Dependencias, principal: PrincipalAtual
) -> None:
    deps.casos.decidir.executar(principal, recomendacao_id, corpo.versao, _decisao(corpo))


@roteador.post("/exportacoes", status_code=201, **exige(Acao.EXPORTAR_RECOMENDACOES))
def solicitar_exportacao(deps: Dependencias, principal: PrincipalAtual) -> RespostaLote:
    return RespostaLote(lote_id=deps.casos.solicitar_exportacao.executar(principal))


@roteador.post(
    "/exportacoes/{lote}/nova-tentativa", status_code=204, **exige(Acao.EXPORTAR_RECOMENDACOES)
)
def nova_tentativa(lote: UUID, deps: Dependencias, principal: PrincipalAtual) -> None:
    deps.casos.tentar_exportar.executar(principal, lote)


@roteador.get("/exportacoes/{lote}/arquivo", **exige(Acao.EXPORTAR_RECOMENDACOES))
def baixar(lote: UUID, deps: Dependencias, principal: PrincipalAtual) -> Response:
    return Response(deps.casos.baixar_lote.executar(principal, lote), media_type="text/csv")


@roteador.get("/politicas", **exige(Acao.VER_CARTEIRA))
def listar_politicas(deps: Dependencias, principal: PrincipalAtual) -> list[RespostaPolitica]:
    return [
        RespostaPolitica(
            versao=r.versao,
            estado=r.estado,
            documento=dict(r.documento),
            portao_aceite=r.portao_aceite,
            relatorio=None if r.relatorio is None else dict(r.relatorio),
        )
        for r in deps.casos.listar_politicas.executar(principal)
    ]


@roteador.post("/politicas", status_code=201, **exige(Acao.USAR_LABORATORIO))
def criar_rascunho(
    corpo: CorpoDocumento, deps: Dependencias, principal: PrincipalAtual
) -> RespostaVersao:
    return RespostaVersao(versao=deps.casos.criar_rascunho.executar(principal, corpo.documento))


@roteador.post("/politicas/{versao}/publicar", status_code=204, **exige(Acao.PUBLICAR_POLITICA))
def publicar(versao: int, deps: Dependencias, principal: PrincipalAtual) -> None:
    deps.casos.publicar.executar(principal, versao)


@roteador.get("/divergencias", **exige(Acao.VER_CARTEIRA))
def listar_divergencias(deps: Dependencias, principal: PrincipalAtual) -> list[RespostaDivergencia]:
    return [
        RespostaDivergencia(
            id=d.id,
            contrato_id=d.contrato_id,
            competencia=str(d.competencia),
            aprovado=str(d.aprovado),
            cobrado=str(d.cobrado),
            situacao=d.situacao.value,
            justificativa=d.justificativa,
        )
        for d in deps.casos.listar_divergencias.executar(principal)
    ]


@roteador.post(
    "/divergencias/{divergencia_id}/justificativa",
    status_code=204,
    **exige(Acao.TRATAR_DIVERGENCIA),
)
def justificar(
    divergencia_id: UUID, corpo: CorpoJustificativa, deps: Dependencias, principal: PrincipalAtual
) -> None:
    deps.casos.tratar_divergencia.justificar(principal, divergencia_id, corpo.texto)


@roteador.post(
    "/divergencias/{divergencia_id}/resolucao", status_code=204, **exige(Acao.TRATAR_DIVERGENCIA)
)
def resolver(divergencia_id: UUID, deps: Dependencias, principal: PrincipalAtual) -> None:
    deps.casos.tratar_divergencia.resolver(principal, divergencia_id)
