"""Montagem das fontes de dados, usada pelo worker e pelo teste de conexão da API."""

from collections.abc import Mapping
from typing import Any

import httpx

from dynaprice.adaptadores.saida.conectores.dominio import ConectorDominio
from dynaprice.adaptadores.saida.conectores.omie import ConectorOmie
from dynaprice.adaptadores.saida.planilha import Pseudonimizador
from dynaprice.aplicacao.portas import FonteDeCarteira

_OMIE_URL = "https://app.omie.com.br"


def _fonte_dominio(chave: bytes) -> Any:
    def montar(credencial: Mapping[str, Any], _parametros: Mapping[str, Any]) -> FonteDeCarteira:
        # Importação tardia: pyodbc exige libodbc, presente só com o conector habilitado (D-ODBC).
        import pyodbc

        return ConectorDominio(
            lambda: pyodbc.connect(credencial["dsn"], readonly=True, timeout=30),
            Pseudonimizador(chave),
            pyodbc.Error,
        )

    return montar


def _fonte_omie(credencial: Mapping[str, Any], _parametros: Mapping[str, Any]) -> FonteDeCarteira:
    cliente = httpx.Client(base_url=_OMIE_URL, timeout=60)
    return ConectorOmie(cliente, credencial["app_key"], credencial["app_secret"])


def fontes_de_dados(chave: bytes) -> dict[str, Any]:
    return {"dominio": _fonte_dominio(chave), "omie": _fonte_omie}
