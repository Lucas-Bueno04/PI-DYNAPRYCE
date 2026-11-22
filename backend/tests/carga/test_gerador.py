"""F2.6: o gerador de carga da cotação (RNF02: p95 < 300 ms, erro < 0,5%)."""

import asyncio
import json

import httpx
import pytest

from tests.carga.gerador import Medida, percentil, rodar, veredito


def _cliente(manipulador: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=manipulador, base_url="https://teste")


def test_percentil_por_posto_mais_proximo() -> None:
    valores = [float(i) for i in range(1, 101)]
    assert percentil(valores, 95) == 95.0
    assert percentil(valores, 50) == 50.0
    assert percentil([7.0], 95) == 7.0


def test_percentil_sem_amostras_e_invalido() -> None:
    with pytest.raises(ValueError, match="amostras"):
        percentil([], 95)


def test_veredito_aprova_dentro_dos_limites() -> None:
    medida = Medida(latencias_ms=[100.0] * 200, erros=0, total=200)
    resultado = veredito(medida)
    assert resultado.aprovado and resultado.p95_ms == 100.0 and resultado.taxa_de_erro == 0


def test_veredito_reprova_por_latencia() -> None:
    medida = Medida(latencias_ms=[100.0] * 90 + [400.0] * 10, erros=0, total=100)
    assert not veredito(medida).aprovado


def test_veredito_reprova_por_erro_acima_de_meio_por_cento() -> None:
    assert not veredito(Medida(latencias_ms=[10.0] * 99, erros=1, total=100)).aprovado
    assert veredito(Medida(latencias_ms=[10.0] * 199, erros=1, total=200)).aprovado is False
    assert veredito(Medida(latencias_ms=[10.0] * 1000, erros=4, total=1004)).aprovado


def test_rodar_dispara_taxa_vezes_duracao_pedidos_autenticados() -> None:
    recebidos: list[httpx.Request] = []

    def atender(pedido: httpx.Request) -> httpx.Response:
        recebidos.append(pedido)
        return httpx.Response(201, json={})

    async def execucao() -> Medida:
        async with _cliente(httpx.MockTransport(atender)) as http:
            return await rodar(http, "tok", taxa=100, duracao_s=0.2, corpos=[{"regime": "LP"}])

    medida = asyncio.run(execucao())
    assert (medida.total, medida.erros, len(medida.latencias_ms)) == (20, 0, 20)
    assert {p.headers["authorization"] for p in recebidos} == {"Bearer tok"}
    assert all(p.url.path == "/api/v1/cotacoes" for p in recebidos)


def test_rodar_alterna_os_corpos_e_conta_erros() -> None:
    corpos_vistos: list[dict[str, object]] = []

    def atender(pedido: httpx.Request) -> httpx.Response:
        corpo = json.loads(pedido.content)
        corpos_vistos.append(corpo)
        if corpo["regime"] == "SN":
            return httpx.Response(500)
        if corpo["regime"] == "LR":
            raise httpx.ConnectError("caiu")
        return httpx.Response(201, json={})

    async def execucao() -> Medida:
        async with _cliente(httpx.MockTransport(atender)) as http:
            corpos = [{"regime": "LP"}, {"regime": "SN"}, {"regime": "LR"}]
            return await rodar(http, "t", taxa=60, duracao_s=0.15, corpos=corpos)

    medida = asyncio.run(execucao())
    assert medida.total == 9 and medida.erros == 6
    assert [c["regime"] for c in corpos_vistos[:3]].count("LP") == 1
    assert len(medida.latencias_ms) == 3  # só as respostas 201 entram na latência
