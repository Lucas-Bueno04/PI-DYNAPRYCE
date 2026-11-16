"""F3.2: o consultor com papel em dois inquilinos troca de inquilino e o isolamento se mantém."""

from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient

from dynaprice.dominio.modelos.autenticacao import Papel
from tests.api.apoio import criar_usuario
from tests.aplicacao.preco_apoio import CenarioDePreco
from tests.conftest import Banco
from tests.dominio.modelos.documentos import documento_tabela_7

ORIGEM = {"Origin": "https://dynaprice.teste"}


@pytest.fixture
def outro_tenant(banco: Banco) -> UUID:
    with psycopg.connect(banco.superusuario, autocommit=True) as s:
        linha = s.execute(
            "INSERT INTO core.tenant (nome) VALUES ('Segundo') RETURNING id"
        ).fetchone()
    assert linha is not None
    return UUID(str(linha[0]))


def _consultor(cliente: TestClient, a: UUID, b: UUID) -> tuple[dict[str, str], UUID]:
    email, senha = criar_usuario(cliente, a, {Papel.ANALISAR})
    auth = cliente.app.state.servicos.auth  # type: ignore[attr-defined]
    with auth.fabrica.sem_tenant() as uow:
        usuario = uow.usuarios.obter_por_email(email)
        assert usuario is not None
        uow.usuarios.definir_papeis(usuario.id, b, frozenset({Papel.ANALISAR}))
    resposta = cliente.post("/api/v1/auth/entrar", json={"email": email, "senha": senha})
    assert resposta.status_code == 200
    tokens = resposta.json()["tokens"]
    return {"Authorization": f"Bearer {tokens['acesso']}"}, UUID(tokens["tenant_id"])


def test_apos_a_troca_so_se_ve_o_inquilino_novo(
    cliente: TestClient, novo_tenant: UUID, outro_tenant: UUID
) -> None:
    auth = cliente.app.state.servicos.auth  # type: ignore[attr-defined]
    pisos = {novo_tenant: "235", outro_tenant: "999"}
    for tenant, piso in pisos.items():
        documento = documento_tabela_7()
        documento["piso_por_segmento"]["LP"] = piso
        CenarioDePreco(auth.fabrica, auth.relogio, tenant, None).publicar_politica(documento)  # type: ignore[arg-type]

    cabecalho, atual = _consultor(cliente, novo_tenant, outro_tenant)
    destino = outro_tenant if atual == novo_tenant else novo_tenant  # a ordem inicial não importa
    antes = cliente.get("/api/v1/politicas", headers=cabecalho).json()
    assert [p["documento"]["piso_por_segmento"]["LP"] for p in antes] == [pisos[atual]]

    troca = cliente.post(
        "/api/v1/auth/inquilino", json={"tenant_id": str(destino)}, headers={**cabecalho, **ORIGEM}
    )
    assert troca.status_code == 200
    novo = {"Authorization": f"Bearer {troca.json()['acesso']}"}
    depois = cliente.get("/api/v1/politicas", headers=novo).json()
    assert [p["documento"]["piso_por_segmento"]["LP"] for p in depois] == [pisos[destino]]
    cotacao = cliente.post("/api/v1/cotacoes", json={"regime": "LP"}, headers=novo)
    assert cotacao.json()["preco"] == f"{pisos[destino]}.00"


def test_troca_para_inquilino_sem_papel_e_negada(
    cliente: TestClient, novo_tenant: UUID, outro_tenant: UUID
) -> None:
    email, senha = criar_usuario(cliente, novo_tenant, {Papel.ANALISAR})
    entrou = cliente.post("/api/v1/auth/entrar", json={"email": email, "senha": senha}).json()
    cabecalho = {"Authorization": f"Bearer {entrou['tokens']['acesso']}", **ORIGEM}
    resposta = cliente.post(
        "/api/v1/auth/inquilino", json={"tenant_id": str(outro_tenant)}, headers=cabecalho
    )
    assert resposta.status_code == 403
