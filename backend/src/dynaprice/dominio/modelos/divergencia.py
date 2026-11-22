"""Divergência de cobrança: aprovado × cobrado (F1.3, uc_conc)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import UUID

from dynaprice.dominio.modelos.competencia import Competencia
from dynaprice.dominio.modelos.dinheiro import Dinheiro
from dynaprice.dominio.modelos.erros import TransicaoInvalida, ValorInvalido


class SituacaoDivergencia(StrEnum):
    ABERTA = "aberta"
    JUSTIFICADA = "justificada"
    RESOLVIDA = "resolvida"


@dataclass(frozen=True, slots=True)
class Divergencia:
    id: UUID
    contrato_id: str
    competencia: Competencia
    aprovado: Dinheiro
    cobrado: Dinheiro
    situacao: SituacaoDivergencia = SituacaoDivergencia.ABERTA
    justificativa: str = ""

    def justificar(self, texto: str) -> Divergencia:
        if not texto.strip():
            raise ValorInvalido("a justificativa não pode ser vazia")
        if self.situacao is not SituacaoDivergencia.ABERTA:
            raise TransicaoInvalida(f"divergência: {self.situacao} → justificada proibido")
        return replace(self, situacao=SituacaoDivergencia.JUSTIFICADA, justificativa=texto)

    def resolver(self) -> Divergencia:
        if self.situacao is SituacaoDivergencia.RESOLVIDA:
            raise TransicaoInvalida("divergência já resolvida")
        return replace(self, situacao=SituacaoDivergencia.RESOLVIDA)
