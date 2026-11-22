"""Entidades mínimas do contrato como unidade de preço (ADR-003)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal

from dynaprice.dominio.modelos.ajustes import DescontoNegociado, Kappa
from dynaprice.dominio.modelos.competencia import Competencia
from dynaprice.dominio.modelos.dinheiro import Dinheiro
from dynaprice.dominio.modelos.equacao_de_tempo import congelar
from dynaprice.dominio.modelos.erros import ValorInvalido
from dynaprice.dominio.modelos.regime import Departamento, Regime


def _exigir_id(identificador: str, tipo: str) -> None:
    if not identificador.strip():
        raise ValorInvalido(f"{tipo} sem identificador")


@dataclass(frozen=True, slots=True)
class Empresa:
    """Unidade operacional: regime (obrigatório, ADR-004), direcionadores e horas.

    `departamentos` são os atendidos: uma filial só com folha não tem o β0 fiscal (ADR-003).
    """

    id: str
    regime: Regime
    departamentos: frozenset[Departamento] = frozenset(Departamento)

    def __post_init__(self) -> None:
        _exigir_id(self.id, "empresa")
        if not self.departamentos:
            raise ValorInvalido(f"empresa {self.id} sem departamento atendido")

    def atende(self, departamento: Departamento) -> bool:
        return departamento in self.departamentos


@dataclass(frozen=True, slots=True)
class Vinculo:
    """Empresa → contrato numa faixa de competências [desde, ate]; `ate` None = em aberto."""

    empresa_id: str
    contrato_id: str
    desde: Competencia
    ate: Competencia | None = None
    principal: bool = False

    def __post_init__(self) -> None:
        if self.ate is not None and self.ate < self.desde:
            raise ValorInvalido(f"vínculo termina ({self.ate}) antes de começar ({self.desde})")

    def vigente_em(self, competencia: Competencia) -> bool:
        return self.desde <= competencia and (self.ate is None or competencia <= self.ate)


@dataclass(frozen=True, slots=True, eq=False)
class Contrato:
    """Unidade comercial: preço vigente, κ, desconto, mês de reajuste e estado provisório."""

    id: str
    preco_vigente: Dinheiro
    kappa: Kappa = field(default_factory=Kappa.neutro)
    desconto: DescontoNegociado = field(default_factory=DescontoNegociado.nenhum)
    mes_reajuste: int | None = None
    provisorio: bool = False

    def __post_init__(self) -> None:
        _exigir_id(self.id, "contrato")
        if self.mes_reajuste is not None and not 1 <= self.mes_reajuste <= 12:
            raise ValorInvalido(f"mês de reajuste inválido: {self.mes_reajuste}")

    def __eq__(self, outro: object) -> bool:
        return isinstance(outro, Contrato) and outro.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    def reajustar(self, novo_preco: Dinheiro) -> Contrato:
        """Preço aprovado passa a vigorar e deixa de ser provisório (seção 6.7)."""
        return replace(self, preco_vigente=novo_preco, provisorio=False)


@dataclass(frozen=True, slots=True)
class Direcionadores:
    """Direcionadores x_k de uma empresa numa competência (contagens não negativas)."""

    empresa_id: str
    competencia: Competencia
    valores: Mapping[str, Decimal]

    def __post_init__(self) -> None:
        object.__setattr__(self, "valores", congelar(self.valores, "direcionadores"))

    def valor(self, nome: str) -> Decimal:
        return self.valores.get(nome, Decimal(0))
