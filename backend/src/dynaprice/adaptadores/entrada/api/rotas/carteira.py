"""Rotas de leitura da carteira: painel de indicadores e lista de clientes."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from dynaprice.adaptadores.entrada.api.seguranca import Dependencias, PrincipalAtual, exige
from dynaprice.aplicacao.autorizacao import Acao
from dynaprice.aplicacao.casos_de_uso.carteira import LinhaDeCliente
from dynaprice.dominio.modelos import Competencia

roteador = APIRouter(tags=["carteira"])
CompetenciaTexto = Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")]


class RespostaCliente(BaseModel):
    contrato_id: str
    regime: str | None
    empresas: int
    preco_vigente: str
    preco_alvo: str | None
    defasagem_pct: str | None
    cobrado: str | None
    mes_reajuste: int | None
    provisorio: bool
    kappa: str
    recomendacao: str | None


class RespostaRegime(BaseModel):
    regime: str
    empresas: int
    contratos: int
    receita: str


class RespostaPonto(BaseModel):
    competencia: str
    valor: str


class RespostaFaixa(BaseModel):
    rotulo: str
    contratos: int


class RespostaPainel(BaseModel):
    competencia: str
    empresas: int
    contratos: int
    provisorios: int
    receita_mensal: str
    receita_alvo: str
    potencial_de_reajuste: str
    alertas: int
    competencias_com_dados: list[str]
    por_regime: list[RespostaRegime]
    serie_receita: list[RespostaPonto]
    faixas: list[RespostaFaixa]
    recomendacoes: dict[str, int]
    divergencias: dict[str, int]
    maiores_defasagens: list[RespostaCliente]


def _texto(valor: Decimal | None) -> str | None:
    return None if valor is None else str(valor)


def _cliente(linha: LinhaDeCliente) -> RespostaCliente:
    return RespostaCliente(
        contrato_id=linha.contrato_id,
        regime=linha.regime,
        empresas=linha.empresas,
        preco_vigente=str(linha.preco_vigente),
        preco_alvo=_texto(linha.preco_alvo),
        defasagem_pct=_texto(linha.defasagem_pct),
        cobrado=_texto(linha.cobrado),
        mes_reajuste=linha.mes_reajuste,
        provisorio=linha.provisorio,
        kappa=str(linha.kappa),
        recomendacao=linha.recomendacao,
    )


@roteador.get("/clientes", **exige(Acao.VER_CARTEIRA))
def listar_clientes(
    competencia: CompetenciaTexto, deps: Dependencias, principal: PrincipalAtual
) -> list[RespostaCliente]:
    linhas = deps.casos.listar_clientes.executar(principal, Competencia.de_texto(competencia))
    return [_cliente(linha) for linha in linhas]


@roteador.get("/painel", **exige(Acao.VER_CARTEIRA))
def painel(
    competencia: CompetenciaTexto, deps: Dependencias, principal: PrincipalAtual
) -> RespostaPainel:
    p = deps.casos.painel.executar(principal, Competencia.de_texto(competencia))
    return RespostaPainel(
        competencia=p.competencia,
        empresas=p.empresas,
        contratos=p.contratos,
        provisorios=p.provisorios,
        receita_mensal=str(p.receita_mensal),
        receita_alvo=str(p.receita_alvo),
        potencial_de_reajuste=str(p.potencial_de_reajuste),
        alertas=p.alertas,
        competencias_com_dados=list(p.competencias_com_dados),
        por_regime=[
            RespostaRegime(
                regime=f.regime, empresas=f.empresas, contratos=f.contratos, receita=str(f.receita)
            )
            for f in p.por_regime
        ],
        serie_receita=[
            RespostaPonto(competencia=s.competencia, valor=str(s.valor)) for s in p.serie_receita
        ],
        faixas=[RespostaFaixa(rotulo=f.rotulo, contratos=f.contratos) for f in p.faixas],
        recomendacoes=dict(p.recomendacoes),
        divergencias=dict(p.divergencias),
        maiores_defasagens=[_cliente(linha) for linha in p.maiores_defasagens],
    )
