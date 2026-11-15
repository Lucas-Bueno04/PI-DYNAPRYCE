"""Âncora externa da auditoria (RNF06): publica a cabeça da cadeia e confere o banco contra ela."""

from dataclasses import dataclass
from uuid import UUID

from dynaprice.aplicacao.portas import FabricaDeUnidades, Relogio
from dynaprice.aplicacao.portas.ancora import Ancora, AncoraExterna


@dataclass(frozen=True, slots=True)
class DivergenciaDeAncora:
    seq: int
    ancorado: str
    no_banco: str | None  # None: o evento ancorado não existe mais


@dataclass(frozen=True, slots=True)
class ResultadoDaVerificacao:
    tenant_id: UUID
    quebra_interna: int | None
    divergencias: tuple[DivergenciaDeAncora, ...]

    @property
    def integro(self) -> bool:
        return self.quebra_interna is None and not self.divergencias


class AncorarAuditoria:
    def __init__(self, fabrica: FabricaDeUnidades, ancora: AncoraExterna, relogio: Relogio) -> None:
        self._fabrica = fabrica
        self._ancora = ancora
        self._relogio = relogio

    def executar(self) -> int:
        """Âncora a cabeça de cada inquilino com evento novo; devolve quantas gravou."""
        total = 0
        for tenant_id in _inquilinos(self._fabrica):
            with self._fabrica.para_tenant(tenant_id) as uow:
                cabeca = uow.auditoria.cabeca()
            ultimas = self._ancora.listar(tenant_id)
            if cabeca is None or (ultimas and ultimas[-1].seq >= cabeca[0]):
                continue
            self._ancora.registrar(Ancora(tenant_id, cabeca[0], cabeca[1], self._relogio.agora()))
            total += 1
        return total


class VerificarAuditoria:
    def __init__(self, fabrica: FabricaDeUnidades, ancora: AncoraExterna) -> None:
        self._fabrica = fabrica
        self._ancora = ancora

    def executar(self) -> tuple[ResultadoDaVerificacao, ...]:
        return tuple(self._de(tenant_id) for tenant_id in _inquilinos(self._fabrica))

    def _de(self, tenant_id: UUID) -> ResultadoDaVerificacao:
        ancoras = self._ancora.listar(tenant_id)
        divergencias: list[DivergenciaDeAncora] = []
        with self._fabrica.para_tenant(tenant_id) as uow:
            quebra = uow.auditoria.primeira_quebra()
            for ancora in ancoras:
                no_banco = uow.auditoria.hash_em(ancora.seq)
                if no_banco != ancora.hash_hex:
                    divergencias.append(DivergenciaDeAncora(ancora.seq, ancora.hash_hex, no_banco))
        return ResultadoDaVerificacao(tenant_id, quebra, tuple(divergencias))


def _inquilinos(fabrica: FabricaDeUnidades) -> list[UUID]:
    with fabrica.sem_tenant() as uow:
        return list(uow.usuarios.inquilinos_ativos())
