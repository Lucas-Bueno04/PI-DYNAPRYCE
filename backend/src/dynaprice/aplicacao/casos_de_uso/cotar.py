"""d_cot: cotação de cliente novo pela cascata da ADR-004 (sequência "cotação", plano 4.5).

O preço vem de `InferenciaDePreco` (k_inf), a mesma regra da recalibração; este caso de uso só
escolhe a política vigente, monta a decomposição auditável e grava entradas e versão, o que
permite reproduzir o preço depois de uma nova publicação (`ReproduzirCotacao`).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from dynaprice.aplicacao.autorizacao import Acao, autorizar
from dynaprice.aplicacao.erros import Conflito, NaoEncontrado
from dynaprice.aplicacao.politica_em_memoria import PoliticaEmMemoria, PoliticaVigente
from dynaprice.aplicacao.portas import FabricaDeUnidades, Relogio
from dynaprice.dominio.modelos import Dinheiro, Horas, Kappa, Regime, fabricar_politica
from dynaprice.dominio.modelos.autenticacao import Principal
from dynaprice.dominio.precificacao import NucleoDePreco
from dynaprice.dominio.precificacao.inferencia import NivelDeInformacao, PrecoInferido


@dataclass(frozen=True, slots=True)
class PedidoDeCotacao:
    regime: Regime  # obrigatório (ADR-004 item 2)
    meses: int = 0
    horas_padrao: Decimal | None = None
    kappa: Decimal | None = None

    def entradas(self) -> dict[str, Any]:
        return {
            "regime": self.regime.value,
            "meses": self.meses,
            "horas_padrao": None if self.horas_padrao is None else str(self.horas_padrao),
            "kappa": None if self.kappa is None else str(self.kappa),
        }


@dataclass(frozen=True, slots=True)
class Cotacao:
    id: UUID
    preco: Dinheiro
    politica_versao: int
    provisorio: bool
    decomposicao: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ComparacaoDaCotacao:
    gravado: Decimal
    recalculado: Decimal


_MOTIVO = {
    NivelDeInformacao.SEM_HISTORICO: "sem histórico: preço provisório igual ao piso do regime",
    NivelDeInformacao.PARCIAL: "histórico parcial: mistura do esforço medido e do piso do regime, "
    "pesada pela credibilidade Z; revisão integral ao completar 12 meses",
    NivelDeInformacao.COMPLETO: "12 meses ou mais: preço definitivo κ·max(piso, τ·H_pad)",
}


def _inferir(nucleo: NucleoDePreco, pedido: PedidoDeCotacao) -> PrecoInferido:
    horas = None if pedido.horas_padrao is None else Horas(pedido.horas_padrao)
    kappa = None if pedido.kappa is None else Kappa(pedido.kappa)
    return nucleo.inferencia.preco(pedido.regime, horas, pedido.meses, kappa)


def _decompor(
    nucleo: NucleoDePreco, pedido: PedidoDeCotacao, inferido: PrecoInferido
) -> dict[str, Any]:
    politica = nucleo.politica
    piso = politica.piso(pedido.regime)
    alvo = inferido.alvo
    base = None if alvo is None else nucleo.preco.base(pedido.regime, alvo.horas_padrao)
    return {
        "nivel_informacao": inferido.nivel.value,
        "regime": pedido.regime.value,
        "meses": pedido.meses,
        "piso": str(piso),
        "tarifa": str(politica.tarifa.valor),
        "horas_padrao": None if alvo is None else str(alvo.horas_padrao.valor),
        "base_propria": None if base is None else str(nucleo.preco.arredondar(base)),
        "piso_vinculante": None if alvo is None else alvo.piso_vinculante,
        "credibilidade_z": str(inferido.credibilidade.normalize()),
        "kappa": str(Kappa(pedido.kappa).valor if pedido.kappa else Kappa.neutro().valor),
        "preco_exato": str(inferido.exato),
        "preco": str(inferido.valor),
        "provisorio": inferido.provisorio,
        "motivo": _MOTIVO[inferido.nivel],
    }


class CotarServico:
    def __init__(
        self, fabrica: FabricaDeUnidades, relogio: Relogio, memoria: PoliticaEmMemoria
    ) -> None:
        self._fabrica = fabrica
        self._relogio = relogio
        self._memoria = memoria

    def executar(self, principal: Principal, pedido: PedidoDeCotacao) -> Cotacao:
        autorizar(principal, Acao.COTAR_SERVICO)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            vigente = self._memoria.vigente(uow, principal.tenant_id)
            if vigente is None:
                raise Conflito("nenhuma política publicada: publique uma antes de cotar")
            inferido = _inferir(vigente.nucleo, pedido)
            decomposicao = _decompor(vigente.nucleo, pedido, inferido)
            cotacao_id = self._gravar(uow, principal, vigente, pedido, inferido, decomposicao)
        return Cotacao(
            cotacao_id, inferido.valor, vigente.politica.versao, inferido.provisorio, decomposicao
        )

    @staticmethod
    def _gravar(
        uow: Any,
        principal: Principal,
        vigente: PoliticaVigente,
        pedido: PedidoDeCotacao,
        inferido: PrecoInferido,
        decomposicao: Mapping[str, Any],
    ) -> UUID:
        versao = vigente.politica.versao
        cotacao_id: UUID = uow.cotacoes.gravar(
            pedido.regime.value,
            versao,
            pedido.entradas(),
            inferido.valor.valor,
            decomposicao,
            principal.usuario_id,
        )
        uow.auditoria.registrar(
            "cotacao_criada",
            {"cotacao": str(cotacao_id), "politica": versao, "preco": str(inferido.valor)},
            usuario_id=principal.usuario_id,
        )
        return cotacao_id


class ReproduzirCotacao:
    """Refaz o preço com as entradas e a versão gravadas, mesmo depois de nova publicação."""

    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, principal: Principal, cotacao_id: UUID) -> ComparacaoDaCotacao:
        autorizar(principal, Acao.COTAR_SERVICO)
        with self._fabrica.para_tenant(principal.tenant_id) as uow:
            cotacao = uow.cotacoes.obter(cotacao_id)
            registro = None if cotacao is None else uow.politicas.obter(cotacao.politica_versao)
        if cotacao is None or registro is None:
            raise NaoEncontrado("cotação")
        nucleo = NucleoDePreco.da_politica(fabricar_politica(registro.documento))
        e = cotacao.entradas
        pedido = PedidoDeCotacao(
            Regime(e["regime"]),
            e["meses"],
            None if e["horas_padrao"] is None else Decimal(e["horas_padrao"]),
            None if e["kappa"] is None else Decimal(e["kappa"]),
        )
        return ComparacaoDaCotacao(cotacao.preco, _inferir(nucleo, pedido).valor.valor)
