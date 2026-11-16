"""Conector do BCB: IPCA mensal (série 433 do SGS, variação em %) para o índice de inflação."""

import calendar
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from dynaprice.aplicacao.portas import ConectorIndisponivel
from dynaprice.dominio.modelos import Competencia
from dynaprice.dominio.modelos.indice import VariacaoDeIndice

URL_BASE = "https://api.bcb.gov.br"
_CAMINHO = "/dados/serie/bcdata.sgs.433/dados"
_FORMATO = "%d/%m/%Y"


class ConectorBcbIpca:
    def __init__(self, cliente: httpx.Client) -> None:
        self._cliente = cliente

    def variacoes(self, inicio: Competencia, fim: Competencia) -> tuple[VariacaoDeIndice, ...]:
        ultimo_dia = calendar.monthrange(fim.ano, fim.mes)[1]
        try:
            resposta = self._cliente.get(
                f"{URL_BASE}{_CAMINHO}",
                params={
                    "formato": "json",
                    "dataInicial": f"01/{inicio.mes:02d}/{inicio.ano}",
                    "dataFinal": f"{ultimo_dia:02d}/{fim.mes:02d}/{fim.ano}",
                },
            )
            resposta.raise_for_status()
            itens = resposta.json()
        except (httpx.HTTPError, ValueError) as erro:
            raise ConectorIndisponivel("BCB indisponível ou resposta ilegível") from erro
        if not isinstance(itens, list):
            raise ConectorIndisponivel("BCB devolveu um formato inesperado")
        variacoes = [_variacao(item) for item in itens]
        return tuple(v for v in variacoes if inicio <= v.competencia <= fim)


def _variacao(item: Any) -> VariacaoDeIndice:
    try:
        data = datetime.strptime(item["data"], _FORMATO)
        percentual = Decimal(str(item["valor"]))
    except (KeyError, TypeError, ValueError, InvalidOperation) as erro:
        raise ConectorIndisponivel("BCB devolveu um item ilegível") from erro
    return VariacaoDeIndice(Competencia(data.year, data.month), percentual / 100)
