"""F1.15: contrato HTTP base, Problem Details, OpenAPI exportado e logs sem dado proibido (S7)."""

import json
import logging
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from dynaprice.adaptadores.entrada.api.logs import configurar_logs, limpar_evento

OPENAPI = Path(__file__).resolve().parents[3] / "frontend" / "openapi.json"


def test_saude_responde_200(cliente: TestClient) -> None:
    resposta = cliente.get("/api/v1/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"situacao": "ok"}


def test_saude_confere_o_banco(cliente: TestClient) -> None:
    assert cliente.get("/api/v1/saude").json()["situacao"] == "ok"


def test_404_em_problem_details(cliente: TestClient) -> None:
    resposta = cliente.get("/api/v1/nao-existe")
    assert resposta.status_code == 404
    assert resposta.headers["content-type"].startswith("application/problem+json")
    corpo = resposta.json()
    assert corpo["status"] == 404
    assert {"type", "title", "status"} <= set(corpo)


def test_erro_de_validacao_em_problem_details_sem_ecoar_a_entrada(cliente: TestClient) -> None:
    resposta = cliente.post(
        "/api/v1/auth/entrar", json={"email": "a@b.c", "senha": 123, "extra": "x"}
    )
    assert resposta.status_code == 422
    assert resposta.headers["content-type"].startswith("application/problem+json")
    assert "a@b.c" not in resposta.text


def test_toda_resposta_tem_request_id(cliente: TestClient) -> None:
    assert cliente.get("/api/v1/saude").headers["x-request-id"]


def test_request_id_do_cliente_nao_e_refletido_sem_validar(cliente: TestClient) -> None:
    resposta = cliente.get("/api/v1/saude", headers={"x-request-id": "x" * 500})
    assert resposta.headers["x-request-id"] != "x" * 500


def test_erro_inesperado_nao_expoe_detalhe(cliente: TestClient) -> None:
    from dynaprice.adaptadores.entrada.api.erros import resposta_de_erro_inesperado

    corpo = json.loads(bytes(resposta_de_erro_inesperado().body))
    assert corpo["status"] == 500
    assert "detail" not in corpo


def test_openapi_exportado_esta_atualizado(cliente: TestClient) -> None:
    """Quem muda a API roda `dynaprice api openapi`: o cliente é gerado desse arquivo."""
    assert json.loads(OPENAPI.read_text(encoding="utf-8")) == cliente.app.openapi()  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "campos",
    [
        {"email": "fulano@exemplo.com"},
        {"senha": "s3cr3t-valor"},
        {"token": "abc.def.ghi"},
        {"refresh": "valor-opaco"},
        {"cpf": "123.456.789-09"},
        {"cnpj": "12.345.678/0001-95"},
        {"mensagem": "falha para fulano@exemplo.com"},
        {"mensagem": "documento 123.456.789-09"},
        {"mensagem": "documento 12.345.678/0001-95"},
        {"mensagem": "Authorization: Bearer abc.def.ghi"},
        {"aninhado": {"senha": "s3cr3t-valor"}},
        {"lista": ["fulano@exemplo.com"]},
    ],
)
def test_logs_nao_contem_campos_proibidos(campos: dict[str, object]) -> None:
    limpo = json.dumps(limpar_evento(None, "info", dict(campos)))
    for proibido in (
        "fulano@exemplo.com",
        "s3cr3t-valor",
        "abc.def.ghi",
        "valor-opaco",
        "123.456.789-09",
        "12.345.678/0001-95",
    ):
        assert proibido not in limpo


def test_log_comum_passa_inalterado() -> None:
    assert limpar_evento(None, "info", {"evento": "job", "tentativas": 2}) == {
        "evento": "job",
        "tentativas": 2,
    }


def test_logs_da_biblioteca_padrao_tambem_sao_limpos(capsys: pytest.CaptureFixture[str]) -> None:
    raiz = logging.getLogger()
    originais = list(raiz.handlers)
    try:
        configurar_logs()
        logging.getLogger("qualquer").warning("falha para fulano@exemplo.com")
        saida = capsys.readouterr().err
    finally:
        raiz.handlers[:] = originais
    assert "falha para ***" in saida
    assert "fulano@exemplo.com" not in saida


def test_resposta_de_auth_nao_fica_em_cache(cliente: TestClient) -> None:
    resposta = cliente.post("/api/v1/auth/entrar", json={"email": "a@b.c", "senha": "x"})
    assert resposta.headers["cache-control"] == "no-store"


def test_traceback_tambem_passa_pela_limpeza(capsys: pytest.CaptureFixture[str]) -> None:
    raiz = logging.getLogger()
    originais = list(raiz.handlers)
    try:
        configurar_logs()
        try:
            raise ValueError("duplicado fulano@exemplo.com")
        except ValueError:
            logging.getLogger("qualquer").exception("falhou")
        saida = capsys.readouterr().err
    finally:
        raiz.handlers[:] = originais
    assert "fulano@exemplo.com" not in saida
    assert "ValueError" in saida


def test_n6_token_de_redefinicao_nao_fica_em_cache(cliente: TestClient) -> None:
    resposta = cliente.post(f"/api/v1/usuarios/{uuid4()}/redefinicao")
    assert resposta.headers["cache-control"] == "no-store"


def test_n4_log_de_acesso_nao_e_religado() -> None:
    from dynaprice.adaptadores.entrada.api import logs

    assert "uvicorn.access" not in logs._LOGGERS_DO_UVICORN
