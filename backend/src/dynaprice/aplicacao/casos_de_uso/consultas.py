"""Leituras usadas pela interface: recomendações com decomposição, listas e simulação."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.casos_de_uso.recalibrar import JANELA_MESES
from dynaprice.aplicacao.erros import NaoEncontrado
from dynaprice.aplicacao.portas import (
    Alerta,
    FabricaDeUnidades,
    RegistroDePolitica,
    SimuladorDeRascunho,
    UnidadeDeTrabalho,
)
from dynaprice.dominio.modelos import Competencia, Dinheiro, fabricar_politica
from dynaprice.dominio.modelos.autenticacao import Principal
from dynaprice.dominio.modelos.divergencia import Divergencia
from dynaprice.dominio.modelos.recomendacao import EstadoRecomendacao, Recomendacao


@dataclass(frozen=True, slots=True)
class RecomendacaoDetalhada:
    recomendacao: Recomendacao
    decomposicao: Mapping[str, Any]


def _decomposicao(uow: UnidadeDeTrabalho, recomendacao: Recomendacao) -> dict[str, Any]:
    alvo = uow.precos_alvo.obter(recomendacao.preco_alvo_id)
    registro = uow.politicas.obter(recomendacao.politica_versao)
    if alvo is None or registro is None:
        return {}
    entradas, documento = alvo.entradas, registro.documento
    regime = entradas["regime"]
    return {
        "preco_alvo": str(alvo.preco_alvo),
        "nivel_informacao": alvo.nivel,
        "horas_padrao": None if alvo.horas_padrao is None else str(alvo.horas_padrao),
        "horas_por_departamento": entradas.get("horas_por_departamento", {}),
        "regime": regime,
        "tarifa": documento["tarifa_hora_padrao"]["valor"],
        "piso": str(Dinheiro.de(documento["piso_por_segmento"][regime])),
        "kappa": entradas["kappa"],
    }


class ListarRecomendacoes:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(
        self, principal: Principal, estado: EstadoRecomendacao | None
    ) -> Sequence[RecomendacaoDetalhada]:
        autorizar(principal, Acao.VER_CARTEIRA)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            return [
                RecomendacaoDetalhada(r, _decomposicao(uow, r))
                for r in uow.recomendacoes.listar(estado)
            ]


class ListarPoliticas:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, principal: Principal) -> Sequence[RegistroDePolitica]:
        autorizar(principal, Acao.VER_CARTEIRA)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            return uow.politicas.listar()


class ListarDivergencias:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, principal: Principal) -> Sequence[Divergencia]:
        autorizar(principal, Acao.VER_CARTEIRA)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            return uow.divergencias.listar()


class ListarAlertas:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, principal: Principal) -> Sequence[Alerta]:
        autorizar(principal, Acao.VER_CARTEIRA)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            return uow.alertas.nao_reconhecidos()


class BaixarLote:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, principal: Principal, lote: UUID) -> bytes:
        autorizar(principal, Acao.EXPORTAR_RECOMENDACOES)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            arquivo = uow.lotes.arquivo(lote)
        if arquivo is None:
            raise NaoEncontrado("arquivo do lote")
        return arquivo


class SimularRascunho:
    def __init__(self, fabrica: FabricaDeUnidades, simulador: SimuladorDeRascunho) -> None:
        self._fabrica = fabrica
        self._simulador = simulador

    def executar(
        self, principal: Principal, documento: Mapping[str, Any], referencia: Competencia
    ) -> Mapping[str, Any]:
        autorizar(principal, Acao.USAR_LABORATORIO)
        politica = fabricar_politica({**documento, "versao": 1})
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            carteira = uow.fatos.carteira(referencia.somar(1 - JANELA_MESES), referencia)
        return self._simulador.simular(carteira, politica, referencia)
