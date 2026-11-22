"""k_tar: origem da tarifa τ como Strategy (seções 6.4 e 6.5).

- TarifaPorPrecoRevelado: τ̂ = ΣF / ΣH_pad sobre os contratos com informação completa (Eq. 65; D3).
- TarifaAncoradaEmCusto: τ = τ_c / ϱ · (1 + m) (Eq. 63).
- TarifaPorReceitaAlvo: R(τ) = R_alvo resolvida exatamente (Prop. 5, Eq. 67); com R_alvo = R0
  é o cenário de receita constante τ*, usado só como referência (Prop. 7).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from dynaprice.dominio.modelos import Dinheiro, Horas, Kappa, Regime, Tarifa, ValorInvalido

type Pisos = Mapping[Regime, Dinheiro]


@dataclass(frozen=True, slots=True)
class ObservacaoDeTarifa:
    """Um contrato de 𝒞: regime, H_pad, honorário praticado F e κ."""

    regime: Regime
    horas_padrao: Horas
    honorario: Dinheiro
    kappa: Kappa


class EstimadorDeTarifa(Protocol):
    def estimar(self, observacoes: Sequence[ObservacaoDeTarifa], pisos: Pisos) -> Tarifa: ...


class TarifaPorPrecoRevelado:
    def estimar(self, observacoes: Sequence[ObservacaoDeTarifa], pisos: Pisos) -> Tarifa:
        horas = sum((o.horas_padrao.valor for o in observacoes), Decimal(0))
        if horas <= 0:
            raise ValorInvalido("τ̂ exige horas-padrão positivas em 𝒞")
        return Tarifa(sum((o.honorario.valor for o in observacoes), Decimal(0)) / horas)


class TarifaAncoradaEmCusto:
    def __init__(self, custo_por_hora: Decimal, rho: Decimal, margem: Decimal) -> None:
        if custo_por_hora <= 0 or rho <= 0 or margem <= -1:
            raise ValorInvalido("custo e ϱ devem ser > 0 e a margem > -100%")
        self._tarifa = Tarifa(custo_por_hora / rho * (1 + margem))

    def estimar(self, observacoes: Sequence[ObservacaoDeTarifa], pisos: Pisos) -> Tarifa:
        return self._tarifa


def margem_implicita(tarifa: Decimal, rho: Decimal, custo_por_hora: Decimal) -> Decimal:
    """m = τ·ϱ / τ_c − 1 (Eq. 64)."""
    return tarifa * rho / custo_por_hora - 1


def receita(tarifa: Decimal, observacoes: Sequence[ObservacaoDeTarifa], pisos: Pisos) -> Decimal:
    """R(τ) = Σ κ_i·max(π_r(i), τ·H_i) (Eq. 66)."""
    return sum(
        (
            o.kappa.valor * max(pisos[o.regime].valor, tarifa * o.horas_padrao.valor)
            for o in observacoes
        ),
        Decimal(0),
    )


@dataclass(frozen=True, slots=True)
class _Ponto:
    quebra: Decimal  # b_i = π_i / H_i
    kappa_horas: Decimal  # κ_i·H_i
    kappa_piso: Decimal  # κ_i·π_i


class TarifaPorReceitaAlvo:
    def __init__(self, receita_alvo: Decimal) -> None:
        self._alvo = receita_alvo

    @classmethod
    def receita_constante(cls, observacoes: Sequence[ObservacaoDeTarifa]) -> TarifaPorReceitaAlvo:
        return cls(sum((o.honorario.valor for o in observacoes), Decimal(0)))

    def estimar(self, observacoes: Sequence[ObservacaoDeTarifa], pisos: Pisos) -> Tarifa:
        pontos = sorted((_ponto(o, pisos) for o in observacoes), key=lambda p: p.quebra)
        pisos_restantes = sum((p.kappa_piso for p in pontos), Decimal(0))  # Π_0 = R(0)
        if pisos_restantes >= self._alvo:
            raise ValorInvalido("Prop. 4: Σ κ·π_r deve ser menor que a receita-alvo")
        inclinacao = Decimal(0)
        escolhido = (pisos_restantes, inclinacao)
        for ponto in pontos:  # Π_m e S_m acumulados; m* = maior m com R(b_(m)) ≤ R_alvo
            pisos_restantes -= ponto.kappa_piso
            inclinacao += ponto.kappa_horas
            if pisos_restantes + ponto.quebra * inclinacao > self._alvo:
                break
            escolhido = (pisos_restantes, inclinacao)
        return Tarifa((self._alvo - escolhido[0]) / escolhido[1])


def _ponto(o: ObservacaoDeTarifa, pisos: Pisos) -> _Ponto:
    if o.horas_padrao.valor <= 0:
        raise ValorInvalido("Prop. 4 exige H_pad > 0 em todo contrato de 𝒞")
    piso = pisos[o.regime].valor
    return _Ponto(
        piso / o.horas_padrao.valor, o.kappa.valor * o.horas_padrao.valor, o.kappa.valor * piso
    )


def tarifa_por_bissecao(
    observacoes: Sequence[ObservacaoDeTarifa],
    pisos: Pisos,
    receita_alvo: Decimal,
    precisao: Decimal = Decimal("1e-6"),
) -> Decimal:
    """Bisseção (Eq. 68) para variantes em que R não é afim por partes."""
    baixo, alto = Decimal(0), Decimal(1)
    while receita(alto, observacoes, pisos) < receita_alvo:
        alto *= 2
    while alto - baixo > precisao:
        meio = (baixo + alto) / 2
        if receita(meio, observacoes, pisos) < receita_alvo:
            baixo = meio
        else:
            alto = meio
    return (baixo + alto) / 2
