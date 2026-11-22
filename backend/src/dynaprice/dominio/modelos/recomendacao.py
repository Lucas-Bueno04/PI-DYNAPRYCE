"""Recomendação de reajuste: State por tabela de transições (F1.3)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from uuid import UUID

from dynaprice.dominio.modelos.ajustes import Kappa
from dynaprice.dominio.modelos.competencia import Competencia
from dynaprice.dominio.modelos.dinheiro import Dinheiro
from dynaprice.dominio.modelos.erros import TransicaoInvalida


class EstadoRecomendacao(StrEnum):
    PENDENTE = "pendente"
    APROVADA = "aprovada"
    REJEITADA = "rejeitada"
    EXPIRADA = "expirada"
    EXPORTADA = "exportada"
    FALHA_EXPORTACAO = "falha_exportacao"


_E = EstadoRecomendacao


@dataclass(frozen=True, slots=True)
class Recomendacao:
    id: UUID
    contrato_id: str
    preco_alvo_id: UUID
    politica_versao: int
    competencia: Competencia
    efeito: Competencia
    preco_vigente: Dinheiro
    preco_proposto: Dinheiro
    trajetoria: tuple[Dinheiro, ...]
    kappa: Kappa = field(default_factory=Kappa.neutro)
    estado: EstadoRecomendacao = _E.PENDENTE
    versao: int = 1
    lote_id: UUID | None = None
    motivo: str = ""
    decidido_por: UUID | None = None

    def _transitar(
        self, origem: EstadoRecomendacao, destino: EstadoRecomendacao, **mudancas: object
    ) -> Recomendacao:
        """A origem vem de cada ação: o mesmo destino não abre o caminho de outra ação."""
        if self.estado is not origem:
            raise TransicaoInvalida(f"recomendação: {self.estado} → {destino} proibido")
        return replace(self, estado=destino, versao=self.versao + 1, **mudancas)  # type: ignore[arg-type]

    def aprovar(
        self,
        por: UUID,
        kappa: Kappa | None = None,
        trajetoria: tuple[Dinheiro, ...] | None = None,
    ) -> Recomendacao:
        passos = trajetoria or self.trajetoria
        return self._transitar(
            _E.PENDENTE,
            _E.APROVADA,
            decidido_por=por,
            kappa=kappa or self.kappa,
            trajetoria=passos,
            preco_proposto=passos[0],
        )

    def rejeitar(self, por: UUID, motivo: str) -> Recomendacao:
        return self._transitar(_E.PENDENTE, _E.REJEITADA, decidido_por=por, motivo=motivo)

    def expirar(self) -> Recomendacao:
        return self._transitar(_E.PENDENTE, _E.EXPIRADA)

    def exportar(self, lote_id: UUID) -> Recomendacao:
        return self._transitar(_E.APROVADA, _E.EXPORTADA, lote_id=lote_id)

    def falhar_exportacao(self) -> Recomendacao:
        return self._transitar(_E.APROVADA, _E.FALHA_EXPORTACAO)

    def tentar_de_novo(self) -> Recomendacao:
        return self._transitar(_E.FALHA_EXPORTACAO, _E.APROVADA)
