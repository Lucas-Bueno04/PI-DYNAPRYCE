"""Rotas do ciclo mensal sobre o banco real: o que a interface usa."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from dynaprice.aplicacao.casos_de_uso.recalibrar import Recalibrar
from dynaprice.dominio.modelos.autenticacao import Papel, Principal
from tests.adaptadores.test_planilha import planilha
from tests.aplicacao.preco_apoio import REFERENCIA, CenarioDePreco
from tests.dominio.modelos.documentos import documento_tabela_7


def _cabecalho(cliente: TestClient, tenant: UUID, *papeis: Papel) -> dict[str, str]:
    principal = Principal(uuid4(), tenant, frozenset(papeis), True)
    emissor = cliente.app.state.servicos.auth.emissor  # type: ignore[attr-defined]
    return {"Authorization": f"Bearer {emissor.emitir(principal)}"}


def _com_pendente(preco: CenarioDePreco) -> None:
    preco.publicar_politica()
    preco.contrato_tabela_7()
    Recalibrar(preco.fabrica, preco.relogio).executar(preco.tenant, REFERENCIA)


def test_fila_mostra_a_decomposicao(cliente: TestClient, preco: CenarioDePreco) -> None:
    _com_pendente(preco)
    resposta = cliente.get(
        "/api/v1/recomendacoes",
        params={"estado": "pendente"},
        headers=_cabecalho(cliente, preco.tenant, Papel.ANALISAR),
    )
    assert resposta.status_code == 200
    (item,) = resposta.json()
    assert item["preco_proposto"] == "502.55"
    assert item["trajetoria"] == ["502.55", "577.93", "614.27"]
    decomposicao = item["decomposicao"]
    assert decomposicao["preco_alvo"] == "614.27"
    assert decomposicao["nivel_informacao"] == 2
    assert decomposicao["horas_padrao"] == "5.9350"
    assert decomposicao["regime"] == "LP"
    assert decomposicao["tarifa"] == "103.5"
    assert decomposicao["piso"] == "235.00"
    assert decomposicao["kappa"] == "1"


def test_decidir_exportar_e_baixar(cliente: TestClient, preco: CenarioDePreco) -> None:
    _com_pendente(preco)
    cabecalho = _cabecalho(cliente, preco.tenant, Papel.APROVAR)
    (item,) = cliente.get("/api/v1/recomendacoes", headers=cabecalho).json()
    decisao = cliente.post(
        f"/api/v1/recomendacoes/{item['id']}/decisao",
        json={"versao": item["versao"], "acao": "aprovar"},
        headers=cabecalho,
    )
    assert decisao.status_code == 204
    repetida = cliente.post(
        f"/api/v1/recomendacoes/{item['id']}/decisao",
        json={"versao": item["versao"], "acao": "aprovar"},
        headers=cabecalho,
    )
    assert repetida.status_code == 409
    assert cliente.post("/api/v1/exportacoes", headers=cabecalho).status_code == 201


def test_recomendacao_de_outro_inquilino_e_404(cliente: TestClient, preco: CenarioDePreco) -> None:
    _com_pendente(preco)
    cabecalho = _cabecalho(cliente, preco.tenant, Papel.APROVAR)
    (item,) = cliente.get("/api/v1/recomendacoes", headers=cabecalho).json()
    outro = _cabecalho(cliente, uuid4(), Papel.APROVAR)
    resposta = cliente.post(
        f"/api/v1/recomendacoes/{item['id']}/decisao",
        json={"versao": 1, "acao": "aprovar"},
        headers=outro,
    )
    assert resposta.status_code == 404


def test_politicas_publicar_e_listar(cliente: TestClient, preco: CenarioDePreco) -> None:
    analista = _cabecalho(cliente, preco.tenant, Papel.ANALISAR)
    criado = cliente.post(
        "/api/v1/politicas", json={"documento": documento_tabela_7()}, headers=analista
    )
    assert criado.status_code == 201
    versao = criado.json()["versao"]
    assert cliente.post(f"/api/v1/politicas/{versao}/publicar", headers=analista).status_code == 403
    aprovador = _cabecalho(cliente, preco.tenant, Papel.APROVAR)
    assert (
        cliente.post(f"/api/v1/politicas/{versao}/publicar", headers=aprovador).status_code == 204
    )
    assert cliente.get("/api/v1/politicas", headers=analista).json()[0]["estado"] == "publicada"


def test_importar_planilha_por_upload(cliente: TestClient, preco: CenarioDePreco) -> None:
    resposta = cliente.post(
        "/api/v1/importacoes",
        data={"inicio": "2026-01", "fim": "2026-12"},
        files={"arquivo": ("carga.xlsx", planilha(), "application/octet-stream")},
        headers=_cabecalho(cliente, preco.tenant, Papel.ANALISAR),
    )
    assert resposta.status_code == 201
    assert resposta.json()["versao"] == 1


def test_conector_nao_devolve_credencial(cliente: TestClient, preco: CenarioDePreco) -> None:
    admin = _cabecalho(cliente, preco.tenant, Papel.ADMINISTRAR)
    resposta = cliente.put(
        "/api/v1/conectores/omie",
        json={"credencial": {"app_secret": "segredo-x"}, "parametros": {}, "dias_fechamento": 5},
        headers=admin,
    )
    assert resposta.status_code == 204
    listagem = cliente.get("/api/v1/conectores", headers=admin)
    assert "segredo-x" not in listagem.text
    assert listagem.json()[0]["credencial_configurada"] is True


def test_pendencias_e_alertas(cliente: TestClient, preco: CenarioDePreco) -> None:
    cabecalho = _cabecalho(cliente, preco.tenant, Papel.ANALISAR)
    assert (
        cliente.get(
            "/api/v1/vinculos/pendencias", params={"competencia": "2027-01"}, headers=cabecalho
        ).json()
        == []
    )
    assert cliente.get("/api/v1/alertas", headers=cabecalho).status_code == 200


def test_simular_rascunho(cliente: TestClient, preco: CenarioDePreco) -> None:
    preco.contrato_tabela_7()
    resposta = cliente.post(
        "/api/v1/laboratorio/simulacoes",
        json={"documento": documento_tabela_7(), "referencia": "2027-01"},
        headers=_cabecalho(cliente, preco.tenant, Papel.ANALISAR),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["contratos"] == 1
    assert corpo["receita_alvo"] == "614.27"


def test_testar_conector_nao_devolve_segredo(cliente: TestClient, preco: CenarioDePreco) -> None:
    admin = _cabecalho(cliente, preco.tenant, Papel.ADMINISTRAR)
    cliente.put(
        "/api/v1/conectores/fonte-sem-driver",
        json={"credencial": {"app_secret": "segredo-x"}, "parametros": {}, "dias_fechamento": 5},
        headers=admin,
    )
    resposta = cliente.post("/api/v1/conectores/fonte-sem-driver/teste", headers=admin)
    assert resposta.status_code == 200
    assert resposta.json() == {"situacao": "falhou", "detalhe": "conector desconhecido"}
    assert "segredo-x" not in resposta.text
