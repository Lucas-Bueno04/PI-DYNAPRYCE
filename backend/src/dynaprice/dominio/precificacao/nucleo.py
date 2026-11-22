"""Factory do núcleo de preço: liga k_pol, k_inf, k_tr, k_gat e k_din a uma versão de política.

Único lugar onde o núcleo é montado; cotação, recalibração e simulador recebem o resultado.
"""

from dataclasses import dataclass

from dynaprice.dominio.modelos import PoliticaVersao
from dynaprice.dominio.precificacao.dinheiro import arredondamento_da_politica
from dynaprice.dominio.precificacao.equacoes_tempo import EquacoesDeTempo
from dynaprice.dominio.precificacao.gatilho import GatilhoDeRevisao
from dynaprice.dominio.precificacao.inferencia import InferenciaDePreco, PisoDoRegime
from dynaprice.dominio.precificacao.politica import PoliticaDePreco
from dynaprice.dominio.precificacao.transicao import RegraDeTransicao


@dataclass(frozen=True, slots=True)
class NucleoDePreco:
    politica: PoliticaVersao
    equacoes: EquacoesDeTempo
    preco: PoliticaDePreco
    inferencia: InferenciaDePreco
    transicao: RegraDeTransicao
    gatilho: GatilhoDeRevisao

    @classmethod
    def da_politica(cls, politica: PoliticaVersao) -> NucleoDePreco:
        preco = PoliticaDePreco(politica)
        return cls(
            politica=politica,
            equacoes=EquacoesDeTempo(politica),
            preco=preco,
            inferencia=InferenciaDePreco(preco, PisoDoRegime(politica)),
            transicao=RegraDeTransicao(
                politica.teto_real_theta, arredondamento_da_politica(politica)
            ),
            gatilho=GatilhoDeRevisao(politica.gatilho_delta),
        )
