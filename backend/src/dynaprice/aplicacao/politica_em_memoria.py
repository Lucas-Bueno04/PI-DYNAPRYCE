"""Política vigente em memória, conferida por versão a cada uso (D-RECARGA)."""

import threading
from dataclasses import dataclass
from uuid import UUID

from dynaprice.aplicacao.portas import UnidadeDeTrabalho
from dynaprice.dominio.modelos import PoliticaVersao
from dynaprice.dominio.precificacao import NucleoDePreco


@dataclass(frozen=True, slots=True)
class PoliticaVigente:
    politica: PoliticaVersao
    nucleo: NucleoDePreco


class PoliticaEmMemoria:
    def __init__(self) -> None:
        self._por_tenant: dict[UUID, PoliticaVigente] = {}
        self._trava = threading.Lock()

    def vigente(self, uow: UnidadeDeTrabalho, tenant_id: UUID) -> PoliticaVigente | None:
        versao = uow.politicas.versao_publicada()
        if versao is None:
            return None
        with self._trava:
            guardada = self._por_tenant.get(tenant_id)
        if guardada is not None and guardada.politica.versao == versao:
            return guardada
        politica = uow.politicas.publicada()
        if politica is None:
            return None
        nova = PoliticaVigente(politica, NucleoDePreco.da_politica(politica))
        with self._trava:
            self._por_tenant[tenant_id] = nova
        return nova

    def versao_em_memoria(self, tenant_id: UUID) -> int | None:
        with self._trava:
            guardada = self._por_tenant.get(tenant_id)
        return None if guardada is None else guardada.politica.versao

    def descartar(self, tenant_id: UUID) -> None:
        with self._trava:
            self._por_tenant.pop(tenant_id, None)

    def limpar(self) -> None:
        with self._trava:
            self._por_tenant.clear()
