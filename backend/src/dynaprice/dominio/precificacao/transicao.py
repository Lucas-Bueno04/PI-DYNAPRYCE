"""k_tr: transição limitada e congelamento nominal (Eq. 72; Algoritmo 3; Prop. 8; Eq. 73).

B_t = P_t·(1 + π_t); se P* ≥ B_t, P_{t+1} = min(P*, B_t·(1 + θ)); senão max(P*, P_t).
O resultado é arredondado por k_din e depois contido em [P_t, max(P*, P_t)], o que mantém
as propriedades (a) e (c) da Prop. 8 com qualquer estratégia de arredondamento.
"""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum

from dynaprice.dominio.modelos import Dinheiro, ValorInvalido
from dynaprice.dominio.precificacao.dinheiro import Arredondamento


class MotivoDoPasso(StrEnum):
    TETO = "teto"  # limitado por B·(1 + θ)
    ALVO = "alvo"  # alcançou P*
    CONGELADO = "congelado"  # alvo abaixo do corrigido: nominal mantido
    REVISAO_INTEGRAL = "revisao_integral"  # provisório em ℓ = 2 (seção 6.7)


@dataclass(frozen=True, slots=True)
class PassoDeTransicao:
    vigente: Dinheiro
    alvo: Dinheiro
    corrigido: Decimal  # B_t
    novo: Dinheiro
    motivo: MotivoDoPasso


class RegraDeTransicao:
    def __init__(self, teto_real_theta: Decimal, arredondamento: Arredondamento) -> None:
        if teto_real_theta < 0:
            raise ValorInvalido(f"θ deve ser ≥ 0: {teto_real_theta}")
        self._theta = teto_real_theta
        self._arredondamento = arredondamento

    def proximo(
        self,
        vigente: Dinheiro,
        alvo: Dinheiro,
        inflacao: Decimal = Decimal(0),
        revisao_integral: bool = False,
    ) -> PassoDeTransicao:
        if inflacao < 0:
            raise ValorInvalido(f"inflação do ciclo deve ser ≥ 0 (Prop. 8): {inflacao}")
        corrigido = vigente.valor * (1 + inflacao)
        if revisao_integral:
            return PassoDeTransicao(vigente, alvo, corrigido, alvo, MotivoDoPasso.REVISAO_INTEGRAL)
        if alvo.valor >= corrigido:
            teto = corrigido * (1 + self._theta)
            motivo = MotivoDoPasso.ALVO if alvo.valor <= teto else MotivoDoPasso.TETO
            exato = min(alvo.valor, teto)
        else:
            motivo = MotivoDoPasso.CONGELADO if alvo <= vigente else MotivoDoPasso.ALVO
            exato = max(alvo.valor, vigente.valor)
        novo = self._conter(self._arredondamento.arredondar(exato), vigente, alvo)
        return PassoDeTransicao(vigente, alvo, corrigido, novo, motivo)

    @staticmethod
    def _conter(novo: Dinheiro, vigente: Dinheiro, alvo: Dinheiro) -> Dinheiro:
        return min(max(novo, vigente), max(alvo, vigente))


def ciclos_ate_o_alvo(distancia: Decimal, teto_real_theta: Decimal) -> int:
    """t* = ⌈ln G / ln(1 + θ)⌉ para G = P*/P_0 > 1 com alvo real constante (Eq. 73)."""
    if distancia <= 1:
        return 0
    if teto_real_theta <= 0:
        raise ValorInvalido("com θ = 0 o alvo acima do preço nunca é alcançado")
    razao = distancia.ln() / (1 + teto_real_theta).ln()
    return int(razao.to_integral_value(rounding=ROUND_CEILING))
