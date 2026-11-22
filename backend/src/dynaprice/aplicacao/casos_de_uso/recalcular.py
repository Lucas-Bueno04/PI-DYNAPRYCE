"""`cli recalcular`: refaz o preço-alvo a partir das entradas gravadas (reprodutibilidade)."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from dynaprice.aplicacao.erros import NaoEncontrado
from dynaprice.aplicacao.portas import FabricaDeUnidades
from dynaprice.dominio.modelos import Horas, Kappa, Regime, fabricar_politica
from dynaprice.dominio.precificacao import NucleoDePreco


@dataclass(frozen=True, slots=True)
class ComparacaoDoRecalculo:
    gravado: Decimal
    recalculado: Decimal


class RecalcularPrecoAlvo:
    def __init__(self, fabrica: FabricaDeUnidades) -> None:
        self._fabrica = fabrica

    def executar(self, tenant_id: UUID, preco_alvo_id: UUID) -> ComparacaoDoRecalculo:
        with self._fabrica.para_tenant(tenant_id) as uow:
            alvo = uow.precos_alvo.obter(preco_alvo_id)
            registro = None if alvo is None else uow.politicas.obter(alvo.politica_versao)
        if alvo is None or registro is None:
            raise NaoEncontrado("preço-alvo")
        nucleo = NucleoDePreco.da_politica(fabricar_politica(registro.documento))
        entradas = alvo.entradas
        inferido = nucleo.inferencia.preco(
            Regime(entradas["regime"]),
            Horas(Decimal(entradas["horas_padrao"])),
            entradas["meses"],
            Kappa(Decimal(entradas["kappa"])),
        )
        return ComparacaoDoRecalculo(alvo.preco_alvo, inferido.valor.valor)
