"""Decisão humana sobre a recomendação (F1.27): aprovar, ajustar κ ou rejeitar."""

from dataclasses import dataclass, replace
from decimal import Decimal
from uuid import UUID

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.casos_de_uso.recalibrar import trajetoria_ate_o_alvo
from dynaprice.aplicacao.erros import Conflito, NaoEncontrado
from dynaprice.aplicacao.portas import FabricaDeUnidades, Relogio, UnidadeDeTrabalho
from dynaprice.dominio.modelos import (
    DESCONTO_SEM_JUSTIFICATIVA,
    Dinheiro,
    Horas,
    Kappa,
    Regime,
    ValorInvalido,
    fabricar_politica,
)
from dynaprice.dominio.modelos.autenticacao import Principal
from dynaprice.dominio.modelos.recomendacao import Recomendacao
from dynaprice.dominio.precificacao import NucleoDePreco


@dataclass(frozen=True, slots=True)
class Aprovar:
    pass


@dataclass(frozen=True, slots=True)
class AjustarKappa:
    kappa: Decimal
    justificativa: str


@dataclass(frozen=True, slots=True)
class Rejeitar:
    motivo: str


type Decisao = Aprovar | AjustarKappa | Rejeitar


def recalcular_com_kappa(
    uow: UnidadeDeTrabalho, recomendacao: Recomendacao, novo: Kappa
) -> tuple[Dinheiro, tuple[Dinheiro, ...]]:
    """Recalcula alvo e trajetória com as entradas gravadas e a política da recomendação."""
    registro = uow.politicas.obter(recomendacao.politica_versao)
    alvo = uow.precos_alvo.obter(recomendacao.preco_alvo_id)
    if registro is None or alvo is None:
        raise NaoEncontrado("entradas da recomendação")
    nucleo = NucleoDePreco.da_politica(fabricar_politica(registro.documento))
    entradas = alvo.entradas
    horas = Horas(Decimal(entradas["horas_padrao"]))
    inferido = nucleo.inferencia.preco(Regime(entradas["regime"]), horas, entradas["meses"], novo)
    passos = trajetoria_ate_o_alvo(
        nucleo, recomendacao.preco_vigente, inferido.valor, Decimal(entradas["inflacao"])
    )
    return inferido.valor, passos


class DecidirRecomendacao:
    def __init__(self, fabrica: FabricaDeUnidades, relogio: Relogio) -> None:
        self._fabrica = fabrica
        self._relogio = relogio

    def executar(
        self, principal: Principal, recomendacao_id: UUID, versao: int, decisao: Decisao
    ) -> None:
        autorizar(principal, Acao.DECIDIR_RECOMENDACAO)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            atual = uow.recomendacoes.obter(recomendacao_id)
            if atual is None:
                raise NaoEncontrado("recomendação")
            if atual.versao != versao:
                raise Conflito("a recomendação mudou desde a leitura")
            nova, tipo = self._aplicar(uow, atual, principal.usuario_id, decisao)
            uow.recomendacoes.salvar(nova, versao)
            uow.auditoria.registrar(
                tipo,
                {
                    "recomendacao": str(atual.id),
                    "contrato": atual.contrato_id,
                    "preco": str(nova.preco_proposto),
                    "kappa": str(nova.kappa.valor),
                    "motivo": nova.motivo,
                },
                usuario_id=principal.usuario_id,
            )

    def _aplicar(
        self, uow: UnidadeDeTrabalho, atual: Recomendacao, por: UUID, decisao: Decisao
    ) -> tuple[Recomendacao, str]:
        match decisao:
            case Aprovar():
                return atual.aprovar(por), "recomendacao_aprovada"
            case AjustarKappa():
                return self._ajustar(uow, atual, por, decisao), "recomendacao_ajustada"
            case Rejeitar(motivo):
                if not motivo.strip():
                    raise ValorInvalido("a rejeição exige motivo")
                return atual.rejeitar(por, motivo), "recomendacao_rejeitada"

    @staticmethod
    def _ajustar(
        uow: UnidadeDeTrabalho, atual: Recomendacao, por: UUID, decisao: AjustarKappa
    ) -> Recomendacao:
        registro = uow.politicas.obter(atual.politica_versao)
        if registro is None:
            raise NaoEncontrado("política da recomendação")
        maximo = fabricar_politica(registro.documento).kappa_maximo
        kappa = Kappa.de(decisao.kappa, maximo)  # D12: κ̄ da política; κ < 1 é inválido no tipo
        if kappa.valor - 1 > DESCONTO_SEM_JUSTIFICATIVA and not decisao.justificativa.strip():
            raise ValorInvalido("ajuste de κ acima de 5% exige justificativa")
        _, passos = recalcular_com_kappa(uow, atual, kappa)
        contrato = uow.contratos.obter(atual.contrato_id)
        if contrato is None:
            raise NaoEncontrado("contrato")
        uow.contratos.salvar(replace(contrato, kappa=kappa))
        return atual.aprovar(por, kappa, passos or None)
