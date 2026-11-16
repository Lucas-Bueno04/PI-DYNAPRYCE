"""F1.24: conector do Omie com respostas no formato da API pública (sem chamada real)."""

import json
from decimal import Decimal
from typing import Any

import httpx
import pytest

from dynaprice.adaptadores.saida.conectores.omie import ConectorOmie
from dynaprice.aplicacao.portas import ConectorIndisponivel, CredencialInvalida
from dynaprice.dominio.modelos import Competencia

JAN, DEZ = Competencia(2026, 1), Competencia(2026, 12)


def _pagina(numero: int, total: int, titulos: list[dict[str, Any]]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"pagina": numero, "total_de_paginas": total, "conta_receber_cadastro": titulos},
    )


def _titulo(cliente: int, valor: float, vencimento: str) -> dict[str, Any]:
    return {
        "codigo_cliente_fornecedor": cliente,
        "valor_documento": valor,
        "data_vencimento": vencimento,
        "status_titulo": "RECEBIDO",
    }


class Servidor:
    def __init__(self, respostas: list[httpx.Response]) -> None:
        self.respostas = respostas
        self.pedidos: list[dict[str, Any]] = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(json.loads(pedido.content))
        return self.respostas.pop(0)


def _conector(servidor: Servidor, esperas: list[float] | None = None) -> ConectorOmie:
    cliente = httpx.Client(transport=httpx.MockTransport(servidor), base_url="https://omie.teste")
    registro = esperas if esperas is not None else []
    return ConectorOmie(cliente, "chave", "segredo-do-omie", esperar=registro.append)


def test_percorre_todas_as_paginas_e_soma_por_mes() -> None:
    servidor = Servidor(
        [
            _pagina(1, 2, [_titulo(10, 100.50, "05/01/2026")]),
            _pagina(2, 2, [_titulo(10, 50.25, "20/01/2026"), _titulo(11, 70, "05/02/2026")]),
        ]
    )
    honorarios = _conector(servidor).extrair(JAN, DEZ).honorarios
    assert {(h.contrato_id, str(h.competencia), h.valor.valor) for h in honorarios} == {
        ("10", "2026-01", Decimal("150.75")),
        ("11", "2026-02", Decimal("70.00")),
    }
    assert [p["param"][0]["pagina"] for p in servidor.pedidos] == [1, 2]


def test_fora_da_janela_e_ignorado() -> None:
    servidor = Servidor([_pagina(1, 1, [_titulo(10, 1, "05/01/2025")])])
    assert _conector(servidor).extrair(JAN, DEZ).honorarios == ()


def test_limite_de_taxa_faz_backoff_sem_perder_pagina() -> None:
    esperas: list[float] = []
    servidor = Servidor(
        [
            _pagina(1, 2, [_titulo(10, 1, "05/01/2026")]),
            httpx.Response(425, json={"faultstring": "aguarde"}),
            httpx.Response(429),
            _pagina(2, 2, [_titulo(11, 2, "05/01/2026")]),
        ]
    )
    honorarios = _conector(servidor, esperas).extrair(JAN, DEZ).honorarios
    assert {h.contrato_id for h in honorarios} == {"10", "11"}
    assert [p["param"][0]["pagina"] for p in servidor.pedidos] == [1, 2, 2, 2]
    assert esperas == [2, 4]


def test_limite_persistente_vira_indisponivel() -> None:
    servidor = Servidor([httpx.Response(429) for _ in range(5)])
    with pytest.raises(ConectorIndisponivel):
        _conector(servidor).extrair(JAN, DEZ)


def test_rede_fora_vira_indisponivel() -> None:
    def falha(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("sem rota")

    cliente = httpx.Client(transport=httpx.MockTransport(falha), base_url="https://omie.teste")
    with pytest.raises(ConectorIndisponivel):
        ConectorOmie(cliente, "c", "s", esperar=lambda _: None).extrair(JAN, DEZ)


@pytest.mark.parametrize("status", [401, 403])
def test_credencial_recusada_e_permanente(status: int) -> None:
    with pytest.raises(CredencialInvalida):
        _conector(Servidor([httpx.Response(status)])).extrair(JAN, DEZ)


def test_segredo_nao_aparece_no_erro_nem_na_representacao() -> None:
    servidor = Servidor([httpx.Response(500) for _ in range(5)])
    conector = _conector(servidor)
    assert "segredo-do-omie" not in repr(conector)
    with pytest.raises(ConectorIndisponivel) as erro:
        conector.extrair(JAN, DEZ)
    assert "segredo-do-omie" not in str(erro.value)
