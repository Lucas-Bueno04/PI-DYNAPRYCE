"""k_gat: recomendação de revisão quando |ln(P/P*)| > ln(1 + δ) (Eq. 74, zona morta simétrica)."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from dynaprice.dominio.modelos import Dinheiro, ValorInvalido


class DirecaoDoDesvio(StrEnum):
    ACIMA = "acima"  # preço vigente acima do alvo
    ABAIXO = "abaixo"
    NO_ALVO = "no_alvo"


@dataclass(frozen=True, slots=True)
class AvaliacaoDoGatilho:
    desvio: Decimal  # ln D_i, D_i = P_i / P*_i
    limiar: Decimal  # ln(1 + δ)

    @property
    def dispara(self) -> bool:
        return abs(self.desvio) > self.limiar

    @property
    def direcao(self) -> DirecaoDoDesvio:
        if self.desvio > 0:
            return DirecaoDoDesvio.ACIMA
        return DirecaoDoDesvio.ABAIXO if self.desvio < 0 else DirecaoDoDesvio.NO_ALVO


class GatilhoDeRevisao:
    def __init__(self, delta: Decimal) -> None:
        if delta < 0:
            raise ValorInvalido(f"δ deve ser ≥ 0: {delta}")
        self._limiar = (1 + delta).ln()

    def avaliar(self, vigente: Dinheiro, alvo: Dinheiro) -> AvaliacaoDoGatilho:
        if vigente.valor <= 0 or alvo.valor <= 0:
            raise ValorInvalido("gatilho exige preço vigente e alvo positivos")
        return AvaliacaoDoGatilho((vigente.valor / alvo.valor).ln(), self._limiar)
