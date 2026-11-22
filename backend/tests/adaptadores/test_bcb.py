"""F3.5: conector do BCB (SGS 433, IPCA mensal em %) com respostas sintéticas no formato público."""

from decimal import Decimal

import httpx
import pytest

from dynaprice.adaptadores.saida.conectores.bcb import ConectorBcbIpca
from dynaprice.aplicacao.portas import ConectorIndisponivel
from dynaprice.dominio.modelos import Competencia


def _conector(
    resposta: httpx.Response, pedidos: list[httpx.Request] | None = None
) -> ConectorBcbIpca:
    def atender(pedido: httpx.Request) -> httpx.Response:
        if pedidos is not None:
            pedidos.append(pedido)
        return resposta

    return ConectorBcbIpca(httpx.Client(transport=httpx.MockTransport(atender)))


def test_converte_percentual_em_fracao_e_data_em_competencia() -> None:
    corpo = [{"data": "01/01/2026", "valor": "0.42"}, {"data": "01/02/2026", "valor": "-0.10"}]
    variacoes = _conector(httpx.Response(200, json=corpo)).variacoes(
        Competencia(2026, 1), Competencia(2026, 2)
    )
    assert [(v.competencia, v.variacao) for v in variacoes] == [
        (Competencia(2026, 1), Decimal("0.0042")),
        (Competencia(2026, 2), Decimal("-0.0010")),
    ]


def test_pede_a_serie_433_com_o_intervalo_em_dd_mm_aaaa() -> None:
    pedidos: list[httpx.Request] = []
    _conector(httpx.Response(200, json=[]), pedidos).variacoes(
        Competencia(2026, 1), Competencia(2026, 10)
    )
    (pedido,) = pedidos
    assert pedido.url.path == "/dados/serie/bcdata.sgs.433/dados"
    assert dict(pedido.url.params) == {
        "formato": "json",
        "dataInicial": "01/01/2026",
        "dataFinal": "31/10/2026",
    }


def test_ignora_meses_fora_do_intervalo_pedido() -> None:
    corpo = [{"data": "01/12/2025", "valor": "0.5"}, {"data": "01/01/2026", "valor": "0.4"}]
    variacoes = _conector(httpx.Response(200, json=corpo)).variacoes(
        Competencia(2026, 1), Competencia(2026, 1)
    )
    assert [v.competencia for v in variacoes] == [Competencia(2026, 1)]


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(500),
        httpx.Response(429),
        httpx.Response(200, text="<html>indisponível</html>"),
        httpx.Response(200, json={"erro": "x"}),
        httpx.Response(200, json=[{"data": "2026-01", "valor": "0.4"}]),
        httpx.Response(200, json=[{"data": "01/01/2026", "valor": "abc"}]),
    ],
)
def test_resposta_ruim_vira_conector_indisponivel(resposta: httpx.Response) -> None:
    with pytest.raises(ConectorIndisponivel):
        _conector(resposta).variacoes(Competencia(2026, 1), Competencia(2026, 1))


def test_falha_de_rede_vira_conector_indisponivel() -> None:
    def cair(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("lento")

    conector = ConectorBcbIpca(httpx.Client(transport=httpx.MockTransport(cair)))
    with pytest.raises(ConectorIndisponivel):
        conector.variacoes(Competencia(2026, 1), Competencia(2026, 1))
