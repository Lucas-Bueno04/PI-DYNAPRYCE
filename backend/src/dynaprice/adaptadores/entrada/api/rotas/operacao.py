"""Rotas de operação: importação, vínculos, conectores, alertas, diagnóstico e laboratório."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Form, Query, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from dynaprice.adaptadores.entrada.api.seguranca import Dependencias, PrincipalAtual, exige
from dynaprice.aplicacao.autorizacao import Acao
from dynaprice.dominio.modelos import Competencia, Vinculo

roteador = APIRouter(tags=["operacao"])

CompetenciaTexto = Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")]


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CorpoVinculo(_Entrada):
    empresa_id: str = Field(max_length=64)
    contrato_id: str = Field(max_length=64)
    desde: str = Field(pattern=r"^\d{4}-\d{2}$")
    ate: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    principal: bool = False


class CorpoConector(_Entrada):
    credencial: dict[str, Any]
    parametros: dict[str, Any] = Field(default_factory=dict)
    dias_fechamento: int = Field(default=5, ge=0, le=28)


class CorpoSimulacao(_Entrada):
    documento: dict[str, Any]
    referencia: str = Field(pattern=r"^\d{4}-\d{2}$")


class RespostaImportacao(BaseModel):
    versao: int
    repetida: bool
    quarentena: int


class RespostaConector(BaseModel):
    tipo: str
    parametros: dict[str, Any]
    dias_fechamento: int
    credencial_configurada: bool


class RespostaTeste(BaseModel):
    situacao: str
    detalhe: str


class RespostaAlerta(BaseModel):
    tipo: str
    referencia: str
    criado_em: str


@roteador.post("/importacoes", status_code=201, **exige(Acao.IMPORTAR_DADOS))
def importar(
    arquivo: UploadFile,
    inicio: Annotated[str, Form(pattern=r"^\d{4}-\d{2}$")],
    fim: Annotated[str, Form(pattern=r"^\d{4}-\d{2}$")],
    deps: Dependencias,
    principal: PrincipalAtual,
) -> RespostaImportacao:
    resultado = deps.casos.importar.executar(
        principal,
        arquivo.filename or "",
        arquivo.file.read(),
        Competencia.de_texto(inicio),
        Competencia.de_texto(fim),
    )
    return RespostaImportacao(
        versao=resultado.versao, repetida=resultado.repetida, quarentena=resultado.quarentena
    )


@roteador.get("/vinculos/pendencias", **exige(Acao.VER_CARTEIRA))
def pendencias(
    competencia: CompetenciaTexto, deps: Dependencias, principal: PrincipalAtual
) -> list[str]:
    resultado: list[str] = deps.casos.listar_pendencias.executar(
        principal, Competencia.de_texto(competencia)
    )
    return resultado


@roteador.post("/vinculos", status_code=204, **exige(Acao.GERIR_VINCULOS))
def criar_vinculo(corpo: CorpoVinculo, deps: Dependencias, principal: PrincipalAtual) -> None:
    deps.casos.criar_vinculo.executar(
        principal,
        Vinculo(
            corpo.empresa_id,
            corpo.contrato_id,
            Competencia.de_texto(corpo.desde),
            None if corpo.ate is None else Competencia.de_texto(corpo.ate),
            corpo.principal,
        ),
    )


@roteador.get("/conectores", **exige(Acao.GERIR_CONECTORES))
def listar_conectores(deps: Dependencias, principal: PrincipalAtual) -> list[RespostaConector]:
    return [
        RespostaConector(
            tipo=c.tipo,
            parametros=dict(c.parametros),
            dias_fechamento=c.dias_fechamento,
            credencial_configurada=c.credencial_configurada,
        )
        for c in deps.casos.listar_conectores.executar(principal)
    ]


@roteador.put("/conectores/{tipo}", status_code=204, **exige(Acao.GERIR_CONECTORES))
def configurar_conector(
    tipo: str, corpo: CorpoConector, deps: Dependencias, principal: PrincipalAtual
) -> None:
    deps.casos.configurar_conector.executar(
        principal, tipo, corpo.credencial, corpo.parametros, corpo.dias_fechamento
    )


@roteador.post("/conectores/{tipo}/teste", **exige(Acao.GERIR_CONECTORES))
def testar_conector(tipo: str, deps: Dependencias, principal: PrincipalAtual) -> RespostaTeste:
    resultado = deps.casos.testar_conector.executar(principal, tipo)
    return RespostaTeste(situacao=resultado.situacao, detalhe=resultado.detalhe)


@roteador.get("/alertas", **exige(Acao.VER_CARTEIRA))
def alertas(deps: Dependencias, principal: PrincipalAtual) -> list[RespostaAlerta]:
    return [
        RespostaAlerta(tipo=a.tipo, referencia=a.referencia, criado_em=a.criado_em.isoformat())
        for a in deps.casos.listar_alertas.executar(principal)
    ]


@roteador.get("/metricas", **exige(Acao.GERIR_USUARIOS))
def metricas(request: Request) -> dict[str, dict[str, float]]:
    instantaneo: dict[str, dict[str, float]] = request.app.state.metricas.instantaneo()
    return instantaneo


@roteador.get("/diagnostico", **exige(Acao.VER_CARTEIRA))
def diagnostico(
    referencia: CompetenciaTexto, deps: Dependencias, principal: PrincipalAtual
) -> dict[str, Any]:
    relatorio = deps.casos.diagnostico.executar(principal, Competencia.de_texto(referencia))
    return {"titulo": relatorio.titulo, "secoes": [asdict(s) for s in relatorio.secoes]}


@roteador.post("/laboratorio/simulacoes", **exige(Acao.USAR_LABORATORIO))
def simular(corpo: CorpoSimulacao, deps: Dependencias, principal: PrincipalAtual) -> dict[str, Any]:
    resultado: dict[str, Any] = dict(
        deps.casos.simular.executar(
            principal, corpo.documento, Competencia.de_texto(corpo.referencia)
        )
    )
    return resultado
