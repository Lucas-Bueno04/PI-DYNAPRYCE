"""m_diag: implementa a porta AnalisadorDeCarteira (Facade sobre contexto, calibração e seções)."""

from dynaprice.dominio.estimacao.diagnostico.calibracao import calibrar
from dynaprice.dominio.estimacao.diagnostico.contexto import montar_contexto
from dynaprice.dominio.estimacao.diagnostico.secoes_carteira import (
    secao_fechamento,
    secao_mistos,
    secao_mudanca_de_regime,
)
from dynaprice.dominio.estimacao.diagnostico.secoes_modelos import secao_equacoes, secao_ridge
from dynaprice.dominio.estimacao.diagnostico.secoes_ocultacao import secao_ocultacao
from dynaprice.dominio.estimacao.diagnostico.secoes_politica import (
    secao_credibilidade,
    secao_pisos,
    secao_sensibilidade,
    secao_tarifa,
)
from dynaprice.dominio.estimacao.diagnostico.secoes_preco import (
    secao_carteira,
    secao_concentracao,
    secao_curva,
    secao_desalinhamento,
)
from dynaprice.dominio.modelos import Carteira, Competencia, Relatorio


class AnalisadorDoLaboratorio:
    def __init__(self, semente: int = 0) -> None:
        self._semente = semente

    def analisar(self, carteira: Carteira, referencia: Competencia) -> Relatorio:
        contexto = montar_contexto(carteira, referencia, self._semente)
        cal = calibrar(contexto)
        secoes = (
            secao_carteira(contexto),
            secao_curva(contexto),
            secao_concentracao(contexto),
            secao_desalinhamento(contexto),
            secao_equacoes(contexto),
            secao_ridge(contexto),
            secao_pisos(contexto, cal),
            secao_tarifa(contexto, cal),
            secao_sensibilidade(contexto, cal),
            secao_credibilidade(cal),
            secao_ocultacao(contexto, cal),
            secao_mistos(contexto),
            secao_mudanca_de_regime(contexto),
            secao_fechamento(contexto),
        )
        titulo = f"Relatório do laboratório DynaPrice — referência {referencia}"
        return Relatorio(titulo, secoes, {"politica_rascunho.json": cal.documento})
