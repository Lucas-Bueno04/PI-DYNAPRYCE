"""Adapter p_src sintético: carteira reprodutível pela semente (G1), sem dado real."""

import random

from dynaprice.adaptadores.saida.sintetico.esforco import GeradorDeEsforco
from dynaprice.adaptadores.saida.sintetico.estrutura import PlanejadorDeEstrutura, PlanoDaCarteira
from dynaprice.adaptadores.saida.sintetico.honorarios import GeradorDeHonorarios
from dynaprice.adaptadores.saida.sintetico.parametros import ParametrosSinteticos
from dynaprice.dominio.modelos import Carteira, Competencia, Contrato, Honorario, ValorInvalido


class GeradorDeCarteiraSintetica:
    """Implementa FonteDeCarteira; a mesma semente e a mesma janela dão a mesma carteira."""

    def __init__(self, parametros: ParametrosSinteticos) -> None:
        self._p = parametros

    def extrair(self, inicio: Competencia, fim: Competencia) -> Carteira:
        if fim < inicio:
            raise ValorInvalido(f"janela invertida: {inicio} > {fim}")
        aleatorio = random.Random(self._p.semente)
        plano = PlanejadorDeEstrutura(self._p, aleatorio).planejar(inicio, fim)
        esforco = GeradorDeEsforco(self._p, aleatorio).gerar(plano.empresas, inicio, fim)
        honorarios = GeradorDeHonorarios(self._p, aleatorio).gerar(
            plano, esforco.horas_medias, inicio, fim
        )
        return Carteira(
            empresas=tuple(e.empresa for e in plano.empresas),
            contratos=_contratos(plano, honorarios),
            vinculos=plano.vinculos,
            direcionadores=esforco.direcionadores,
            horas=esforco.horas,
            honorarios=honorarios,
        )


def _contratos(plano: PlanoDaCarteira, honorarios: tuple[Honorario, ...]) -> tuple[Contrato, ...]:
    vigente = {h.contrato_id: h.valor for h in honorarios}  # último mês prevalece
    return tuple(
        Contrato(c.id, vigente[c.id], mes_reajuste=c.mes_reajuste, provisorio=c.provisorio)
        for c in plano.contratos
    )
