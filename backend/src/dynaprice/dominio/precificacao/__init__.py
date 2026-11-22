"""Anel 1: núcleo de preço (k_*), única implementação da regra de preço (ADR-001)."""

from dynaprice.dominio.precificacao.agregacao import (
    AgregadoDoContrato,
    AgregadorDeContratos,
    MotivoPendencia,
    Pendencia,
    RegraDeSegmento,
    ResultadoDaAgregacao,
    empresas_sem_vinculo,
    regime_da_principal,
)
from dynaprice.dominio.precificacao.dinheiro import (
    Arredondamento,
    ArredondamentoAoCentavo,
    ArredondamentoComercial,
    arredondamento_da_politica,
)
from dynaprice.dominio.precificacao.equacoes_tempo import (
    EquacoesDeTempo,
    HorasPadrao,
    media_dos_direcionadores,
)
from dynaprice.dominio.precificacao.gatilho import (
    AvaliacaoDoGatilho,
    DirecaoDoDesvio,
    GatilhoDeRevisao,
)
from dynaprice.dominio.precificacao.inferencia import (
    BaseSemHistorico,
    InferenciaDePreco,
    NivelDeInformacao,
    PisoDoRegime,
    PrecoInferido,
    fator_de_credibilidade,
    nivel_de_informacao,
)
from dynaprice.dominio.precificacao.nucleo import NucleoDePreco
from dynaprice.dominio.precificacao.politica import PoliticaDePreco, PrecoAlvo
from dynaprice.dominio.precificacao.tarifa import (
    EstimadorDeTarifa,
    ObservacaoDeTarifa,
    TarifaAncoradaEmCusto,
    TarifaPorPrecoRevelado,
    TarifaPorReceitaAlvo,
    margem_implicita,
    receita,
    tarifa_por_bissecao,
)
from dynaprice.dominio.precificacao.transicao import (
    MotivoDoPasso,
    PassoDeTransicao,
    RegraDeTransicao,
    ciclos_ate_o_alvo,
)

__all__ = [
    "AgregadoDoContrato",
    "AgregadorDeContratos",
    "Arredondamento",
    "ArredondamentoAoCentavo",
    "ArredondamentoComercial",
    "AvaliacaoDoGatilho",
    "BaseSemHistorico",
    "DirecaoDoDesvio",
    "EquacoesDeTempo",
    "EstimadorDeTarifa",
    "GatilhoDeRevisao",
    "HorasPadrao",
    "InferenciaDePreco",
    "MotivoDoPasso",
    "MotivoPendencia",
    "NivelDeInformacao",
    "NucleoDePreco",
    "ObservacaoDeTarifa",
    "PassoDeTransicao",
    "Pendencia",
    "PisoDoRegime",
    "PoliticaDePreco",
    "PrecoAlvo",
    "PrecoInferido",
    "RegraDeSegmento",
    "RegraDeTransicao",
    "ResultadoDaAgregacao",
    "TarifaAncoradaEmCusto",
    "TarifaPorPrecoRevelado",
    "TarifaPorReceitaAlvo",
    "arredondamento_da_politica",
    "ciclos_ate_o_alvo",
    "empresas_sem_vinculo",
    "fator_de_credibilidade",
    "margem_implicita",
    "media_dos_direcionadores",
    "nivel_de_informacao",
    "receita",
    "regime_da_principal",
    "tarifa_por_bissecao",
]
