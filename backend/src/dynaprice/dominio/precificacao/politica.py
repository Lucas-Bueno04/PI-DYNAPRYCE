"""k_pol: preço-alvo P* = κ·max(π_r, τ·H_pad), 1 ≤ κ ≤ κ̄ (Eq. 59; Prop. 3; Eq. 60).

Única implementação da regra de preço: cotação, recalibração e simulador passam por aqui.
"""

from dataclasses import dataclass
from decimal import Decimal

from dynaprice.dominio.modelos import (
    Dinheiro,
    Horas,
    Kappa,
    PoliticaVersao,
    Regime,
    Tarifa,
    ValorInvalido,
)
from dynaprice.dominio.precificacao.dinheiro import Arredondamento, arredondamento_da_politica


@dataclass(frozen=True, slots=True)
class PrecoAlvo:
    """Decomposição auditável do preço-alvo (A5): piso, parcela do esforço, κ e resultado."""

    regime: Regime
    horas_padrao: Horas
    piso: Dinheiro
    tarifa: Tarifa
    kappa: Kappa
    exato: Decimal  # κ·max(π_r, τ·H_pad) sem arredondar
    valor: Dinheiro  # arredondado por k_din

    @property
    def parcela_esforco(self) -> Decimal:
        return self.tarifa * self.horas_padrao

    @property
    def piso_vinculante(self) -> bool:
        return self.parcela_esforco < self.piso.valor


class PoliticaDePreco:
    def __init__(
        self, politica: PoliticaVersao, arredondamento: Arredondamento | None = None
    ) -> None:
        self._politica = politica
        self._arredondamento = arredondamento or arredondamento_da_politica(politica)

    @property
    def versao(self) -> PoliticaVersao:
        return self._politica

    def base(self, regime: Regime, horas_padrao: Horas) -> Decimal:
        """max(π_r, τ·H_pad): o preço-alvo com κ = 1, sem arredondar."""
        return max(self._politica.piso(regime).valor, self._politica.tarifa * horas_padrao)

    def preco_alvo(
        self, regime: Regime, horas_padrao: Horas, kappa: Kappa | None = None
    ) -> PrecoAlvo:
        kappa = kappa or Kappa.neutro()
        if kappa.valor > self._politica.kappa_maximo:
            raise ValorInvalido(
                f"κ = {kappa.valor} acima de κ̄ = {self._politica.kappa_maximo} "
                f"(política v{self._politica.versao})"
            )
        exato = kappa.valor * self.base(regime, horas_padrao)
        return PrecoAlvo(
            regime=regime,
            horas_padrao=horas_padrao,
            piso=self._politica.piso(regime),
            tarifa=self._politica.tarifa,
            kappa=kappa,
            exato=exato,
            valor=self.arredondar(exato),
        )

    def arredondar(self, valor: Decimal) -> Dinheiro:
        """k_din da política: todo preço sai arredondado pelo mesmo ponto."""
        return self._arredondamento.arredondar(valor)

    def ponto_de_quebra(self, regime: Regime) -> Horas:
        """H†_r = π_r / τ (Eq. 60): abaixo paga o piso, acima paga pelas horas-padrão."""
        return Horas(self._politica.piso(regime).valor / self._politica.tarifa.valor)
