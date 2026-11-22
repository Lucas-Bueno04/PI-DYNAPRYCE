"""Importação de carteira (uc_import): raw versionado, quarentena e fatos normalizados."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.portas import (
    FabricaDeUnidades,
    LeitorDeArquivo,
    Rejeitada,
    Relogio,
    UnidadeDeTrabalho,
)
from dynaprice.dominio.modelos import Carteira, Competencia, Empresa
from dynaprice.dominio.modelos.autenticacao import Principal

FONTE_PLANILHA = "planilha"


@dataclass(frozen=True, slots=True)
class ResultadoDaImportacao:
    versao: int
    repetida: bool
    quarentena: int


def carteira_em_json(carteira: Carteira) -> dict[str, Any]:
    """Só o que já foi minimizado: documentos chegam aqui pseudonimizados."""
    return {
        "empresas": sorted(e.id for e in carteira.empresas),
        "contratos": sorted(c.id for c in carteira.contratos),
        "direcionadores": [
            {
                "empresa": d.empresa_id,
                "competencia": str(d.competencia),
                "valores": {k: str(v) for k, v in d.valores.items()},
            }
            for d in carteira.direcionadores
        ],
        "honorarios": [
            {"contrato": h.contrato_id, "competencia": str(h.competencia), "valor": str(h.valor)}
            for h in carteira.honorarios
        ],
    }


def gravar_carteira(
    uow: UnidadeDeTrabalho, carteira: Carteira, versao: int
) -> tuple[Rejeitada, ...]:
    """Normaliza nos fatos; devolve as referências a cadastros que não existem."""
    for contrato in carteira.contratos:
        # Cadastro novo apenas: o preço de um contrato existente é governado pelo produto.
        if uow.contratos.obter(contrato.id) is None:
            uow.contratos.salvar(contrato)
    for empresa in carteira.empresas:
        uow.empresas.salvar(empresa)
    empresas = {e.id: e for e in uow.empresas.listar()}
    contratos = {c.id for c in uow.contratos.listar()}
    rejeitadas = _gravar_vinculos(uow, carteira, set(empresas), contratos)
    _gravar_fatos(uow, carteira, empresas, versao)
    for honorario in carteira.honorarios:
        if honorario.contrato_id in contratos:
            uow.fatos.gravar_honorario(honorario)
    return rejeitadas


def _gravar_fatos(
    uow: UnidadeDeTrabalho, carteira: Carteira, empresas: Mapping[str, Empresa], versao: int
) -> None:
    horas: dict[tuple[str, Competencia], dict[str, Any]] = {}
    for h in carteira.horas:
        horas.setdefault((h.empresa_id, h.competencia), {})[h.departamento.value] = h.horas.valor
    for d in carteira.direcionadores:
        empresa = empresas.get(d.empresa_id)
        if empresa is not None:
            mes = horas.get((d.empresa_id, d.competencia), {})
            uow.fatos.gravar_empresa_mes(d, mes, versao, empresa.regime)


def _gravar_vinculos(
    uow: UnidadeDeTrabalho, carteira: Carteira, empresas: set[str], contratos: set[str]
) -> tuple[Rejeitada, ...]:
    rejeitadas: list[Rejeitada] = []
    for numero, vinculo in enumerate(carteira.vinculos, start=1):
        if vinculo.empresa_id in empresas and vinculo.contrato_id in contratos:
            uow.vinculos.salvar(vinculo)
        else:
            rejeitadas.append(Rejeitada("vinculos.csv", numero, "referencia_invalida"))
    return tuple(rejeitadas)


def registrar_extracao(
    uow: UnidadeDeTrabalho,
    relogio: Relogio,
    fonte: str,
    competencia: Competencia,
    carteira: Carteira,
    hash_conteudo: str,
    rejeicoes: tuple[Rejeitada, ...] = (),
) -> ResultadoDaImportacao:
    existente = uow.extracoes.versao_do_hash(fonte, competencia, hash_conteudo)
    if existente is not None:
        return ResultadoDaImportacao(existente, repetida=True, quarentena=0)
    agora: datetime = relogio.agora()
    versao = uow.extracoes.proxima_versao(fonte, competencia)
    origem = "planilha" if fonte == FONTE_PLANILHA else "conector"
    extracao = uow.extracoes.gravar(
        fonte, competencia, versao, origem, hash_conteudo, carteira_em_json(carteira), agora
    )
    todas = (*rejeicoes, *gravar_carteira(uow, carteira, versao))
    for r in todas:
        uow.extracoes.quarentenar(extracao, r.arquivo, r.linha, r.motivo)
    parametros = {"competencia": str(competencia)}
    uow.fila.enfileirar("conciliar", f"conciliar:{competencia}:{fonte}:{versao}", parametros, agora)
    uow.fila.enfileirar("recalibrar", f"recalibrar:{competencia}", parametros, agora)
    return ResultadoDaImportacao(versao, repetida=False, quarentena=len(todas))


class ImportarPlanilha:
    def __init__(
        self, fabrica: FabricaDeUnidades, relogio: Relogio, leitor: LeitorDeArquivo
    ) -> None:
        self._fabrica = fabrica
        self._relogio = relogio
        self._leitor = leitor

    def executar(
        self,
        principal: Principal,
        nome: str,
        conteudo: bytes,
        inicio: Competencia,
        fim: Competencia,
    ) -> ResultadoDaImportacao:
        autorizar(principal, Acao.IMPORTAR_DADOS)
        leitura = self._leitor.ler(nome, conteudo, inicio, fim)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            resultado = registrar_extracao(
                uow,
                self._relogio,
                FONTE_PLANILHA,
                fim,
                leitura.carteira,
                leitura.hash_conteudo,
                leitura.rejeicoes,
            )
            uow.auditoria.registrar(
                "carteira_importada",
                {"versao": resultado.versao, "repetida": resultado.repetida},
                usuario_id=principal.usuario_id,
            )
        return resultado
