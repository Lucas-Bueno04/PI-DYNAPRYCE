"""F2.2: POST /api/v1/cotacoes sobre o banco real."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from tests.aplicacao.preco_apoio import CenarioDePreco
from tests.dominio.modelos.documentos import documento_tabela_7


def _cabecalho(cliente: TestClient, tenant: UUID, *papeis: Papel) -> dict[str, str]:
    principal = Principal(uuid4(), tenant, frozenset(papeis), True)
    emissor = cliente.app.state.servicos.auth.emissor  # type: ignore[attr-defined]
    return {"Authorization": f"Bearer {emissor.emitir(principal)}"}


def test_cotacao_sem_historico_devolve_201_com_decomposicao(
    cliente: TestClient, preco: CenarioDePreco
) -> None:
    preco.publicar_politica()
    resposta = cliente.post(
        "/api/v1/cotacoes",
        json={"regime": "LP"},
        headers=_cabecalho(cliente, preco.tenant, Papel.ANALISAR),
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["preco"] == "235.00" and corpo["provisorio"] is True
    assert corpo["politica_versao"] == 1
    assert corpo["decomposicao"]["nivel_informacao"] == 0
    assert "piso do regime" in corpo["decomposicao"]["motivo"]


def test_cotacao_parcial_usa_credibilidade(cliente: TestClient, preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    resposta = cliente.post(
        "/api/v1/cotacoes",
        json={"regime": "LP", "meses": 4, "horas_padrao": "3"},
        headers=_cabecalho(cliente, preco.tenant, Papel.APROVAR),
    )
    assert resposta.json()["preco"] == "285.33"


@pytest.mark.parametrize(
    "corpo",
    [
        {},  # regime obrigatório
        {"regime": "XX"},
        {"regime": "LP", "meses": -1},
        {"regime": "LP", "meses": 3},  # histórico sem horas-padrão
        {"regime": "LP", "meses": 2, "horas_padrao": "3", "kappa": "1.3"},  # acima de κ̄
        {"regime": "LP", "extra": 1},
    ],
)
def test_entradas_invalidas_sao_422(
    cliente: TestClient, preco: CenarioDePreco, corpo: dict[str, object]
) -> None:
    preco.publicar_politica()
    resposta = cliente.post(
        "/api/v1/cotacoes", json=corpo, headers=_cabecalho(cliente, preco.tenant, Papel.ANALISAR)
    )
    assert resposta.status_code == 422


def test_sem_politica_publicada_e_409(cliente: TestClient, preco: CenarioDePreco) -> None:
    resposta = cliente.post(
        "/api/v1/cotacoes",
        json={"regime": "LP"},
        headers=_cabecalho(cliente, preco.tenant, Papel.ANALISAR),
    )
    assert resposta.status_code == 409


def test_sem_token_e_401(cliente: TestClient) -> None:
    assert cliente.post("/api/v1/cotacoes", json={"regime": "LP"}).status_code == 401


def test_reproducao_depois_de_nova_politica(cliente: TestClient, preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    cabecalho = _cabecalho(cliente, preco.tenant, Papel.ANALISAR)
    criada = cliente.post("/api/v1/cotacoes", json={"regime": "LP"}, headers=cabecalho).json()
    novo = documento_tabela_7()
    novo["piso_por_segmento"]["LP"] = "250"
    preco.publicar_politica(novo)
    repro = cliente.get(f"/api/v1/cotacoes/{criada['id']}/reproducao", headers=cabecalho)
    assert repro.status_code == 200
    assert Decimal(repro.json()["gravado"]) == Decimal(repro.json()["recalculado"]) == Decimal(235)
    outra = cliente.post("/api/v1/cotacoes", json={"regime": "LP"}, headers=cabecalho).json()
    assert outra["preco"] == "250.00" and outra["politica_versao"] == 2


def test_reproducao_de_outro_inquilino_e_404(cliente: TestClient, preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    criada = cliente.post(
        "/api/v1/cotacoes",
        json={"regime": "LP"},
        headers=_cabecalho(cliente, preco.tenant, Papel.ANALISAR),
    ).json()
    estranho = _cabecalho(cliente, uuid4(), Papel.ANALISAR)
    assert (
        cliente.get(f"/api/v1/cotacoes/{criada['id']}/reproducao", headers=estranho).status_code
        == 404
    )


def test_relatorio_de_provisorios_abaixo_do_esforco(
    cliente: TestClient, preco: CenarioDePreco
) -> None:
    from dynaprice.aplicacao.casos_de_uso.recalibrar import Recalibrar
    from tests.aplicacao.preco_apoio import REFERENCIA

    preco.publicar_politica()
    preco.contrato_tabela_7("P1", meses=6, provisorio=True, vigente="437")
    Recalibrar(preco.fabrica, preco.relogio).executar(preco.tenant, REFERENCIA)
    cabecalho = _cabecalho(cliente, preco.tenant, Papel.ANALISAR)
    resposta = cliente.get(
        "/api/v1/relatorios/provisorios", params={"competencia": "2027-01"}, headers=cabecalho
    )
    assert resposta.status_code == 200
    assert resposta.json() == [
        {
            "contrato_id": "P1",
            "preco_vigente": "437.00",
            "esforco": "614.27",
            "diferenca": "177.27",
            "meses": 6,
        }
    ]
    assert (
        cliente.get(
            "/api/v1/relatorios/provisorios", params={"competencia": "2027-1"}, headers=cabecalho
        ).status_code
        == 422
    )
