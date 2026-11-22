"""Conector do Omie: contas a receber viram honorários cobrados (F1.24).

Mapeamento a confirmar com o escritório: o código do cliente no Omie é usado como id do contrato.
"""

import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from dynaprice.aplicacao.portas import ConectorIndisponivel, CredencialInvalida
from dynaprice.dominio.modelos import Carteira, Competencia, Dinheiro, Honorario

_CAMINHO = "/api/v1/financas/contareceber/"
_REGISTROS_POR_PAGINA = 200
_MAX_TENTATIVAS = 5
_ESPERA_INICIAL_S = 2
_STATUS_DE_ESPERA = frozenset({425, 429, 500, 502, 503, 504})
_STATUS_DE_CREDENCIAL = frozenset({401, 403})


class ConectorOmie:
    def __init__(
        self,
        cliente: httpx.Client,
        app_key: str,
        app_secret: str,
        esperar: Callable[[float], None] = time.sleep,
    ) -> None:
        self._cliente = cliente
        self._app_key = app_key
        self._app_secret = app_secret
        self._esperar = esperar

    def __repr__(self) -> str:
        return "ConectorOmie()"

    def extrair(self, inicio: Competencia, fim: Competencia) -> Carteira:
        somas: dict[tuple[str, Competencia], Decimal] = defaultdict(Decimal)
        pagina, total = 1, 1
        while pagina <= total:
            corpo = self._pagina(pagina)
            total = int(corpo.get("total_de_paginas", 1))
            for titulo in corpo.get("conta_receber_cadastro", []):
                self._somar(titulo, inicio, fim, somas)
            pagina += 1
        honorarios = tuple(
            Honorario(contrato, competencia, Dinheiro.de(valor))
            for (contrato, competencia), valor in sorted(somas.items(), key=str)
        )
        return Carteira((), (), (), (), (), honorarios)

    @staticmethod
    def _somar(
        titulo: dict[str, Any],
        inicio: Competencia,
        fim: Competencia,
        somas: dict[tuple[str, Competencia], Decimal],
    ) -> None:
        vencimento = datetime.strptime(titulo["data_vencimento"], "%d/%m/%Y")
        competencia = Competencia(vencimento.year, vencimento.month)
        if inicio <= competencia <= fim:
            chave = (str(titulo["codigo_cliente_fornecedor"]), competencia)
            somas[chave] += Decimal(str(titulo["valor_documento"]))

    def _pagina(self, pagina: int) -> dict[str, Any]:
        espera: float = _ESPERA_INICIAL_S
        for tentativa in range(1, _MAX_TENTATIVAS + 1):
            resposta = self._pedir(pagina)
            if resposta.status_code in _STATUS_DE_CREDENCIAL:
                raise CredencialInvalida(f"Omie recusou a credencial ({resposta.status_code})")
            if resposta.status_code not in _STATUS_DE_ESPERA:
                resposta.raise_for_status()
                corpo: dict[str, Any] = resposta.json()
                return corpo
            if tentativa < _MAX_TENTATIVAS:
                self._esperar(espera)
                espera *= 2
        raise ConectorIndisponivel(f"Omie indisponível na página {pagina}")

    def _pedir(self, pagina: int) -> httpx.Response:
        try:
            return self._cliente.post(
                _CAMINHO,
                json={
                    "call": "ListarContasReceber",
                    "app_key": self._app_key,
                    "app_secret": self._app_secret,
                    "param": [{"pagina": pagina, "registros_por_pagina": _REGISTROS_POR_PAGINA}],
                },
            )
        except httpx.TransportError as erro:
            raise ConectorIndisponivel("Omie inacessível") from erro
