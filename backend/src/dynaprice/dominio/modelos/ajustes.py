"""Multiplicador de complexidade κ (Eq. 59, A5) e desconto negociado (D12 revisada)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from dynaprice.dominio.modelos.conversao import Numero, para_decimal
from dynaprice.dominio.modelos.dinheiro import Dinheiro
from dynaprice.dominio.modelos.erros import ValorInvalido

KAPPA_TETO_ABSOLUTO = Decimal("1.2")  # D12 revisada: κ ∈ [1,0; 1,2]
DESCONTO_SEM_JUSTIFICATIVA = Decimal("0.05")


@dataclass(frozen=True, slots=True, order=True)
class Kappa:
    """κ com 1 ≤ κ ≤ κ̄; κ < 1 quebraria A1/A2 e a Prop. 7."""

    valor: Decimal

    def __post_init__(self) -> None:
        if not Decimal(1) <= self.valor <= KAPPA_TETO_ABSOLUTO:
            raise ValorInvalido(f"κ fora de [1; {KAPPA_TETO_ABSOLUTO}]: {self.valor}")

    @classmethod
    def de(cls, valor: Numero, maximo: Decimal = KAPPA_TETO_ABSOLUTO) -> Kappa:
        kappa = cls(para_decimal(valor, "kappa"))
        if kappa.valor > maximo:
            raise ValorInvalido(f"κ = {kappa.valor} acima de κ̄ = {maximo} da política")
        return kappa

    @classmethod
    def neutro(cls) -> Kappa:
        return cls(Decimal(1))


@dataclass(frozen=True, slots=True)
class DescontoNegociado:
    """Desconto comercial fora da regra de preço: auditado, justificado acima de 5%."""

    percentual: Decimal
    justificativa: str = ""

    def __post_init__(self) -> None:
        if not Decimal(0) <= self.percentual < 1:
            raise ValorInvalido(f"desconto fora de [0; 1): {self.percentual}")
        if self.percentual > DESCONTO_SEM_JUSTIFICATIVA and not self.justificativa.strip():
            raise ValorInvalido("desconto acima de 5% exige justificativa")

    @classmethod
    def de(cls, percentual: Numero, justificativa: str = "") -> DescontoNegociado:
        return cls(para_decimal(percentual, "desconto"), justificativa)

    @classmethod
    def nenhum(cls) -> DescontoNegociado:
        return cls(Decimal(0))

    def aplicar(self, preco: Dinheiro) -> Dinheiro:
        return Dinheiro.de(preco.valor * (1 - self.percentual))
